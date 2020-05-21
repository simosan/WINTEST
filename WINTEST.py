# (注意1) 本AP実行元はWindowsのみに対応
# (注意2) 読み込ませるyamlはoperationに記載したテストコマンドとその結果（標準出力 or 標準出力エラー）をアサーション方式で定義する。
# (注意3) yamlのoperationの定義は以下のとおり。
#           localtest or remotetest   テストをしたいコマンドを定義。
#                                        テスト対象がlocalマシンの場合localtest，remoteマシンの場合remotetest
#           testname                  テスト名を記載する。
#           expect                    testの期待値（とはいってもここでは定義しない）。
#           in or notin               testの期待値（ここで定義）。正規表現対応。
#                                        inは結果に対象文字列が含まれていることを確認するケース。
#                                        notinは結果に対象文字列が含まれていないことを確認するケース。
# (注意4) yaml内の環境変数(_${XXX})をOSに設定した環境変数に置換可能。置換したい場合はOSの環境変数を事前に設定しておくこと。
#        _${HOGE}というyaml環境変数はpowershellでは$env:HOGE="AAA"，DOSではset HOGE="AAA"
#        といった具合に事前設定しておくと，passwd等をベタ書きにしなくてよい。
#        _${XXX}のXXXはa-zA-Z0-9内の文字にすること。特殊文字,2バイト文字はNG
# (注意5) yamlに設定する環境変数(_${XXX})にパスワードを仕込む場合は，必ず，_${~PASSWD}という形式にすること。
#         この形式に沿わないと，実行時コマンドの標準出力にパスワードが表示されてしまう（マスキングされない）。
# (注意6) yamlのhostnameに複数ホスト指定可能。カンマで区切る。
# (注意7) yamlでexpect,in(notin)を定義する際，":"は必ず揃えること。崩れるとエラーになる。
#         xxxxxtestとexpectは文字の先頭を揃える必要がある。
#         [よいパターン]
#             - remotetest: cmd /c echo hogehoge > d:\app\xx\tmp\test.txt;dir D:\app\xx\tmp\test.txt
#               testname: Test1
#               expect:
#                   in: test.txt
#
#         [ダメなパターン]
#             - remotetest: cmd /c echo hogehoge > d:\app\xx\tmp\test.txt;dir D:\app\xx\tmp\test.txt
#                   testname: Test!     ←  remotetestと先頭が揃っていない
#                   expect:             ←　remotetestと先頭が揃っていない
#                   notin: test.txt     ←  expectと:が揃っていない

import sys
import yaml
import os
import re
import subprocess
import ctypes


# ターミナルに出力するクラス（OSプラットフォーム判定処理を元に緑 or 赤処理を定義）


class Termout:

    # グリーンメッセージ用
    @staticmethod
    def greenmsgout(msg):
        # 色つけのためにWindows APIハンドルの設定いろいろ
        STD_OUTPUT_HANDLE = -11
        FOREGROUND_GREEN = 0x0002 | 0x0008  # 緑色/背景黒
        # ターミナル色付け用のハンドル取得
        handle = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        reset = Termout.get_csbi_attributes(handle)
        # メッセージを緑
        ctypes.windll.kernel32.SetConsoleTextAttribute(handle, FOREGROUND_GREEN)
        print(msg)
        # 色をもとに戻す
        ctypes.windll.kernel32.SetConsoleTextAttribute(handle, reset)

    # エラーメッセージ用
    @staticmethod
    def errmsgout(msg):
        # 色つけのためにWindows APIハンドルの設定いろいろ
        STD_OUTPUT_HANDLE = -11
        FOREGROUND_RED = 0x0004 | 0x0008  # 赤色/背景黒
        # ターミナル色付け用のハンドル取得
        handle = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        reset = Termout.get_csbi_attributes(handle)
        # エラーメッセージを赤
        ctypes.windll.kernel32.SetConsoleTextAttribute(handle, FOREGROUND_RED)
        print(msg)
        # 色をもとに戻す
        ctypes.windll.kernel32.SetConsoleTextAttribute(handle, reset)

    # その他色（シアンにした）
    @staticmethod
    def etcmsgout(msg):
        # 色つけのためにWindows APIハンドルの設定いろいろ
        STD_OUTPUT_HANDLE = -11
        FOREGROUND_CYAN = 0x0003 | 0x0008  # シアン（青みたいなやつ）/背景黒
        # ターミナル色付け用のハンドル取得
        handle = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        reset = Termout.get_csbi_attributes(handle)
        # エラーメッセージをシアン
        ctypes.windll.kernel32.SetConsoleTextAttribute(handle, FOREGROUND_CYAN)
        print(msg)
        # 色をもとに戻す
        ctypes.windll.kernel32.SetConsoleTextAttribute(handle, reset)

    # ターミナルバッファクリア（色戻す）
    @staticmethod
    def get_csbi_attributes(handle):
        import struct
        csbi = ctypes.create_string_buffer(22)
        res = ctypes.windll.kernel32.GetConsoleScreenBufferInfo(handle, csbi)
        assert res

        (bufx, bufy, curx, cury, wattr,
         left, top, right, bottom, maxx, maxy) = struct.unpack("hhhhHhhhhhh",
                                                               csbi.raw)
        return wattr


# 共通処理クラス


class CommonCls:

    # yamlの環境変数を展開(_${XXX}のXXXを展開)
    @staticmethod
    def envvarexpansion(var):
        # _${XXXXXX}はマスキングのため即リターン
        if var == '_${XXXXXX}':
            return var
        # 先頭が_$か本yamlの仕様どおり$_かチェック
        if var[0:2] == "_$":
            # 正規表現で環境変数文字列（_${XXX}）を抽出
            pattern = '_\${?(.*)}'
            result = re.match(pattern, var)
            if result:
                envstr = result.group(1)
                # OS環境変数を取得
                # import pdb; pdb.set_trace()
                try:
                    varrtn = os.environ[envstr]
                except KeyError:
                    Termout.errmsgout(var + "の値が設定されていません")
                    sys.exit(255)
            else:
                Termout.errmsgout("環境変数の設定ルールに誤りがあります（正：_${XXX})")
                sys.exit(255)
        else:
            Termout.errmsgout("環境変数の設定ルールに誤りがあります（正：_${XXX})")
            sys.exit(255)
        return varrtn

    # ope内の環境変数（_${XXX}）を値に置換
    @staticmethod
    def replacevar(opestr):
        # 正規表現で環境変数文字列（_${XXX}）を抽出
        pattern = '(_\${[a-zA-Z0-9]+})'
        result = re.findall(pattern, opestr)
        # マッチした環境変数のリストをenvvarexpansionで値取得
        # import pdb;pdb.set_trace()
        replaceopestr = opestr
        for i in result:
            tmpvar = CommonCls.envvarexpansion(i)
            replaceopestr = replaceopestr.replace(i, tmpvar)
        return replaceopestr


# Windowsターミナルテスト（ローカル or リモート）実行クラス
# yamlのTargetCon毎にインスタンスが生成される。

class WinCommandTest:

    def __init__(self, hostdt, hstnm):
        # 初期化
        self.h = ""
        self.u = ""
        self.p = ""

        for idx in hostdt:
            for k, v in idx.items():
                if k == 'hostname':
                    self.h = hstnm
                elif k == 'userid':
                    self.u = v
                elif k == 'passwd':
                    self.p = CommonCls.envvarexpansion(v)

    # TargetConのOperationを処理
    def servertest(self, oped):

        rtn = ''
        for idx in oped:
            # k=localtest or remotetest or expect or in(notin) v=操作
            for k, v in idx.items():
                if k == "localtest":
                    self.localtest(idx)
                    rtn = True
                elif k == "remotetest":
                    self.remotetest(idx)
                    rtn = True
                elif k == "testname":
                    pass
                elif k == "expect":
                    pass
                elif k == "in" or k == "notin":
                    pass
                else:
                    Termout.errmsgout('指定不可能な文字列を使用しています k=' + k)
                    rtn = False
                    break
            else:
                continue
            break

        return rtn

    def localtest(self, dict):
        # コマンド実行（yamlのシーケンス（'-'）単位）
        try:
            cmdoutput = self.doscmd(dict.get('localtest'))
            self.chkoutput(cmdoutput,
                           dict.get('localtest'),
                           dict.get('testname'),
                           dict.get('expect'))
        except KeyError as e:
            Termout.errmsgout('キーに誤りがあります->' + dict.items())
            Termout.errmsgout(str(e))
            sys.exit(255)

    def remotetest(self, dict):
        # Windowsリモートコマンド（Powershellコマンドレット）
        # useridとpasswdが設定されていればPowershellにcredentialを設定
        if len(self.u) != 0:
            if len(self.p) == 0:
                Termout.errmsgout('useridが設定されている場合はpasswdは空にできません!')
                sys.exit(255)
            pscmd = 'powershell -c "$pass=ConvertTo-SecureString -AsPlainText \'' + self.p + '\' -Force;' + \
                    '$credential=New-Object System.Management.Automation.PSCredential \'' + self.u + '\', $pass;' + \
                    'Invoke-Command -ComputerName ' + self.h + ' -Credential $credential ' + \
                    ' -ScriptBlock {' + dict.get('remotetest') + '}"'
        else:
            pscmd = 'powershell -c "Invoke-Command -ComputerName ' + self.h + \
                ' -ScriptBlock {' + dict.get('remotetest') + '}"'
        try:
            cmdoutput = self.doscmd(pscmd)
            self.chkoutput(cmdoutput,
                           dict.get('remotetest'),
                           dict.get('testname'),
                           dict.get('expect'))
        except KeyError as e:
            Termout.errmsgout('キーに誤りがあります->' + dict.items())
            Termout.errmsgout(str(e))
            sys.exit(255)

    def doscmd(self, cmdline):
        try:
            cmdline = CommonCls.replacevar(cmdline)
            # command実行
            child = subprocess.Popen(cmdline, shell=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = child.communicate()
            # 結果は標準出力か標準エラー出力かはケースバイケースなので，結合して返す。
            stdstr = stdout.decode('shift_jis') + stderr.decode('shift_jis')

        except subprocess.SubprocessError as e:
            Termout.errmsgout('CommandException Error!')
            Termout.errmsgout(str(e))
            sys.exit(255)

        return stdstr

    def chkoutput(self, outstrline, testcmd, testname, expt):
        Termout.etcmsgout("=========TestStart===========")
        # print("OutPutString: " + outstrline)
        print("TestName: " + testname)
        print("Check Command : " + testcmd)
        flg = False
        try:
            for k, v in expt.items():
                print("Expect : " + v)
                print("ExpectMode : " + k)
            if k == 'in':
                rslt = re.search(expt.get('in'), outstrline)
                print("MatchedOutput: " + str(rslt))
                if str(rslt) != 'None':
                    flg = True
            else:
                rslt = re.search(expt.get('notin'), outstrline)
                print("NotMatched Check: " + str(rslt))
                if str(rslt) == 'None':
                    flg = True
        except AttributeError as e:
            Termout.errmsgout("chkoutput Error!")
            Termout.errmsgout(str(e))
            sys.exit(255)

        if flg is True:
            Termout.greenmsgout("Test Success!!")
        else:
            Termout.errmsgout("Test Fault!!")

        Termout.etcmsgout("=============================")
        print('\n')


if __name__ == '__main__':

    args = sys.argv
    if 2 != len(args):
        Termout.errmsgout("引数エラー: python スクリプト yamlパス")
        sys.exit(255)

    # yaml(定義)を読み込む
    with open(args[1], encoding="utf-8") as file:
        data = yaml.load(file, Loader=yaml.SafeLoader)
        for indx, val in enumerate(data):
            TRGT = 'TargetCon' + str(indx+1)
            # ConnParm-hostname複数指定があればループ
            hostlist = data[TRGT]['ConnParm'][0].get("hostname").split(',')
            for host in hostlist:
                Termout.greenmsgout("=" * 8 + TRGT + "-" + host + "=" * 8)
                print('\n')
                objWin = WinCommandTest(data[TRGT]['ConnParm'], host)
                rtn = objWin.servertest(data[TRGT]['Operation'])
                if rtn is False:
                    Termout.errmsgout("servertest Error!")
                    sys.exit(255)
    Termout.greenmsgout("処理が完了しました")
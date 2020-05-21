# NAME

WINTEST.py - Windows Server Infrastructure Behavior and State Testing tool


## Overview

A python script inspired by Serverspec, Infrastructure Testing tool.
This is an assertion-based test tool that checks the expected value of Windows commands according to the definition of the yaml file specified in the argument.

## Prerequisite

This tool has been tested on Windows10 or 2016+ where python is installed.

* python 3.7+
* python library(pyyaml)

## Usage

    $ python WINTEST.py xxxx.yaml


xxxx is optional.


## How to Write a YAML File (Configuration Definition)

Summary of Description

```
    TargetCon1:
      ConnParm:
      - hostname: XXX.XXX.XXX.XXX
      - userid: Administrator
      - passwd: _${XXXXXPASSWD}
      Operation:
      - remotetest: dcdiag /v
        testname: Verify the validity of the domain controller
        expect:
         notin: エラー
```      
---
- hostname: hostname or IP  You can specify more than one by comma.
- userid: User ID to connect to.
- passwd: Hardcodes are not acceptable. The format should be _${XXXXPASSWD}.
- remotetest or localtest: Confirmation commands for testing. localtest for local checking and remotetest for remote server checking
- testname: Test name
- expect: No value is specified.
- in or notin: expected value of standard output or standard error output result of the command  ※regular expression support
---


## Note

1) This AP execution source supports only Windows.

2) The yaml to be read defines the test command described in operation and its result (standard output or standard output error) in the assertion method.

3) The definition of operation in YAML is as follows.
   localtest or remotetest   Define the command you want to test.If the test target is a local machine, then localtest, if the test target is a remote machine, then remotetest

   testname   The name of the test.
   expect     The expectation value of the expect test (which is not defined here).
   in or notin    The expected value of the in or notin test (defined here). Regular expression support.
                  "in" is a case where the result confirms that the target string is included.
                  "Notin" is a case where the result confirms that the target string is not included.

4) Environment variables (\_${XXX}) in yaml can be replaced with environment variables set to the OS. If you want to replace it, you need to set the OS environment variables in advance.
The yaml environment variable $\_{HOGE} should be set in advance like $env:HOGE="AAA" in powershell or set HOGE="AAA" in DOS, so that you don't have to write passwd and so on.
XXX in \_${XXX} should be the letters in a-zA-Z0-9. Special characters and 2-byte characters are not allowed.

5) When inserting a password into the environment variable (\_${XXX}) in yaml, be sure to use the format $\_{~PASSWD}.
If this format is not followed, the password will be displayed (not masked) in the standard output of the runtime command.

6) Multiple hosts can be specified in hostname of yaml. Separate them with commas.

## Licence

SSHOPE.py is under [MIT license](https://en.wikipedia.org/wiki/MIT_License).



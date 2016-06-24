#!/usr/bin/env python2
# -*- coding: utf-8 -*-

########################################################################
########################## [ poor man's lpr ] ##########################
########################################################################

# python standard library
import sys, socket, argparse

# ----------------------------------------------------------------------

def usage():
  parser = argparse.ArgumentParser(description="Line Printer Daemon Protocol (RFC 1179) Print.")
  parser.add_argument("hostname", help="printer ip address or hostname")
  parser.add_argument("filename", help="file to be delivered to printer")
  return parser.parse_args()

# ----------------------------------------------------------------------

# parse args
args = usage()      

# read local file
try:
  with open(args.filename, mode='rb') as f:
    data = f.read()
  f.close()
except IOError as e:
  print "Cannot read from file: " + str(e)
  sys.exit()

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

# --------[ RFC 1179 | 6.2 02 - Receive control file ]------------------

hostname = socket.gethostname()
username = "nobody"

ctrl = 'H'+hostname[:31]+"\n" \
     + 'P'+username[:31]+"\n"

s.send("\002"+str(len(ctrl))+" "+"cfA001"+hostname+"\n")
check_acknowledgement()
s.send(ctrl + "\000") # send control file || file complete indicator
check_acknowledgement()

# --------[ RFC 1179 | 6.3 03 - Receive data file ]---------------------

s.send("\003"+str(len(data))+" "+"dfA001"+hostname+"\n")
check_acknowledgement()
s.sendall(data + "\000") # send data file || file complete indicator
check_acknowledgement()

# ----------------------------------------------------------------------

s.close()

# -*- coding: utf-8 -*-

# python standard library
from __future__ import print_function
from socket import socket
import sys, re, os, stat, time

# third party modules
from colorama import Fore, Back, Style

# ----------------------------------------------------------------------

# return first item of list or alternative
def item(mylist, alternative=""):
  return next(iter(mylist), alternative)

# split list into chunks of equal size
def chunks(l, n):
  for i in xrange(0, len(l), n):
    yield l[i:i+n]

# ----------------------------------------------------------------------

class log():
  # open logfile
  def open(self, filename):
    try:
      return open(filename, mode='wb')
    except IOError as e:
      output().errmsg("Cannot open logfile", str(e))
      return None

  # write raw data to logfile
  def write(self, logfile, data):
    # logfile open and data non-empty
    if logfile and data:
      try:
        logfile.write(data)
      except IOError as e:
        output().errmsg("Cannot log", str(e))

  # write comment to logfile
  def comment(self, logfile, line):
    comment = "%" + ("[ " + line + " ]").center(72, '-')
    self.write(logfile, os.linesep + comment + os.linesep)

  # close logfile
  def close(self, logfile):
    try:
      logfile.close()
    except IOError as e:
      output().errmsg("Cannot close logfile", str(e))

# ----------------------------------------------------------------------

class output():
  # show send commands (debug mode)
  def send(self, str, mode):
    ### str = os.linesep.join(str.splitlines())
    if str: print(Back.CYAN + str + Style.RESET_ALL)
    if str and mode == 'hex':
      if str: print(Fore.CYAN + ":".join("{:02x}".format(ord(c)) for c in str) + Style.RESET_ALL)

  # show recv commands (debug mode)
  def recv(self, str, mode):
    ### str = os.linesep.join(str.splitlines())
    if str: print(Back.MAGENTA + str + Style.RESET_ALL)
    if str and mode == 'hex':
      print(Fore.MAGENTA + ":".join("{:02x}".format(ord(c)) for c in str) + Style.RESET_ALL)

  # show information
  def info(self, msg):
    ### if str: print(":".join("{:02x}".format(ord(c)) for c in msg))
    if msg: print(Back.BLUE + msg + Style.RESET_ALL)

  # show raw data
  def raw(self, msg, eol=None):
    if msg: print(Fore.YELLOW + msg + Style.RESET_ALL, end=eol) # TBD: CYAN

  # show chit-chat
  def chitchat(self, msg, eol=None):
    if msg: print(Style.DIM + msg + Style.RESET_ALL, end=eol)
    sys.stdout.flush()

  # show warning message
  def warning(self, msg):
    if msg: print(Back.RED + msg + Style.RESET_ALL)

  # show green message
  def green(self, msg):
    if msg: print(Back.GREEN + msg + Style.RESET_ALL)

  # show error message
  def errmsg(self, msg, info=""):
    if msg: print(Back.RED + msg + Style.RESET_ALL + Style.DIM + " (" + info + ")" + Style.RESET_ALL)

  # show directory listing
  def psdir(self, isdir, size, atime, name, mtime):
    if isdir: print("d %8s   %s %s %s" % (size, atime, Style.DIM + "(last written: " + mtime + ")" + Style.RESET_ALL, Style.BRIGHT + Fore.BLUE + name + Style.RESET_ALL))
    else:     print("- %8s   %s %s %s" % (size, atime, Style.DIM + "(last written: " + mtime + ")" + Style.RESET_ALL, name))

  # show directory listing
  def pjldir(self, name, size):
    if size: print("- %8s   %s" % (size, name))
    else:    print("d %8s   %s" % ("-", Style.BRIGHT + Fore.BLUE + name + Style.RESET_ALL))

  # show directory listing
  def pcldir(self, size, mtime, id, name):
    print("- %8s   %s %s %s" % (size, mtime, Style.DIM + "(macro id: " + id + ")" + Style.RESET_ALL, name))

  # show output from df
  def df(self, args):
    self.info("%-18s %-11s %-11s %-9s %-10s %-8s %-9s %-10s %-10s" % args)

  # show fuzzing results
  def fuzzed(self, path, cmd, opt):
      opt1, opt2, opt3 = opt
      if isinstance(opt1, bool): opt1 = (Back.GREEN + str(opt1) + Back.BLUE + "   ") if opt1 else (Back.RED + str(opt1) + Back.BLUE + "  ")
      if isinstance(opt2, bool): opt2 = (Back.GREEN + str(opt2) + Back.BLUE + "   ") if opt2 else (Back.RED + str(opt2) + Back.BLUE + "  ")
      if isinstance(opt3, bool): opt3 = (Back.GREEN + str(opt3) + Back.BLUE + "   ") if opt3 else (Back.RED + str(opt3) + Back.BLUE + "  ")
      opt = opt1, opt2, opt3
      self.info("%-35s %-12s %-7s %-7s %-7s" % ((path, cmd) + opt))

  # countdown from sec to zero
  def countdown(self, msg, sec, cmd):
    try:
      sys.stdout.write(msg)
      for x in reversed(range(1, sec+1)):
        sys.stdout.write(" " + str(x))
        sys.stdout.flush()
        time.sleep(1)
      print(" KABOOM!")
      return True
    except KeyboardInterrupt:
      print("")

  # show horizontal line
  def hline(self):
    self.info("─" * 72)

# ----------------------------------------------------------------------

class file():
  # read from local file
  def read(self, path):
    try:
      with open(path, mode='rb') as f:
        data = f.read()
      f.close()
      return data
    except IOError as e:
      output().errmsg("Cannot read from file", str(e))

  # write to local file
  def write(self, path, data, m='wb'):
    try:
      with open(path, mode=m) as f:
        f.write(data)
      f.close()
    except IOError as e:
      output().errmsg("Cannot write to file", str(e))

  # append to local file
  def append(self, path, data):
    self.write(path, data, 'ab')

# ----------------------------------------------------------------------

class conn(object):
  # create debug connection object
  def __init__(self, mode, debug, quiet):
    self.mode  = mode
    self.debug = debug
    self.quiet = quiet
    self._file = None
    self._sock = socket()

  # open connection
  def open(self, target):
    # target is a character device
    if os.path.exists(target) \
      and stat.S_ISCHR(os.stat(target).st_mode):
        self._file = os.open(target, os.O_RDWR)
    # treat target as ipv4 socket
    else: self._sock.connect((target, 9100))

  # close connection
  def close(self, *arg):
    # close file descriptor
    if self._file: os.close(self._file)
    # close inet socket
    else: self._sock.close()

  # set timeout
  def timeout(self, *arg):
    self._sock.settimeout(*arg)

  # send data
  def send(self, data):
    if self.debug: output().send(self.beautify(data), self.debug)
    # send data to device
    if self._file: return os.write(self._file, data)
    # send data to socket
    else: return self._sock.send(data)

  # receive data
  def recv(self, bytes):
    # receive data from device
    if self._file: data = os.read(self._file, bytes)
    # receive data from socket
    else: data = self._sock.recv(bytes)
    # output recv data when in debug mode
    if self.debug: output().recv(self.beautify(data), self.debug)
    return data

  # receive data until a delimiter is reached
  def recv_until(self, delimiter, fb=True, crop=True, binary=False):
    data = ""
    sleep = 0.01 # pause in loop
    watchdog = 0.0 # watchdog timer
    r = re.compile(delimiter, re.DOTALL)
    s = re.compile("^\x04?\x0d?\x0a?" + delimiter, re.DOTALL)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    while not r.search(data):
      # visual feedback on large/slow data transfers
      if not (self.quiet or self.debug) and watchdog > 2.0:
        if int(watchdog * 1000) % 100 == 0: # every 0.1 sec
          output().chitchat(str(len(data)) + " bytes received\r", '')
      data += self.recv(4096) # receive actual data
      if int(watchdog * 100) % 300 == 0: recv = len(data) # every 3 sec
      watchdog += sleep # workaround for endless loops w/o socket timeout
      time.sleep(sleep) # happens on some devices - python socket error!?
      # watchdog timeout plus we are not receiving data anymore
      if watchdog > self._sock.gettimeout() and len(data) == recv:
        output().errmsg("Receiving data failed", "watchdog timeout")
        return data
      # clear current line from 'so-many bytes received' chit-chat
      if not (self.quiet or self.debug) and watchdog > 2.0:
        if int((watchdog - sleep) * 1000) % 100 == 0: # every 0.1 sec
          output().chitchat(' ' * 24 + "\r", '')
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # warn if feedback expected but response empty (= delimiter only)
    # this also happens for data received out of order (e.g. brother)
    if fb and s.search(data):
      output().chitchat("No data received.")
    # remove delimiter itself from data
    if crop: data = r.sub('', data)
    # crop uel sequence at the beginning
    data = re.sub(r'(^' + const.UEL + ')', '', data)
    '''
    ┌─────────────────────────────────────────────────────────────────────┐
    │ delimiters -- note that carriage return (0d) is optional in ps/pjl  │
    ├─────────────────────────┬─────────────────────┬─────────────────────┤
    │                         │         PJL         │      PostScript     │
    ├─────────────────────────┼─────────┬───────────┼────────┬────────────┤
    │                         │ send    │ recv      │ send   │ recv       │
    ├─────────────────────────┼─────────┼───────────┼────────┼────────────┤
    │ normal commands (ascii) │ 0d? 0a  │ 0d+ 0a 0c │ 0d? 0a │ 0d? 0a 04? │
    ├─────────────────────────┼─────────┼───────────┼────────┼────────────┤
    │ file transfers (binary) │ 0d? 0a  │ 0c        │ 0d? 0a │ -          │
    └─────────────────────────┴─────────┴───────────┴────────┴────────────┘
    '''
    # crop end-of-transmission chars
    if self.mode == 'ps':
      data = re.sub(r'^\x04', '', data)
      if not binary: data = re.sub(r'\x0d?\x0a$', '', data)
    else: # pjl and pcl mode
      if binary: data = re.sub(r'\x0c$', '', data)
      else: data = re.sub(r'\x0d+\x0a?\x0c$', '', data)
    # crop whitespaces/newline as feedback
    if not binary: data = data.strip()
    return data

  # beautify debug output
  def beautify(self, data):
    # remove sent/recv uel sequences
    data = re.sub(r'' + const.UEL, '', data)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if self.mode == 'ps':
      # remove sent postscript header
      data = re.sub(r'' + re.escape(const.PS_HEADER), '', data)
      # remove sent delimiter token
      data = re.sub(r'\(\\nDELIMITER\d+\\n\) echo\n', '', data)
      # remove recv delimiter token
      data = re.sub(r'DELIMITER\d+', '', data)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    elif self.mode == 'pjl':
      # remove sent/recv delimiter token
      data = re.sub(r'@PJL ECHO\s+DELIMITER\d+', '', data)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    elif self.mode == 'pcl':
      # remove sent delimiter token
      data = re.sub(r'\x1b\*s-\d+X', '', data)
      # remove recv delimiter token
      data = re.sub(r'PCL\x0d?\x0a?\x0c?ECHO -\d+', '', data)
      # replace sent escape sequences
      data = re.sub(r'(' + const.ESC + ')', '<Esc>', data)
      pass
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # replace lineseps in between
    data = re.sub(r'\x0d?\x0a?\x0c', os.linesep, data)
    # remove eot/eof sequences
    data = data.strip(const.EOF)
    return data

# ----------------------------------------------------------------------

class const(): # define constants
  SEP         = '/' # use posixoid path separator
  EOL         = '\r\n' # line feed || carriage return
  ESC         = '\x1b' # used to start escape sequences
  UEL         = ESC + '%-12345X' # universal exit language
  EOF         = EOL + '\x0c\x04' # potential end of file chars
  DELIMITER   = "DELIMITER" # delimiter marking end of repsonse
  # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  PS_ERROR    = '%%\[ Error: (.*)\]%%'
  PS_FLUSH    = '%%\[ Flushing: (.*)\]%%'
  PS_PROMPT   = '>' # TBD: could be derived from PS command 'prompt'
  PS_HEADER   = '@PJL ENTER LANGUAGE = POSTSCRIPT\n%!PS\n' \
              + '/echo {(%stdout) (w) file dup 3 2 roll writestring flush} def\n' \
              + '/dump {dup type /dicttype eq {{echo} forall} {==} ifelse} def\n'
  PCL_HEADER  = '@PJL ENTER LANGUAGE = PCL' + EOL + ESC
  # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  SUPERBLOCK  = '31337' # define super macro id to contain pclfs table
  BLOCKRANGE  = range(10000,20000) # use those macros for file content
  NONEXISTENT = -1 # file size to be returned if a file does not exist
  # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  PS_VOL      = '' # no default volume in PostScript (aka: any volume)
  PJL_VOL     = '0:/' # default pjl volume name || unix path seperator

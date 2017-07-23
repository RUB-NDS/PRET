# -*- coding: utf-8 -*-

# python standard library
from __future__ import print_function
from socket import socket
import sys, os, re, stat, math, time, datetime

# third party modules
try: # unicode monkeypatch for windoze
  import win_unicode_console
  win_unicode_console.enable()
except:
  msg = "Please install the 'win_unicode_console' module."
  if os.name == 'nt': print(msg)

try: # os independent color support
  from colorama import init, Fore, Back, Style
  init() # required to get colors on windoze
except ImportError:
  msg = "Please install the 'colorama' module for color support."
  # poor man's colored output (ANSI)
  class Back():
    BLUE      = '\x1b[44m' if os.name == 'posix' else ''
    CYAN      = '\x1b[46m' if os.name == 'posix' else ''
    GREEN     = '\x1b[42m' if os.name == 'posix' else ''
    MAGENTA   = '\x1b[45m' if os.name == 'posix' else ''
    RED       = '\x1b[41m' if os.name == 'posix' else ''
  class Fore():
    BLUE      = '\x1b[34m' if os.name == 'posix' else ''
    CYAN      = '\x1b[36m' if os.name == 'posix' else ''
    MAGENTA   = '\x1b[35m' if os.name == 'posix' else ''
    YELLOW    = '\x1b[33m' if os.name == 'posix' else ''
  class Style():
    DIM       = '\x1b[2m'  if os.name == 'posix' else ''
    BRIGHT    = '\x1b[1m'  if os.name == 'posix' else ''
    RESET_ALL = '\x1b[0m'  if os.name == 'posix' else ''
    NORMAL    = '\x1b[22m' if os.name == 'posix' else ''
  print(Back.RED + msg + Style.RESET_ALL)

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
      output().errmsg("Cannot open logfile", e)
      return None

  # write raw data to logfile
  def write(self, logfile, data):
    # logfile open and data non-empty
    if logfile and data:
      try:
        logfile.write(data)
      except IOError as e:
        output().errmsg("Cannot log", e)

  # write comment to logfile
  def comment(self, logfile, line):
    comment = "%" + ("[ " + line + " ]").center(72, '-')
    self.write(logfile, os.linesep + comment + os.linesep)

  # close logfile
  def close(self, logfile):
    try:
      logfile.close()
    except IOError as e:
      output().errmsg("Cannot close logfile", e)

# ----------------------------------------------------------------------

class output():
  # show send commands (debug mode)
  def send(self, str, mode):
    if str: print(Back.CYAN + str + Style.RESET_ALL)
    if str and mode == 'hex':
      print(Fore.CYAN + conv().hex(str, ':') + Style.RESET_ALL)

  # show recv commands (debug mode)
  def recv(self, str, mode):
    if str: print(Back.MAGENTA + str + Style.RESET_ALL)
    if str and mode == 'hex':
      print(Fore.MAGENTA + conv().hex(str, ':') + Style.RESET_ALL)

  # show information
  def info(self, msg, eol=None):
    if msg: print(Back.BLUE + msg + Style.RESET_ALL, end=eol)
    sys.stdout.flush()

  # show raw data
  def raw(self, msg, eol=None):
    if msg: print(Fore.YELLOW + msg + Style.RESET_ALL, end=eol)
    sys.stdout.flush()

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
    info = str(info).strip()
    if info: # monkeypatch to make python error message less ugly
      info = item(re.findall('Errno -?\d+\] (.*)', info), '') or info.splitlines()[-1]
      info = Style.RESET_ALL + Style.DIM + " (" + info.strip('<>') + ")" + Style.RESET_ALL
    if msg: print(Back.RED + msg + info)

  # show printer and status
  def discover(self, (ipaddr, (device, uptime, status, prstat))):
    ipaddr = output().strfit(ipaddr, 15)
    device = output().strfit(device, 27)
    uptime = output().strfit(uptime,  8)
    status = output().strfit(status, 23)
    if device.strip() != 'device': device = Style.BRIGHT + device + Style.NORMAL
    if prstat == '1': status = Back.GREEN  + status + Back.BLUE # unknown
    if prstat == '2': status = Back.GREEN  + status + Back.BLUE # running
    if prstat == '3': status = Back.YELLOW + status + Back.BLUE # warning
    if prstat == '4': status = Back.GREEN  + status + Back.BLUE # testing
    if prstat == '5': status = Back.RED    + status + Back.BLUE # down
    line = (ipaddr, device, uptime, status)
    output().info('%-15s  %-27s  %-8s  %-23s' % line)

  # recursively list files
  def psfind(self, name):
    vol = Style.DIM + Fore.YELLOW + item(re.findall("^(%.*%)", name)) + Style.RESET_ALL
    name = Fore.YELLOW + const.SEP + re.sub("^(%.*%)", '', name) + Style.RESET_ALL
    print("%s %s" % (vol, name))

  # show directory listing
  def psdir(self, isdir, size, mtime, name, otime):
    otime = Style.DIM + "(created " + otime + ")" + Style.RESET_ALL 
    vol = Style.DIM + Fore.YELLOW + item(re.findall("^(%.*%)", name)) + Style.RESET_ALL
    name = re.sub("^(%.*%)", '', name) # remove volume information from filename
    name = Style.BRIGHT + Fore.BLUE + name + Style.RESET_ALL if isdir else name
    if isdir: print("d %8s   %s %s %s %s" % (size, mtime, otime, vol, name))
    else:     print("- %8s   %s %s %s %s" % (size, mtime, otime, vol, name))

  # show directory listing
  def pjldir(self, name, size):
    name = name if size else Style.BRIGHT + Fore.BLUE + name + Style.RESET_ALL
    if size: print("- %8s   %s" % (size, name))
    else:    print("d %8s   %s" % ("-", name))

  # show directory listing
  def pcldir(self, size, mtime, id, name):
    id = Style.DIM + "(macro id: " + id + ")" + Style.RESET_ALL
    print("- %8s   %s %s %s" % (size, mtime, id, name))

  # show output from df
  def df(self, args):
    self.info("%-16s %-11s %-11s %-9s %-10s %-8s %-9s %-10s %-10s" % args)

  # show fuzzing results
  def fuzzed(self, path, cmd, opt):
      opt1, opt2, opt3 = opt
      if isinstance(opt1, bool): opt1 = (Back.GREEN + str(opt1) + Back.BLUE + "   ")\
                                 if opt1 else (Back.RED + str(opt1) + Back.BLUE + "  ")
      if isinstance(opt2, bool): opt2 = (Back.GREEN + str(opt2) + Back.BLUE + "   ")\
                                 if opt2 else (Back.RED + str(opt2) + Back.BLUE + "  ")
      if isinstance(opt3, bool): opt3 = (Back.GREEN + str(opt3) + Back.BLUE + "   ")\
                                 if opt3 else (Back.RED + str(opt3) + Back.BLUE + "  ")
      opt = opt1, opt2, opt3
      self.info("%-35s %-12s %-7s %-7s %-7s" % ((path, cmd) + opt))

  # show captured jobs
  def joblist(self, (date, size, user, name, soft)):
    user = output().strfit(user, 13)
    name = output().strfit(name, 22)
    soft = output().strfit(soft, 20)
    line = (date, size, user, name, soft)
    output().info('%-12s %5s  %-13s  %-22s  %-20s' % line)

  # show ascii only
  def ascii(self, data):
    data = re.sub(r"(\x00){10}", "\x00", data) # shorten nullbyte streams
    data = re.sub(r"([^ -~])", ".", data) # replace non-printable chars
    self.raw(data, "")

  # show binary dump
  def dump(self, data):
    # experimental regex to match sensitive strings like passwords
    data = re.sub(r"[\x00-\x06,\x1e]([!-~]{6,}?(?!\\0A))\x00{16}", "START" + r"\1" + "STOP", data)
    data = re.sub(r"\00+", "\x00", data) # ignore nullbyte streams
    data = re.sub(r"(\x00){10}", "\x00", data) # ignore nullbyte streams
    data = re.sub(r"([\x00-\x1f,\x7f-\xff])", ".", data)
    data = re.sub(r"START([!-~]{6,}?)STOP", Style.RESET_ALL + Back.BLUE + r"\1" + Style.RESET_ALL + Fore.YELLOW, data)
    self.raw(data, "")

  # dump ps dictionary
  def psdict(self, data, indent=''):
    reload(sys) # workaround for non-ascii output
    sys.setdefaultencoding('UTF8')
    # convert list to dictionary with indices as keys
    if isinstance(data, list):
      data = dict(enumerate(data))
    # data now is expected to be a dictionary
    if len(data.keys()) > 0: last = sorted(data.keys())[-1]
    for key, val in sorted(data.items()):
      type  = val['type'].replace('type', '')
      value = val['value']
      perms = val['perms']
      recursion = False
      # current enty is a dictionary
      if isinstance(value, dict):
        value, recursion = '', True
      # current enty is a ps array
      if isinstance(value, list):
        try: # array contains only atomic values
          value = ' '.join(x['value'] for x in value)
        except: # array contains further list or dict
          # value = sum(val['value'], [])
          value, recursion = '', True
      # value = value.encode('ascii', errors='ignore')
      node = '┬' if recursion else '─'
      edge = indent + ('└' if key == last else '├')
      # output current node in dictionary
      print("%s%s %-3s  %-11s  %-30s  %s" % (edge, node, perms, type, key, value))
      if recursion: # ...
        self.psdict(val['value'], indent + (' ' if key == last else '│'))

  # show some information
  def psonly(self):
   self.chitchat("Info: This only affects jobs printed by a PostScript driver")

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
  def hline(self, len=72):
    self.info("─" * len)

  # crop/pad string to fixed length
  def strfit(self, str, max):
    str = str.strip() or "-"
    if str.startswith('(') and str.endswith(')'): str = str[1:-1]
    # crop long strings
    if len(str) > max:
      str = str[0:max-1] + "…"
    # pad short strings
    return str.ljust(max)

# ----------------------------------------------------------------------

class conv():
  # return current time
  def now(self):
    return int(time.time())

  # return time elapsed since unix epoch
  def elapsed(self, date, div=1, short=False):
    date = str(datetime.timedelta(seconds=int(date)/div))
    return date.split(",")[0] if short else date

  # return date dependend on current year
  def lsdate(self, date):
    year1 = datetime.datetime.now().year
    year2 = datetime.datetime.fromtimestamp(date).year
    pdate = '%b %e ' if os.name == 'posix' else '%b %d '
    format = pdate + "%H:%M" if year1 == year2 else pdate + " %Y"
    return time.strftime(format, time.localtime(date))

  # return date plus/minus given seconds
  def timediff(self, seconds):
    return self.lsdate(self.now() + self.int(seconds) / 1000)

  # convert size to human readble value
  def filesize(self, num):
    num = self.int(num)
    for unit in ['B','K','M']:
      if abs(num) < 1024.0:
        return (("%4.1f%s" if unit == 'M' else "%4.0f%s") % (num, unit)) 
      num /= 1024.0

  # remove carriage return from line breaks
  def nstrip(self, data):
    return re.sub(r'\r\n', '\n', data)

  # convert string to hexdecimal
  def hex(self, data, sep=''):
    return sep.join("{:02x}".format(ord(c)) for c in data)

  # convert to ascii character
  def chr(self, num):
    return chr(self.int(num))

  # convert to integer or zero
  def int(self, num):
    try: n = int(num)
    except ValueError: n = 0
    return n

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
      output().errmsg("Cannot read from file", e)

  # write to local file
  def write(self, path, data, m='wb'):
    try:
      with open(path, mode=m) as f:
        f.write(data)
      f.close()
    except IOError as e:
      output().errmsg("Cannot write to file", e)

  # append to local file
  def append(self, path, data):
    self.write(path, data, 'ab+')

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
    elif self._sock: return self._sock.sendall(data)

  # receive data
  def recv(self, bytes):
    # receive data from device
    if self._file: data = os.read(self._file, bytes)
    # receive data from socket
    else: data = self._sock.recv(bytes)
    # output recv data when in debug mode
    if self.debug: output().recv(self.beautify(data), self.debug)
    return data

  # so-many-seconds-passed bool condition
  def past(self, seconds, watchdog):
    return int(watchdog * 100) % (seconds * 100) == 0

  # connection-feels-slow bool condition
  def slow(self, limit, watchdog):
    return not (self.quiet or self.debug) and watchdog > limit

  # receive data until a delimiter is reached
  def recv_until(self, delimiter, fb=True, crop=True, binary=False):
    data = ""
    sleep = 0.01 # pause in recv loop
    limit = 3.0 # max watchdog overrun
    wd = 0.0 # watchdog timeout counter
    r = re.compile(delimiter, re.DOTALL)
    s = re.compile("^\x04?\x0d?\x0a?" + delimiter, re.DOTALL)
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    while not r.search(data):
      data += self.recv(4096) # receive actual data
      if self.past(limit, wd): wd_old, bytes = wd, len(data)
      wd += sleep       # workaround for endless loop w/o socket timeout
      time.sleep(sleep) # happens on some devices - python socket error?
      # timeout plus it seems we are not receiving data anymore
      if wd > self._sock.gettimeout() and wd >= wd_old + limit:
        if len(data) == bytes:
          output().errmsg("Receiving data failed", "watchdog timeout")
          break
      # visual feedback on large/slow data transfers
      if self.slow(limit, wd) and self.past(0.1, wd) and len(data) > 0:
        output().chitchat(str(len(data)) + " bytes received\r", '')
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # clear current line from 'so-many bytes received' chit-chat
    if self.slow(limit, wd): output().chitchat(' ' * 24 + "\r", '')
    # warn if feedback expected but response empty (= delimiter only)
    # this also happens for data received out of order (e.g. brother)
    if fb and s.search(data): output().chitchat("No data received.")
    # remove delimiter itself from data
    if crop: data = r.sub('', data)
    # crop uel sequence at the beginning
    data = re.sub(r'(^' + const.UEL + ')', '', data)
    '''
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ delimiters -- note that carriage return (0d) is optional in ps/pjl      │
    ├─────────────────────────┬─────────────────────────┬─────────────────────┤
    │                         │           PJL           │      PostScript     │
    ├─────────────────────────┼─────────┬───────────────┼────────┬────────────┤
    │                         │ send    │ recv          │ send   │ recv       │
    ├─────────────────────────┼─────────┼───────────────┼────────┼────────────┤
    │ normal commands (ascii) │ 0d? 0a  │ 0d+ 0a 0c 04? │ 0d? 0a │ 0d? 0a 04? │
    ├─────────────────────────┼─────────┼───────────────┼────────┼────────────┤
    │ file transfers (binary) │ 0d? 0a  │ 0c            │ 0d? 0a │ -          │
    └─────────────────────────┴─────────┴───────────────┴────────┴────────────┘
    '''
    # crop end-of-transmission chars
    if self.mode == 'ps':
      data = re.sub(r'^\x04', '', data)
      if not binary: data = re.sub(r'\x0d?\x0a\x04?$', '', data)
    else: # pjl and pcl mode
      if binary: data = re.sub(r'\x0c$', '', data)
      else: data = re.sub(r'\x0d+\x0a\x0c\x04?$', '', data)
    # crop whitespaces/newline as feedback
    if not binary: data = data.strip()
    return data

  # beautify debug output
  def beautify(self, data):
    # remove sent/recv uel sequences
    data = re.sub(r'' + const.UEL, '', data)
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if self.mode == 'ps':
      # remove sent postscript header
      data = re.sub(r'' + re.escape(const.PS_HEADER), '', data)
      # remove sent postscript hack
      data = re.sub(r'' + re.escape(const.PS_IOHACK), '', data)
      # remove sent delimiter token
      data = re.sub(r'\(DELIMITER\d+\\n\) print flush\n', '', data)
      # remove recv delimiter token
      data = re.sub(r'DELIMITER\d+', '', data)
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    elif self.mode == 'pjl':
      # remove sent/recv delimiter token
      data = re.sub(r'@PJL ECHO\s+DELIMITER\d+', '', data)
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    elif self.mode == 'pcl':
      # remove sent delimiter token
      data = re.sub(r'\x1b\*s-\d+X', '', data)
      # remove recv delimiter token
      data = re.sub(r'PCL\x0d?\x0a?\x0c?ECHO -\d+', '', data)
      # replace sent escape sequences
      data = re.sub(r'(' + const.ESC + ')', '<Esc>', data)
      pass
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
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
  #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  PS_CATCH    = '%%\[ (.*)\]%%'
  PS_ERROR    = '%%\[ Error: (.*)\]%%'
  PS_FLUSH    = '%%\[ Flushing: (.*)\]%%'
  PS_PROMPT   = '>' # TBD: could be derived from PS command 'prompt'
  PS_HEADER   = '@PJL ENTER LANGUAGE = POSTSCRIPT\n%!\n'
  PS_GLOBAL   = 'true 0 startjob pop\n' # 'serverdict begin 0 exitserver'
  PS_SUPER    = '\n1183615869 internaldict /superexec get exec'
  PS_NOHOOK   = '/nohook true def\n'
  PS_IOHACK   = '/print {(%stdout) (w) file dup 3 2 roll writestring flushfile} def\n'\
                '/== {128 string cvs print (\\n) print} def\n'
  PCL_HEADER  = '@PJL ENTER LANGUAGE = PCL' + EOL + ESC
  #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  SUPERBLOCK  = '31337' # define super macro id to contain pclfs table
  BLOCKRANGE  = range(10000,20000) # use those macros for file content
  FILE_EXISTS = -1 # file size to be returned if file/dir size unknown
  NONEXISTENT = -2 # file size to be returned if a file does not exist
  #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  PS_VOL      = '' # no default volume in ps (read: any, write: first)
  PJL_VOL     = '0:' + SEP # default pjl volume name || path seperator

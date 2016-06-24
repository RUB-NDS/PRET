# -*- coding: utf-8 -*-

# python standard library
import re, os, random, datetime

# local pret classes
from printer import printer
from helper import log, output, item, const as c

class postscript(printer):
  # --------------------------------------------------------------------
  # send PostScript command to printer, optionally receive response
  def cmd(self, str_send, fb=True, crop=True, binary=False):
    str_recv = "" # response buffer
    token = c.DELIMITER + str(random.randrange(2**16)) # unique delimiter
    footer = "\n(\\n" + token + "\\n) echo\n" # additional line feed necessary
    # send command to printer device          # to get output on some printers
    try:
      cmd_send = c.UEL + c.PS_HEADER + str_send + c.EOL + footer
      # write to logfile
      log().write(self.logfile, str_send + os.linesep)
      # sent to printer
      self.conn.send(cmd_send)
      # use random token or error message as delimiter PS responses
      str_recv = self.conn.recv_until('(\\n)?' + token
               + "(.*)$|" + c.PS_FLUSH, fb, crop, binary)
      return self.ps_err(str_recv)

    # handle CTRL+C and exceptions
    except (KeyboardInterrupt, Exception) as e:
      self.reconnect(str(e))
      return ""

  # handle error messages from PostScript interpreter
  def ps_err(self, str_recv):
    msg = item(re.findall(c.PS_ERROR, str_recv))
    if msg:
      output().errmsg("PostScript Error", msg)
      str_recv = ""
    return str_recv

  # disable printing hardcopies of error messages
  def on_connect(self, mode):
    if mode == 'init': # only for the first connection attempt
      self.cmd('<< /DoPrintErrors false >> setsystemparams', False)

  # ------------------------[ shell ]-----------------------------------
  def do_shell(self, arg):
    "Open interactive PostScript shell."
    # politely request poor man's remote postscript shell
    output().info("Launching PostScript shell. Press CTRL+D to exit.")
    try:
      self.conn.send(c.UEL + c.PS_HEADER + "executive\n") # "false echo\n"
      while True:
        # use postscript prompt or error message as delimiter
        str_recv = self.conn.recv_until(c.PS_PROMPT + "$|"
                 + c.PS_FLUSH, False, False)
        # output raw response from printer
        output().raw(str_recv, "")
        # break on postscript error message
        if re.search(c.PS_FLUSH, str_recv): break
        # fetch user input and send it to postscript shell
        str_send = raw_input("")
        self.conn.send(str_send + "\n")
    # handle CTRL+C and exceptions
    except (EOFError, KeyboardInterrupt) as e:
      pass
    # reconnect with new conn object
    self.reconnect(None)

  # --------------------------------------------------------------------
  # check if remote volume exists
  def vol_exists(self, vol=''):
    if vol: vol = '%' + vol.strip('%') + '%'
    str_recv = self.cmd('/str 65535 string def (*) {dump} str devforall')
    vols = str_recv.splitlines()
    if vol: return vol in [v.strip('()') for v in vols] # return availability
    else: return vols                                   # return list of vols

  # check if remote directory exists
  def dir_exists(self, path, list=[]):
    # use filenameforall as status is not well supported by ps interpreters
    if not list: list = self.dirlist(path, False)
    for name in list: # use dirlist to check if directory
      if name.startswith(path + c.SEP): return True

  # check if remote file exists
  def file_exists(self, path, ls=False):
    str_recv = self.cmd('(' + path + ') status dup true ne '
             + '{} {pop dump dump dump dump} ifelse', False)
    meta = str_recv.splitlines()
    if len(meta) == 4:
      atime = self.lsdate(int(meta[0]))  # last referenced for reading
      mtime = self.lsdate(int(meta[1]))  # last referenced for writing
      size  = meta[2]                    # file size in bytes
      pages = meta[3]                    # pages (not useful)
      return (size, atime, mtime) if ls else int(size)
    else: return c.NONEXISTENT

  #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  # get complete list of files and directories on remote device
  def dirlist(self, path="", r=True):
    if r: path = self.rpath(path)
    path = path + self.get_sep(path)
    # ----------------------------------------------------------------
    timeout, timeout_old = self.timeout * 10, self.timeout
    self.do_timeout(timeout, True) # workaround: dynamic timeout
    if not self.fuzz: self.chitchat("Retrieving file list. "
    + "Temporarily increasing timeout to " + str(int(timeout)) + ".")
    # ----------------------------------------------------------------
    self.files = self.cmd('/str 65535 string def (' + path
               + '*) {echo (\\n) echo} str filenameforall')
    self.files = sorted(self.files.splitlines())
    # restore original timeout
    self.do_timeout(timeout_old, True)
    return self.files

  # ------------------------[ ls <path> ]-------------------------------
  def do_ls(self, arg):
    "List contents of remote directory:  ls <path>"
    path = self.rpath(arg) + self.get_sep(arg)
    list = self.dirlist(arg)
    cwdlist = []
    # create file list without subdirs
    for name in list:
      max = len(path.split(c.SEP))
      name = c.SEP.join(name.split(c.SEP)[:max])
      if not name in cwdlist: cwdlist.append(name)
    # get metadata for files in cwd
    for name in cwdlist:
      if name:
        meta = self.file_exists(name, True)
        if meta != c.NONEXISTENT: size, atime, mtime = meta
        # some ps interpreters don't support status or return true only
        else: size, atime, mtime = ('?', self.lsdate(0), self.lsdate(0))
        isdir = self.dir_exists(name, list) # check if file is directory
        output().psdir(isdir, size, atime, self.basename(name), mtime)

  # ------------------------[ find <path> ]-----------------------------
  def do_find(self, arg):
    "Recursively list contents of directory:  find <path>"
    for name in self.dirlist(arg):
      output().raw('.' + c.SEP + name)

  # ------------------------[ mirror <path> ]---------------------------
  def do_mirror(self, arg):
    "Mirror remote filesystem to local directory:  mirror <remote path>"
    for name in self.dirlist(arg):
      self.mirror(name, True)

  # ====================================================================

  # ------------------------[ get <file> ]------------------------------
  def get(self, path, size=None):
    if not size:
      size = self.file_exists(path)
    if size != c.NONEXISTENT:
      '''
      # flavour No.1: read whole file into string (max. file size: 65535 bytes)
      return self.cmd('/buffer 65535 string def\n'
                       + '/infile (' + path + ') (r) file def\n'
                       + 'infile buffer readstring\n'
                       + '(%stdout) (w) file buffer writestring\n'
                       + 'flush', True, True, True)
      # flavour No.2: read file one line at a time (max. line size: 65535 bytes)
      return self.cmd('/buffer 65535 string def\n'
                       + '/infile (' + path + ') (r) file def\n'
                       + '{infile buffer readline {=}\n'
                       + '{infile closefile exit} ifelse\n'
                       + '} loop', True, True, True)
      '''
      # flavour No.3: read file one byte at a time
      str_recv = self.cmd('/byte (X) def\n'
                     + '/infile (' + path + ') (r) file def\n'
                     + '{infile read {byte exch 0 exch put\n'
                     + '(%stdout) (w) file byte writestring}\n'
                     + '{infile closefile exit} ifelse\n'
                     + '} loop', True, True, True)
      return (size, str_recv)
    else:
      print("File not found.")
      return c.NONEXISTENT

  # ------------------------[ put <local file> ]------------------------
  def put(self, path, data, mode='w+'):
      # convert to PostScript-compatibe octal notation
      data = ''.join(['\\{:03o}'.format(ord(char)) for char in data])
      self.cmd('/outfile (' + path + ') (' + mode + ') file def\n'
              + 'outfile (' + data + ') writestring\n'
              + 'outfile closefile\n')

  # ------------------------[ append <file> <string> ]------------------
  def append(self, path, data):
    self.put(path, data, 'a+')

  # ------------------------[ delete <file> ]---------------------------
  def delete(self, arg):
    path = self.rpath(arg)
    self.cmd('(' + path + ') deletefile')

  # ------------------------[ rename <old> <new> ]----------------------
  def do_rename(self, arg):
    arg = re.split("\s+", arg, 1)
    if len(arg) > 1:
      old = self.rpath(arg[0])
      new = self.rpath(arg[1])
      self.cmd('(' + old + ') (' + new + ') renamefile')
    else:
      self.onecmd("help rename")

  # define alias but do not show alias in help
  do_mv = do_rename
  def help_rename(self):
    print("Rename remote file:  rename <old> <new>")

  # ====================================================================

  # ------------------------[ id ]--------------------------------------
  def do_id(self, *arg):
    "Show device information."
    output().info(self.cmd('product echo'))

  # ------------------------[ df ]--------------------------------------
  def do_df(self, arg):
    "Show volume information."
    output().df(('VOLUME', 'TOTAL SIZE', 'FREE SPACE', 'PRIORITY',
    'REMOVABLE', 'MOUNTED', 'HASNAMES', 'WRITEABLE', 'SEARCHABLE'))
    for vol in self.vol_exists():
      str_send = vol + ' devstatus dup true eq {pop ' + 'dump ' * 8 + '} if'
      lst_recv = self.cmd(str_send).splitlines()
      values = (vol,) + tuple(lst_recv if len(lst_recv) == 8 else ['-'] * 8)
      output().df(values)

  # ------------------------[ free ]------------------------------------
  def do_free(self, arg):
    "Show available memory or disk space."
    str_recv = self.cmd('statusdict begin\n'
                      + '  diskonline dup true {diskstatus dump dump} if\n'
                      + 'end')
    try: (free, total) = str_recv.splitlines()
    except: return output().info("Not available")
    if free.isdigit() and total.isdigit():
      msg = ("TOTAL SIZE", "FREE SPACE", os.linesep, total, free)
      output().info("%-14s %s%s%-14s %-10s" % msg)

  # ------------------------[ devices ]---------------------------------
  def do_devices(self, arg):
    "Show available I/O devices."
    str_send = '/str 65535 string def (*) {dump} str /IODevice resourceforall'
    for dev in self.cmd(str_send).splitlines():
      output().info(dev)
      output().raw(self.cmd(dev + ' currentdevparams {exch 128 string\n'
                    + 'cvs print (: ) print dump} forall') + os.linesep)

  # ------------------------[ uptime ]----------------------------------
  def do_uptime(self, arg):
    "Show system uptime (might be random)."
    str_recv = self.cmd('realtime dump')
    try: output().info(str(datetime.timedelta(seconds=int(str_recv) / 1000)))
    except ValueError: output().info("Not available")

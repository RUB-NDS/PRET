# -*- coding: utf-8 -*-

# python standard library
import re, os, string, random, datetime

# local pret classes
from printer import printer
from helper import log, output, item, const as c

class postscript(printer):
  # --------------------------------------------------------------------
  # send PostScript command to printer, optionally receive response
  def cmd(self, str_send, fb=True, crop=True, binary=False):
    str_recv = "" # response buffer
    token = c.DELIMITER + str(random.randrange(2**16)) # unique delimiter
    iohack = c.PS_IOHACK if self.iohack else ''   # optionally include output hack
    footer = '\n(' + token + '\\n) print flush\n' # additional line feed necessary
    # send command to printer device              # to get output on some printers
    try:
      cmd_send = c.UEL + c.PS_HEADER + iohack + str_send + c.EOL + footer
      # write to logfile
      log().write(self.logfile, str_send + os.linesep)
      # sent to printer
      self.conn.send(cmd_send)
      # use random token or error message as delimiter PS responses
      str_recv = self.conn.recv_until(token + ".*$"
               + "|" + c.PS_FLUSH, fb, crop, binary)
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
      str_send = '<< /DoPrintErrors false >> setsystemparams '\
               + '(f1) = (f2) ==' # = original, == overwritten
      str_recv = self.cmd(str_send)
      # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
      # handle devices that do not support ps output via 'print' or '=='
      if 'f1' in str_recv: self.iohack = False # all fine, no hack needed
      elif 'f2' in str_recv: # hack required to get output (e.g. Brother)
        output().errmsg('Crippled feedback', '%stdout hack enabled')
      else: # busy or not a PS printer or a silent one (e.g. Dell 3110cn)
        output().errmsg('No feedback', 'Printer busy, non-ps or silent')

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
    str_recv = self.cmd('/str 65535 string def (*)'
             + '{print (\\n) print} str devforall')
    vols = str_recv.splitlines()
    if vol: return vol in vols # return availability
    else: return vols # return list of existing vols

  # check if remote directory exists
  def dir_exists(self, path, list=[]):
    path = self.escape(path)
    if self.fuzz and not list: # use status instead of filenameforall
      return (self.file_exists(path) != c.NONEXISTENT)
    # use filenameforall as some ps interpreters do not support status
    if not list: list = self.dirlist(path, False)
    for name in list: # use dirlist to check if directory
      if re.search("^(%.*%)?" + path + c.SEP, name): return True

  # check if remote file exists
  def file_exists(self, path, ls=False):
    str_recv = self.cmd('(' + path + ') status dup true ne '
             + '{} {pop == == == ==} ifelse', False)
    meta = str_recv.splitlines()
    # standard conform ps interpreters respond with file size + times
    if len(meta) == 4:
      atime = self.lsdate(int(meta[0]))  # last referenced for reading
      mtime = self.lsdate(int(meta[1]))  # last referenced for writing
      size  = meta[2]                    # bytes (file/directory size)
      pages = meta[3]                    # pages (ain't really useful)
      return (size, atime, mtime) if ls else int(size)
    # broken interpreters return true only; can also mean: directory
    elif item(meta) == 'true': return c.FILE_EXISTS
    else: return c.NONEXISTENT

  # escape postscript pathname
  def escape(self, path):
    return path.replace('\\', '\\\\').replace('(', '\(').replace(')', '\)')

  #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  # get complete list of files and directories on remote device
  def dirlist(self, path="", r=True):
    if r: path = self.rpath(path)
    path = self.escape(path + self.get_sep(path))
    # ------------------------------------------------------------------
    timeout, timeout_old = self.timeout * 10, self.timeout
    self.do_timeout(timeout, True) # workaround: dynamic timeout
    if not self.fuzz: self.chitchat("Retrieving file list. "
    + "Temporarily increasing timeout to " + str(int(timeout)) + ".")
    # ------------------------------------------------------------------
    vol = "" if self.vol else "%*%" # search any volume if none specified
    # also lists 'hidden' .dotfiles; special treatment for brother devices
    str_recv = self.find(vol + path + "**") or self.find(vol + path + "*")
    list = {name for name in str_recv.splitlines()}
    self.do_timeout(timeout_old, True)
    return sorted(list)

  def find(self, path):
    str_send = '/str 65535 string def (' + path + ') '\
               '{print (\\n) print} str filenameforall'
    return self.cmd(str_send, False)

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
      # add new and non-empty filenames to list
      if not name in cwdlist and re.sub("^(%.*%)", '', name):
        cwdlist.append(name)
    # get metadata for files in cwd
    for name in cwdlist:
      isdir = self.dir_exists(name, list) # check if file is directory
      metadata = self.file_exists(name, True) if not isdir else None
      if metadata == c.FILE_EXISTS or isdir: # create dummy metadata
        (size, atime, mtime) = ('-', self.lsdate(0), self.lsdate(0))
      elif metadata != c.NONEXISTENT: size, atime, mtime = metadata
      if metadata != c.NONEXISTENT: # we got real or dummy metadata
        output().psdir(isdir, size, atime, self.basename(name), mtime)
      else: output().errmsg("Crippled filename", 'Bad interpreter')

  # ------------------------[ find <path> ]-----------------------------
  def do_find(self, arg):
    "Recursively list contents of directory:  find <path>"
    for name in self.dirlist(arg):
      output().psfind(name)

  # ------------------------[ mirror <path> ]---------------------------
  def do_mirror(self, arg):
    "Mirror remote filesystem to local directory:  mirror <remote path>"
    for name in self.dirlist(arg):
      self.mirror(name, True)

  # ====================================================================

  # ------------------------[ mkdir <path> ]----------------------------
  def do_mkdir(self, arg):
    "Create remote directory:  mkdir <path>"
    if not arg:
      arg = raw_input("Directory: ")
    # writing to dir/file should automatically create dir/
    # .dirfile is not deleted as empty dirs are not listed
    self.put(self.rpath(arg) + c.SEP + '.dirfile', '')

  # ------------------------[ get <file> ]------------------------------
  def get(self, path, size=None):
    if not size:
      size = self.file_exists(path)
    if size != c.NONEXISTENT:
      # read file, one byte at a time
      str_recv = self.cmd('/byte (0) def\n'
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
              + 'outfile closefile\n', False)

  # ------------------------[ append <file> <string> ]------------------
  def append(self, path, data):
    self.put(path, data, 'a+')

  # ------------------------[ delete <file> ]---------------------------
  def delete(self, arg):
    path = self.rpath(arg)
    self.cmd('(' + path + ') deletefile', False)

  # ------------------------[ rename <old> <new> ]----------------------
  def do_rename(self, arg):
    arg = re.split("\s+", arg, 1)
    if len(arg) > 1:
      old = self.rpath(arg[0])
      new = self.rpath(arg[1])
      self.cmd('(' + old + ') (' + new + ') renamefile', False)
    else:
      self.onecmd("help rename")

  # define alias but do not show alias in help
  do_mv = do_rename
  def help_rename(self):
    print("Rename remote file:  rename <old> <new>")

  # ====================================================================

  # ------------------------[ reset ]-----------------------------------
  def do_reset(self, arg):
    "Reset PostScript parameters to factory defaults."
    self.cmd('<< /FactoryDefaults true >> setsystemparams', False)

  # ====================================================================

  # ------------------------[ id ]--------------------------------------
  def do_id(self, *arg):
    "Show device information."
    output().info(self.cmd('product print'))

  # ------------------------[ version ]---------------------------------
  def do_version(self, *arg):
    "Show PostScript interpreter version."
    str_send = \
      '(Version:  ) print version                              ==\n'\
      '(Level:    ) print languagelevel                        ==\n'\
      '(Revision: ) print revision                             ==\n'\
      '(Serial:   ) print serialnumber                         ==\n'\
      '(Built:    ) print currentsystemparams /BuildTime   get ==\n'\
      '(Printer:  ) print currentsystemparams /PrinterName get ==\n'\
      '(License:  ) print currentsystemparams /LicenseID   get =='
    output().info(self.cmd(str_send))

  # ------------------------[ df ]--------------------------------------
  def do_df(self, arg):
    "Show volume information."
    output().df(('VOLUME', 'TOTAL SIZE', 'FREE SPACE', 'PRIORITY',
    'REMOVABLE', 'MOUNTED', 'HASNAMES', 'WRITEABLE', 'SEARCHABLE'))
    for vol in self.vol_exists():
      str_send = '(' + vol + ') devstatus dup true eq {pop ' + '== ' * 8 + '} if'
      lst_recv = self.cmd(str_send).splitlines()
      values = (vol,) + tuple(lst_recv if len(lst_recv) == 8 else ['-'] * 8)
      output().df(values)

  # ------------------------[ free ]------------------------------------
  def do_free(self, arg):
    "Show available memory or disk space."
    output().raw("Disk status")
    str_recv = self.cmd('statusdict begin diskonline dup'
                        ' true {diskstatus == ==} if end')
    try:
      free, total = str_recv.splitlines()
      msg = ("TOTAL SIZE", "FREE SPACE", os.linesep, total, free)
      output().info("%-14s %s%s%-14s %-10s" % msg)
    except:
      output().info("Not available")
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    output().raw("Virtual memory")
    output().info(self.cmd('vmstatus\n'
                         + '(level:  ) print vmstatus == pop\n'
                         + '(used:   ) print == pop\n'
                         + '(max:    ) print == pop'))
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    output().raw("Font cache")
    output().info(self.cmd('cachestatus '
                         + '(bsize:  ) print cachestatus == pop\n'
                         + '(bmax:   ) print == pop\n'
                         + '(msize:  ) print == pop\n'
                         + '(mmax:   ) print == pop\n'
                         + '(csize:  ) print == pop\n'
                         + '(cmax:   ) print == pop\n'
                         + '(blimit: ) print == pop'))
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    output().raw("User cache")
    output().info(self.cmd('ucachestatus '
                         + '(bsize:  ) print ucachestatus == pop\n'
                         + '(bmax:   ) print == pop\n'
                         + '(rsize:  ) print == pop\n'
                         + '(rmax:   ) print == pop\n'
                         + '(blimit: ) print == pop'))

  # ------------------------[ devices ]---------------------------------
  def do_devices(self, arg):
    "Show available I/O devices."
    str_send = '/str 65535 string def (*) {print (\\n) print} str /IODevice resourceforall'
    for dev in self.cmd(str_send).splitlines():
      output().info(dev)
      output().raw(self.cmd('(' + dev + ') currentdevparams {exch 128 string '
                          + 'cvs print (: ) print ==} forall') + os.linesep)

  # ------------------------[ uptime ]----------------------------------
  def do_uptime(self, arg):
    "Show system uptime (might be random)."
    str_recv = self.cmd('realtime ==')
    try: output().info(str(datetime.timedelta(seconds=int(str_recv) / 1000)))
    except ValueError: output().info("Not available")

  # ------------------------[ format ]----------------------------------
  def do_format(self, arg):
    "Initialize printer's file system:  format <disk>"
    if not self.vol:
      output().info("Set volume first using 'chvol'")
    else:
      output().warning("Warning: Initializing the printer's file system will whipe-out all")
      output().warning("user data (e.g. stored jobs) on the volume. Press CTRL+C to abort.")
      if output().countdown("Initializing " + self.vol + " in...", 10, self):
        str_recv = self.cmd('statusdict begin (' + self.vol + ') () initializedisk end', False)

  # ------------------------[ known <operator> ]-------------------------
  def do_known(self, arg):
    "List supported PostScript operators:  known <operator>"
    if arg:
      functionlist = {'User-supplied Operators': arg.split()}
    else:
      functionlist = {
        '01. Operand Stack Manipulation Operators': ['pop', 'exch', 'dup', 'copy', 'index', 'roll', 'clear', 'count', 'mark', 'cleartomark', 'counttomark'],
        '02. Arithmetic and Math Operators': ['add', 'div', 'idiv', 'mod', 'mul', 'sub', 'abs', 'neg', 'ceiling', 'floor', 'round', 'truncate', 'sqrt', 'atan', 'cos', 'sin', 'exp', 'ln', 'log', 'rand', 'srand', 'rrand'],
        '03. Array Operators': ['array', 'length', 'get', 'put', 'getinterval', 'putinterval', 'astore', 'aload', 'forall'],
        '04. Packed Array Operators': ['packedarray', 'setpacking', 'currentpacking'],
        '05. Dictionary Operators': ['dict ', 'maxlength', 'begin', 'end', 'def', 'load', 'store', 'undef', 'known', 'where', 'currentdict', 'errordict', '$error', 'systemdict', 'userdict', 'globaldict', 'statusdict', 'countdictstack', 'dictstack', 'cleardictstack'],
        '06. String Operators': ['string', 'anchorsearch', 'search'],
        '07. Relational, Boolean, and Bitwise Operators': ['eq', 'ne', 'ge', 'gt', 'le', 'lt', 'and', 'or', 'xor', 'true', 'false', 'bitshift'],
        '08. Control Operators': ['exec', 'if', 'ifelse', 'for', 'repeat', 'loop', 'exit', 'stop', 'stopped', 'countexecstack', 'execstack', 'quit', 'start'],
        '09. Type, Attribute, and Conversion Operators': ['type', 'cvlit', 'cvx', 'xcheck', 'executeonly', 'noaccess', 'readonly', 'rcheck', 'wcheck', 'cvi', 'cvn', 'cvr', 'cvrs', 'cvs'],
        '10. File Operators': ['file', 'filter', 'closefile', 'read', 'write', 'readhexstring', 'writehexstring', 'readstring', 'writestring', 'readline', 'token', 'bytesavailable', 'flush', 'flushfile', 'resetfile', 'status', 'run', 'currentfile', 'deletefile', 'renamefile', 'filenameforall', 'setfileposition', 'fileposition', 'print', '=', '==', 'stack', 'pstack', 'printobject', 'writeobject', 'setobjectformat', 'currentobjectformat'],
        '11. Resource Operators': ['defineresource', 'undefineresource', 'findresource', 'findcolorrendering', 'resourcestatus', 'resourceforall'],
        '12. Virtual Memory Operators': ['save', 'restore', 'setglobal', 'currentglobal', 'gcheck', 'startjob', 'defineuserobject', 'execuserobject', 'undefineuserobject', 'UserObjects'],
        '13. Miscellaneous Operators': ['bind', 'null', 'version', 'realtime', 'usertime', 'languagelevel', 'product', 'revision', 'serialnumber', 'executive', 'echo', 'prompt'],
        '14. Device Setup and Output Operators': ['showpage', 'copypage', 'setpagedevice', 'currentpagedevice', 'nulldevice'],
        '15. Errors' : ['configurationerror', 'dictfull', 'dictstackoverflow', 'dictstackunderflow', 'execstackoverflow', 'handleerror', 'interrupt', 'invalidaccess', 'invalidexit', 'invalidfileaccess', 'invalidfont', 'invalidrestore', 'ioerror', 'limitcheck', 'nocurrentpoint', 'rangecheck', 'stackoverflow', 'stackunderflow', 'syntaxerror', 'timeout', 'typecheck', 'undefined', 'undefinedfilename', 'undefinedresource', 'undefinedresult', 'unmatchedmark', 'unregistered', 'VMerror'],
        '16. Proprietary Operators' : []} # TBD: get from firmare, ps.vm or via systemdict (or proprietary dict name) dumper
    # ask interpreter if functions are known
    for desc, funcs in sorted(functionlist.iteritems()):
      output().chitchat(desc)
      commands = ['(' + func  + ': ) print systemdict /'
               + func + ' known ==' for func in funcs]
      str_recv = self.cmd(c.EOL.join(commands), False)
      for line in str_recv.splitlines():
        output().green(line) if " true" in line else output().warning(line)

  # ====================================================================

  # ------------------------[ lock <passwd> ]---------------------------
  def do_lock(self, arg):
    "Lock changing of system parameters."
    if not arg:
      arg = raw_input("Enter password: ")
    self.cmd('<< /Password () '
             '/SystemParamsPassword (' + arg + ') ' # harmless settings
             '/StartJobPassword (' + arg + ') '     # alter initial VM!
             '>> setsystemparams', False)

  # ------------------------[ unlock <passwd> ]-------------------------
  def do_unlock(self, arg):
    "Unlock changing of system parameters."
    max = 2**20 # exhaustive key search max value
    if not arg: # ~140.000 tries/sec on lj4250, wtf?
      print("No password given, cracking.")
      # note that only numeric passwords can be cracked right now
      # according to the standard using 'reset' should also work:
      # *********************************************************
      # `if the system parameter password is forgotten, there is
      # still a way to reset it [...] by passing a dictionary to
      # setsystemparams in which FactoryDefaults is the only entry'
      # *********************************************************
      timeout, timeout_old = self.timeout * 100, self.timeout
      self.do_timeout(timeout, True) # workaround: dynamic timeout
      arg = self.cmd('/min 0 def /max ' + str(max) + ' def\n'
             'statusdict begin { min 1 max\n'
             '  {dup checkpassword {== flush stop} {pop} ifelse} for\n'
             '} stopped pop')
      # restore original timeout
      self.do_timeout(timeout_old, True)
      if arg: output().raw("Found password: " + arg)
      else: return output().warning("Cannot unlock")
    # finally unlock device with password
    self.cmd('<< /Password (' + arg + ') '
             '/SystemParamsPassword () ' # mostly harmless settings
             '/StartJobPassword () '     # administration functions
             '>> setsystemparams', False)

# -*- coding: utf-8 -*-

# python standard library
import re, os, string, random, datetime, json, collections

# local pret classes
from printer import printer
from helper import log, output, file, item, const as c

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
      ### cmd_send = c.UEL + c.PS_HEADER + iohack + str_send + c.EOL + footer
      cmd_send = c.UEL + c.PS_HEADER + iohack + str_send + footer
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
    self.error = None
    msg = item(re.findall(c.PS_ERROR, str_recv))
    if msg: # real postscript command errors
      output().errmsg("PostScript Error", msg.strip())
      self.error = msg
      str_recv = ""
    else: # printer errors or status messages
      msg = item(re.findall(c.PS_CATCH, str_recv))
      if msg:
        self.chitchat("Status Message: '" + msg.strip() + "'")
        str_recv = re.sub(r'' + c.PS_CATCH + '\r?\n', '', str_recv)
    return str_recv

  # disable printing hard copies of error messages
  def on_connect(self, mode):
    if mode == 'init': # only for the first connection attempt
      str_send = '<< /DoPrintErrors false >> setsystemparams '\
               + '(f1) = (f2) ==' # = original, == overwritten
      str_recv = self.cmd(str_send)
      #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
      # handle devices that do not support ps output via 'print' or '=='
      if 'f1' in str_recv or self.error: self.iohack = False # all fine
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
    vols = str_recv.splitlines() + ['%*%']
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
    str_recv = self.cmd('(' + path + ') status dup '
             + '{pop == == == ==} if', False)
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
    timeout, timeout_old = self.timeout * 2, self.timeout
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
    str_send = '/str 256 string def (' + path + ') '\
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
    "Mirror remote file system to local directory:  mirror <remote path>"
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
    if self.iohack: # brother devices without any writeable volumes
      output().warning("Writing might cause this device to crash")
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
      str_send = '(' + vol + ') devstatus dup {pop ' + '== ' * 8 + '} if'
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
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    output().raw("Virtual memory")
    output().info(self.cmd('vmstatus\n'
                         + '(level:  ) print vmstatus == pop\n'
                         + '(used:   ) print == pop\n'
                         + '(max:    ) print == pop'))
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    output().raw("Font cache")
    output().info(self.cmd('cachestatus '
                         + '(bsize:  ) print cachestatus == pop\n'
                         + '(bmax:   ) print == pop\n'
                         + '(msize:  ) print == pop\n'
                         + '(mmax:   ) print == pop\n'
                         + '(csize:  ) print == pop\n'
                         + '(cmax:   ) print == pop\n'
                         + '(blimit: ) print == pop'))
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
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

  # ------------------------[ date ]------------------------------------
  def do_date(self, arg):
    "Show printer's system date and time."
    str_send = '(%Calendar%) /IODevice resourcestatus\n'\
               '{(%Calendar%) currentdevparams /DateTime get print}\n'\
               '{(Not available) print} ifelse'
    str_recv = self.cmd(str_send)
    output().info(str_recv)

  # ====================================================================

  # ------------------------[ lock <passwd> ]---------------------------
  def do_lock(self, arg):
    "Set startjob and system parameters password."
    if not arg:
      arg = raw_input("Enter password: ")
    self.cmd('<< /Password () '
             '/SystemParamsPassword (' + arg + ') ' # harmless settings
             '/StartJobPassword (' + arg + ') '     # alter initial VM!
             '>> setsystemparams', False)

  # ------------------------[ unlock <passwd> ]-------------------------
  def do_unlock(self, arg):
    "Unset startjob and system parameters password."
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
             '/StartJobPassword () '     # permanent changes in VM
             '>> setsystemparams', False)

  # ------------------------[ restart ]---------------------------------
  def do_restart(self, arg):
    "Restart PostScript interpreter."
    output().chitchat("Restarting PostScript interpreter.")
    # reset VM, might delete downloaded files and/or restart printer
    self.cmd('serverdict begin 0 exitserver systemdict /quit get exec')

  # ------------------------[ reset ]-----------------------------------
  def do_reset(self, arg):
    "Reset PostScript settings to factory defaults."
    # reset system parameters -- only works if printer is turned off
    ''' »A flag that, if set to true immediately before the printer is turned
    off, causes all nonvolatile parameters to revert to their factory default
    values at the next power-on. The set of nonvolatile parameters is product
    dependent. In most products, 'PageCount' cannot be reset. If the job that
    sets FactoryDefaults to true is not the last job executed straight before
    power-off, the request is ignored; this reduces the chance that malicious
    jobs will attempt to perform this operation.« '''
    self.cmd('<< /FactoryDefaults true >> setsystemparams')
    output().raw("Printer must be turned off immediately for changes to take effect.")

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

  # ------------------------[ disable ]---------------------------------
  def do_disable(self, arg):
    "Disable printing functionality."
    self.disable = not self.disable
    str_disable = "Disabling" if self.disable else "Enabling"
    str_send = 'serverdict begin 0 exitserver\n'
    str_send += '/showpage {} def' if self.disable\
                else "currentdict /showpage undef"
    output().chitchat(str_disable + " printing functionality")
    self.cmd(str_send)

  # ------------------------[ destroy ]---------------------------------
  def do_destroy(self, arg):
    "Cause physical damage to printer's NVRAM."
    output().warning("Warning: This command tries to cause physical damage to the")
    output().warning("printer NVRAM. Use at your own risk. Press CTRL+C to abort.")
    if output().countdown("Starting NVRAM write cycle loop in...", 10, self):
   #   for n in range(0, 100000):
   #     self.cmd('<< /Password (' + str(n) + ')\n'
   #              '   /SystemParamsPassword (' + str(n+1) + ')\n'
   #              '   /StartJobPassword     (' + str(n+1) + ')\n'
   #              '>> setsystemparams')
      # unfortunatelly we cannot set passwords in a postscript loop
      # itself as it seems the password is only set by the device when the postscript
      # job is finished

   # self.cmd('serverdict begin 0 exitserver\n'
      for n in range(1, 100000):
        self.cmd('/counter 0 def\n'
                 '{ << /Password counter 16 string cvs\n'
                 '     /SystemParamsPassword counter 1 add 16 string cvs\n'
                 '     /StartJobPassword     counter 1 add 16 string cvs\n'
                 '  >> setsystemparams\n'
                 '  /counter counter 1 add def\n'
                 '  counter ==\n'
                 '  counter 1000 eq {exit} if\n'
                 '} loop\n'
                 '<< /Password counter 16 string cvs\n'
                 '   /SystemParamsPassword (0)\n'
                 '   /StartJobPassword     (0)\n'
                 '>> setsystemparams')
        self.chitchat("\rNVRAM write cycles: " + str(n*1000), '')
    print # echo newline if we get this far

  # ------------------------[ hang ]------------------------------------
  def do_hang(self, arg):
    "Execute PostScript infinite loop."
    output().warning("Warning: This command causes an infinite loop rendering the")
    output().warning("device useless until manual restart. Press CTRL+C to abort.")
    if output().countdown("Executing PostScript infinite loop in...", 10, self):
      self.cmd('{} loop', False)

  # ====================================================================

  # ------------------------[ overlay <file.eps> ]----------------------
  def do_overlay(self, arg):
    "Put overlay eps file on all hard copies:  overlay <file.eps>"
    if not arg:
      arg = raw_input('File: ')
    data = file().read(arg)
    if data: self.overlay(data)

  # define alias
  complete_overlay = printer.complete_lfiles # files or directories

  def overlay(self, data):
    str_send = 'serverdict begin 0 exitserver\n'\
               'currentdict /showpage_real known false eq\n'\
               '{/showpage_real systemdict /showpage get def} if\n'\
               '/showpage {save /showpage {} bind def\n'\
               + data + '\nrestore showpage_real} def'
    self.cmd(str_send)

  # ------------------------[ cross <text> <font> ]---------------------
  def do_cross(self, arg):
    arg = re.split("\s+", arg, 1)
    if len(arg) > 1 and arg[0] in self.options_cross:
      font, text = arg
      text = text.strip('"')
      data = file().read(self.fontdir + font + ".pfa") or ""
      data += '\n/' + font + ' findfont 50 scalefont setfont\n'\
              '80 185 translate 52.6 rotate 1.1 1 scale 275 -67 moveto\n'\
              '(' + text  + ') dup stringwidth pop 2 div neg 0 rmoveto show'
      self.overlay(data)
    else:
      self.onecmd("help cross")

  def help_cross(self):
    print("Put printer graffiti on all hard copies:  cross <font> <text>")
    print("Read the docs on how to install custom fonts. Available fonts:")
    for font in sorted(self.options_cross): print("• " + font)

  fontdir = os.path.dirname(os.path.realpath(__file__))\
          + os.path.sep + 'fonts' + os.path.sep
  options_cross = [os.path.splitext(font)[0] for font in (os.listdir(fontdir)
                  if os.path.exists(fontdir) else []) if font.endswith('.pfa')]

  def complete_cross(self, text, line, begidx, endidx):
    return [cat for cat in self.options_cross if cat.startswith(text)]

  # ------------------------[ replace <old> <new> ]---------------------
  def do_replace(self, arg):
    "Replace string in documents to be printed:  replace <old> <new>"
    arg = re.split("\s+", arg, 1)
    if len(arg) > 1:
      oldstr, newstr = self.escape(arg[0]), self.escape(arg[1])
      self.cmd('serverdict begin 0 exitserver\n'
               '/strcat {exch dup length 2 index length add string dup\n'
               'dup 4 2 roll copy length 4 -1 roll putinterval} def\n'
               '/replace {exch pop (' + newstr + ') exch 3 1 roll exch strcat strcat} def\n'
               '/findall {{(' + oldstr + ') search {replace}{exit} ifelse} loop} def\n'
               '/show       {      findall       systemdict /show       get exec} def\n'
               '/ashow      {      findall       systemdict /ashow      get exec} def\n'
               '/widthshow  {      findall       systemdict /widthshow  get exec} def\n'
               '/awidthshow {      findall       systemdict /awidthshow get exec} def\n'
               '/cshow      {      findall       systemdict /cshow      get exec} def\n'
               '/kshow      {      findall       systemdict /kshow      get exec} def\n'
               '/xshow      { exch findall exch  systemdict /xshow      get exec} def\n'
               '/xyshow     { exch findall exch  systemdict /xyshow     get exec} def\n'
               '/yshow      { exch findall exch  systemdict /yshow      get exec} def\n')
    else:
      self.onecmd("help replace")

  # ------------------------[ capture ]---------------------------------
  ######################################################################
  #################### BACKUP OF WORKING VERSION TO ####################
  #################### CAPTURE JOBS ON FILE SYSTEM. ####################
  ######################################################################
  # def do_capture(self, arg):
  #   "Capture jobs to be printed on this device."
  #   hook = 'currentfile' # must be first operator in documents to be printed
  #   data = '  false echo % turn echo off as it slows down interpreters\n'\
  #          '  /strcat {exch dup length 2 index length add string dup\n'\
  #          '  dup 4 2 roll copy length 4 -1 roll putinterval} def\n'\
  #          '  /rndname [(job_) rand 16 string cvs strcat (.ps) strcat] def\n'\
  #          '  /capture {dup rndname 0 get (a+) file dup 3 2 roll writestring} def\n'\
  #          '  /execute {cvx exec} def\n'\
  #          '  {\n'\
  #          '    currentdict (firstrun) known not\n'\
  #          '    {(%!\\n' + hook + ' ) capture execute /firstrun 0 def} if\n'\
  #          '    (%lineedit) (r) file dup\n'\
  #          '    bytesavailable string readstring pop capture execute\n'\
  #          '  } loop'
  #   # hook our code into very first postscript operator
  #   self.cmd('serverdict begin 0 exitserver\n'
  #            '/' + hook + ' {\n'+ data + '\n} def')
  #   self.chitchat("Future print jobs will be captured on file system.")

  # ------------------------[ capture <operation> ]---------------------

  # BUGS: 
  # - ES KÖNNEN MOMENTAN MAX 60.000 ZEILEN JOBS GEPACTURED / RECEIVED WERDEN
  # - AUCH GIBT ES SCHNELL EINEN VMERROR WENN ARRAYS ALS ZU GROSS DEFINIERT
  # - lineedit vs. statementedit vs. stdin
  # - jobs are not executed/printed :)
  # - currentfile im moment darf nur einmal vorkommen, sonst erneut exitserver
  # - der zufall ist noch schlecht

  def do_capture(self, arg):
    "Capture further jobs to be printed on this device."
    # hooks must be the first operators in documents to be printed
    hook = ['currentfile', 'serverdict begin 0 exitserver'] # hook for exitserver
    hack = ['filter', 'currentfile /ASCII85Decode filter'] # hook for capture loop
    # record future print jobs
    if arg.startswith('start'):
      data = '  /strcat {exch dup length 2 index length add string dup\n'\
             '  dup 4 2 roll copy length 4 -1 roll putinterval} def\n'\
             '  /rndname (job_) rand 16 string cvs strcat (.ps) strcat def\n'\
             '  %------------------------------------------------------------------\n'\
             '  false echo                                % no interpreter slowdown\n'\
             '  /newjob true def                          % make sure to set new job\n'\
             '  currentdict /'+hook[0]+' undef            % reset hooked operator\n'\
             '  /max 40000 def                            % maximum dict/array size\n'\
             '  /slots max array def                      % (re-)define slots array\n'\
             '  /counter 2 dict def                       % slot and line counter\n'\
             '  counter (slot) 0 put                      % initialize slot counter\n'\
             '  counter (line) 0 put                      % initialize line counter\n'\
             '  (capturedict) where {pop}                 % print jobs are saved here\n'\
             '  {/capturedict max dict def} ifelse\n'\
             '  capturedict rndname slots put             % assign slots to jobname\n'\
             '  /slotnum {counter (slot) get} def         % get current slot counter\n'\
             '  /linenum {counter (line) get} def         % get current line counter\n'\
             '  %------------------------------------------------------------------\n'\
             '  /capture {\n'\
             '    linenum 0 eq {                          % start of current slot\n'\
             '      /lines max array def                  % (re-)define lines array\n'\
             '      slots slotnum lines put               % assign lines to current slot\n'\
             '    } if\n'\
             '    dup lines exch linenum exch put         % add current line to lines\n'\
             '    counter (line) linenum 1 add put        % increment linecounter\n'\
             '    linenum max eq {                        % slotsize limit reached\n'\
             '      counter (slot) linenum 1 add put      % increment slotcounter\n'\
             '      counter (line) 0 put                  % reset line counter\n'\
             '    } if\n'\
             '  } def\n'\
             '  % - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -\n'\
             '  /eot {dup (\\004) anchorsearch {pop pop permanent}{pop} ifelse} def\n'\
             '  /execline {cvx exec} def\n'\
             '  %------------------------------------------------------------------\n'\
             '  { newjob {(%!\\n'+hack[1]+' ) capture\n'\
             '    pop /newjob false def} if (%lineedit) (r) file\n'\
             '    dup bytesavailable string readstring pop capture eot pop\n'\
             '  } loop' # 2x execline, 1x eot
      # hook our code into postscript operators
      self.cmd('serverdict begin 0 exitserver\n'
               '/permanent {/'+ hook[0]+' {'+hook[1]+'} def} def\n'\
               'permanent /'+hack[0]+' {\n'+data+'\n} def')
      output().raw("Future print jobs will be captured in memory")
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # show captured print jobs
    elif arg.startswith('list'):
      # now = output().info(str(datetime.timedelta(seconds=int(str_recv) / 1000)))
      # str_recv = self.cmd('realtime ==')
      # output().info("job    date        size      username    jobname    ")
      # output().info("────────────────────────────────────────────────────")
      str_send = '(capturedict) where {(Captured jobs:\n) print capturedict {exch ==}\n'\
                 'forall}{(No jobs captured) print} ifelse' # TBD: date or n days ago
      output().raw(self.cmd(str_send))
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # load captured print jobs
    elif arg.startswith('fetch'):
      joblist = self.cmd('(capturedict) where {capturedict {exch ==} forall} if').splitlines()
      for job in joblist:
        target, job = self.basename(self.target), self.basename(job)
        root = os.path.join('capture', target)
        lpath = os.path.join(root, job)
        self.makedirs(root)
        # download captured job
        output().raw("Receiving " + lpath)
        data = self.cmd('/str 65535 string def capturedict /' + job + ' get '
          '{dup null ne { {dup null ne {str cvs print} if} forall } if} forall')
        # remove UEL, normalize newlines 
        data = re.sub(r'(\s+' + c.UEL + '$)', '', data)
        data = os.linesep.join(data.splitlines())
        print(str(len(data)) + " bytes received.")
        # write to local file
        file().write(lpath, data)
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # end capturing print jobs
    elif arg.startswith('stop'):
      output().raw("Stopping job capture, deleting recorded jobs")
      # we could simply use the 'restart' command for this
      self.cmd('serverdict begin 0 exitserver\n'
               'currentdict /capturedict undef\n'
               'currentdict /' + hook[0] + ' undef\n'
               'currentdict /' + hack[0] + ' undef')
    else:
      self.help_capture()

  def help_capture(self):
    print("Print job operations:  jobs <operation>")
    print("  capture start   - Record future print jobs.")
    print("  capture stop    - End capturing print jobs.")
    print("  capture list    - Show captured print jobs.")
    print("  capture fetch   - Save captured print jobs.")
  # print("  capture print   - reprint saved print jobs.")

  options_capture = ('start', 'list', 'fetch', 'stop')
  def complete_capture(self, text, line, begidx, endidx):
    return [cat for cat in self.options_capture if cat.startswith(text)]

  # ------------------------[ hold ]------------------------------------
  def do_hold(self, arg):
    "Enable job retention."
    output().info(self.cmd('serverdict begin 0 exitserver\n'
               'currentpagedevice (CollateDetails) get (Hold) get 1 ne\n'
               '{/retention 1 def}{/retention 0 def} ifelse\n'
               '<< /Collate true /CollateDetails\n'
               '<< /Hold retention /Type 8 >> >> setpagedevice\n'
               '(Job retention ) print\n'
               'currentpagedevice (CollateDetails) get (Hold) get 1 ne\n'
               '{(disabled.) print}{(enabled.) print} ifelse'))
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    '''
    **************************** HP/KYOCERA ****************************
    << /Collate true /CollateDetails <<         /Type 8 /Hold 1 >> >> setpagedevice  % quick copy (HP)
    << /Collate true /CollateDetails <<         /Type 8 /Hold 2 >> >> setpagedevice  % stored job (HP)
    << /Collate true /CollateDetails << /Mode 0 /Type 8 /Hold 1 >> >> setpagedevice  % quick copy (Kyocera)
    << /Collate true /CollateDetails << /Mode 0 /Type 8 /Hold 2 >> >> setpagedevice  % stored job (Kyocera)
    << /Collate true /CollateDetails << /Mode 0                 >> >> setpagedevice  % permanent job storage (Kyocera)
    <<               /CollateDetails << /Hold 0 /Type 8         >> >> setpagedevice  % disable job retention (HP)

    **************************** CANON *********************************
    << /CNJobExecMode store >> setpagedevice
    << /CNJobExecMode hold  >> setpagedevice

    **************************** XEROX #1 ******************************
    userdict /XJXsetraster known { 1 XJXsetraster } if

    **************************** XEROX #2 ******************************
    userdict begin /xerox$holdjob 1 def end
    /EngExe /ProcSet resourcestatus
    {pop pop /EngExe /ProcSet findresource /HoldJob known
    {false /EngExe /ProcSet findresource /HoldJob get exec} if} if

    **************************** TOSHIBA *******************************
    /dscInfo where {
      pop
      dscInfo /For known {
        <</TSBPrivate 100 string dup 0 (DSSC PRINT USERLOGIN=)
          putinterval dup 21 dscInfo /For get putinterval
        >> setpagedevice
      } if
      dscInfo /Title known {
        <</TSBPrivate 100 string dup 0 (DSSC JOB NAME=)
          putinterval dup 14 dscInfo /Title get putinterval
        >> setpagedevice
      } if
    << /TSBPrivate (DSSC PRINT PRINTMODE=HOLD) >> setpagedevice
    }{
      << /TSBPrivate (DSSC PRINT USERLOGIN=CUPS User) >> setpagedevice
      << /TSBPrivate (DSSC JOB NAME=CUPS Document)    >> setpagedevice
      << /TSBPrivate (DSSC PRINT PRINTMODE=HOLD)      >> setpagedevice
    } ifelse"
  '''

  # ====================================================================

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
        '12. Virtual Memory Operators': ['save', 'restore', 'setglobal', 'currentglobal', 'gcheck', 'startjob', 'defineuserobject', 'execuserobject', 'undefineuserobject'],
        '13. Miscellaneous Operators': ['bind', 'null', 'version', 'realtime', 'usertime', 'languagelevel', 'product', 'revision', 'serialnumber', 'executive', 'echo', 'prompt'],
        '14. Device Setup and Output Operators': ['showpage', 'copypage', 'setpagedevice', 'currentpagedevice', 'nulldevice'],
        '15. Errors' : ['handleerror'],
        '16. Proprietary Operators' : []} # TBD: get from firmare, ps.vm or via systemdict (or proprietary dict name) dumper
    # ask interpreter if functions are known to systemdict
    for desc, funcs in sorted(functionlist.iteritems()):
      output().chitchat(desc)
      commands = ['(' + func  + ': ) print systemdict /'
               + func + ' known ==' for func in funcs]
      str_recv = self.cmd(c.EOL.join(commands), False)
      for line in str_recv.splitlines():
        output().green(line) if " true" in line else output().warning(line)

  # ------------------------[ search <key> ]----------------------------
  def do_search(self, arg):
    "Search all dictionaries by key:  search <key>"
    output().info(self.cmd('(' + arg + ') where {(' + arg + ') get ==} if'))

  # ------------------------[ dicts ]-----------------------------------
  def do_dicts(self, arg):
    "Return a list of dictionaries and their permissions."
    output().info("acl   len   max   dictionary")
    output().info("────────────────────────────")
    for dict in self.options_dump:
      str_recv = self.cmd('1183615869 ' + dict + '\n'
                          'dup rcheck {(r) print}{(-) print} ifelse\n'
                          'dup wcheck {(w) print}{(-) print} ifelse\n'
                          'dup xcheck {(x) print}{(-) print} ifelse\n'
                          '( ) print dup length 65500 string cvs print\n'
                          '( ) print maxlength  65500 string cvs print')
      if len(str_recv.split()) == 3:
        output().info("%-5s %-5s %-5s %s" % tuple(str_recv.split() + [dict]))

  # ------------------------[ dump <dict> ]-----------------------------
  def do_dump(self, arg, resource=False):
    "Dump all values of a dictionary:  dump <dict>"
    dump = self.dictdump(arg, resource)
    if dump: output().psdict(dump)

  def help_dump(self):
    print("Dump dictionary:  dump <dict>")
    print("If <dict> is empty, the whole dictionary stack is dumped.")
    print("Standard PostScript dictionaries:")
    for dict in self.options_dump: print("• " + dict)

  # undocumented ... what about proprietary dictionary names?
  options_dump = ('systemdict', 'statusdict', 'userdict', 'globaldict',
        'serverdict', 'errordict', 'internaldict', 'currentpagedevice',
        'currentuserparams', 'currentsystemparams')

  def complete_dump(self, text, line, begidx, endidx):
    return [cat for cat in self.options_dump if cat.startswith(text)]

  # define alias
  complete_browse = complete_dump

  def dictdump(self, dict, resource):
    superexec = False # TBD: experimental privilege escalation
    if not dict: # dump whole dictstack if optional dict parameter is empty
      dict = 'superdict'
      self.chitchat("No dictionary given - dumping everything (might take some time)")
    # recursively dump contents of a postscript dictionary and convert them to json
    str_send = '/superdict {<< (universe) countdictstack array dictstack >>} def\n' \
               '/strcat {exch dup length 2 index length add string dup\n'           \
               'dup 4 2 roll copy length 4 -1 roll putinterval} def\n'              \
               '/remove {exch pop () exch 3 1 roll exch strcat strcat} def\n'       \
               '/escape { {(")   search {remove}{exit} ifelse} loop \n'             \
               '          {(/)   search {remove}{exit} ifelse} loop \n'             \
               '          {(\\\) search {remove}{exit} ifelse} loop } def\n'        \
               '/clones 220 array def /counter 0 def % performance drawback\n'      \
               '/redundancy { /redundant false def\n'                               \
               '  clones {exch dup 3 1 roll eq {/redundant true def} if} forall\n'  \
               '  redundant not {\n'                                                \
               '  dup clones counter 3 2 roll put  % put item into clonedict\n'     \
               '  /counter counter 1 add def       % auto-increment counter\n'      \
               '  } if redundant} def              % return true or false\n'        \
               '/wd {redundancy {pop q (<redundant dict>) p q bc s}\n'              \
               '{bo n {t exch q 128 a q c dump n} forall bc bc s} ifelse } def\n'   \
               '/wa {q q bc s} def\n'                                               \
               '% /wa {ao n {t dump n} forall ac bc s} def\n'                       \
               '/n  {(\\n) print} def               % newline\n'                    \
               '/t  {(\\t) print} def               % tabulator\n'                  \
               '/bo {({)   print} def              % bracket open\n'                \
               '/bc {(})   print} def              % bracket close\n'               \
               '/ao {([)   print} def              % array open\n'                  \
               '/ac {(])   print} def              % array close\n'                 \
               '/q  {(")   print} def              % quote\n'                       \
               '/s  {(,)   print} def              % comma\n'                       \
               '/c  {(: )  print} def              % colon\n'                       \
               '/p  {                  print} def  % print string\n'                \
               '/a  {string cvs        print} def  % print any\n'                   \
               '/pe {escape            print} def  % print escaped string\n'        \
               '/ae {string cvs escape print} def  % print escaped any\n'           \
               '/perms { readable  {(r) p}{(-) p} ifelse\n'                         \
               '         writeable {(w) p}{(-) p} ifelse } def\n'                   \
               '/rwcheck { % readable/writeable check\n'                            \
               '  dup rcheck not {/readable  false def} if\n'                       \
               '  dup wcheck not {/writeable false def} if perms } def\n'           \
               '/dump {\n'                                                          \
               '  /readable true def /writeable true def\n'                         \
               '  dup type bo ("type": ) p q 16 a q s\n'                            \
               '  %%%% check permissions %%%\n'                                     \
               '  ( "perms": ) p q\n'                                               \
               '  dup type /stringtype eq {rwcheck} {\n'                            \
               '    dup type /dicttype eq {rwcheck} {\n'                            \
               '      dup type /arraytype eq {rwcheck} {\n'                         \
               '        dup type /packedarraytype eq {rwcheck} {\n'                 \
               '          dup type /filetype eq {rwcheck} {\n'                      \
               '            perms } % inherit perms from parent\n'                  \
               '          ifelse} ifelse} ifelse} ifelse} ifelse\n'                 \
               '  dup xcheck {(x) p}{(-) p} ifelse\n'                               \
               '  %%%% convert values to strings %%%\n'                             \
               '  q s ( "value": ) p\n'                                             \
               '  %%%% on invalidaccess %%%\n'                                      \
               '  readable false eq {pop q (<access denied>) p q bc s}{\n'          \
               '  dup type /integertype     eq {q  12        a q bc s}{\n'          \
               '  dup type /operatortype    eq {q 128       ae q bc s}{\n'          \
               '  dup type /stringtype      eq {q           pe q bc s}{\n'          \
               '  dup type /booleantype     eq {q   5        a q bc s}{\n'          \
               '  dup type /dicttype        eq {            wd       }{\n'          \
               '  dup type /arraytype       eq {            wa       }{\n'          \
               '  dup type /packedarraytype eq {            wa       }{\n'          \
               '  dup type /nametype        eq {q 128       ae q bc s}{\n'          \
               '  dup type /fonttype        eq {q  30       ae q bc s}{\n'          \
               '  dup type /nulltype        eq {q pop (null) p q bc s}{\n'          \
               '  dup type /realtype        eq {q  42        a q bc s}{\n'          \
               '  dup type /filetype        eq {q 100       ae q bc s}{\n'          \
               '  dup type /marktype        eq {q 128       ae q bc s}{\n'          \
               '  dup type /savetype        eq {q 128       ae q bc s}{\n'          \
               '  dup type /gstatetype      eq {q 128       ae q bc s}{\n'          \
               '  (<cannot handle>) p}\n'                                           \
               '  ifelse} ifelse} ifelse} ifelse} ifelse} ifelse} ifelse} ifelse}\n'\
               '  ifelse} ifelse} ifelse} ifelse} ifelse} ifelse} ifelse} ifelse}\n'\
               'def\n'
    if not resource: str_send += '(' + dict + ') where {'
    str_send += 'bo 1183615869 ' + dict + ' {exch q 128 a q c dump n} forall bc'
    if not resource: str_send += '}{(<nonexistent>) print} ifelse'
    str_recv = self.clean_json(self.cmd(str_send))
    if str_recv == '<nonexistent>':
      output().info("Dictionary not found")
    else: # convert ps dictionary to json
      return json.loads(str_recv, object_pairs_hook=collections.OrderedDict, strict=False)

  # bad practice
  def clean_json(self, string):
    string = re.sub(",[ \t\r\n]+}", "}", string)
    string = re.sub(",[ \t\r\n]+\]", "]", string)
    return unicode(string, errors='ignore')

  # ------------------------[ resource <category> [dump] ]--------------
  def do_resource(self, arg):
    arg = re.split("\s+", arg, 1)
    cat, dump = arg[0], len(arg) > 1
    self.populate_resource()
    if cat in self.options_resource:
      str_send = '(*) {128 string cvs print (\\n) print}'\
                 ' 128 string /' + cat + ' resourceforall'
      items = self.cmd(str_send).splitlines()
      for item in sorted(items):
        output().info(item)
        if dump: self.do_dump('/' + item + ' /' + cat + ' findresource', True)
    else:
      self.onecmd("help resource")

  def help_resource(self):
    self.populate_resource()
    print("List or dump PostScript resource:  resource <category> [dump]")
    print("Available resources on this device:")
    for res in sorted(self.options_resource): print("• " + res)

  options_resource = []
  def complete_resource(self, text, line, begidx, endidx):
    return [cat for cat in self.options_resource if cat.startswith(text)]

  # retrieve available resources
  def populate_resource(self):
    if not self.options_resource:
      str_send = '(*) {print (\\n) print} 128 string /Category resourceforall'
      self.options_resource = self.cmd(str_send).splitlines()

  # ------------------------[ set <key=value> ]-------------------------
  def do_set(self, arg):
    "Set key to value in topmost dictionary:  set <key=value>"
    arg = re.split("=", arg, 1)
    if len(arg) > 1:
      key, val = arg
      # make changes permanent
      str_send = 'serverdict begin 0 exitserver {\n'
      # flavor No.1: put (associate key with value in dict)
      str_send += '/' + key + ' where {/' + key + ' ' + val + ' put} if\n'
      # flavor No.2: store (replace topmost definition of key)
      str_send += '/' + key + ' ' + val + ' store\n'
      # flavor No.3: def (associate key and value in userdict)
      str_send += '/' + key + ' ' + val + ' def\n'
      # ignore invalid access
      str_send += '} 1183615869 internaldict /superexec get exec'
      self.cmd(str_send, False)
    else:
      self.onecmd("help set")

  # ------------------------[ config <setting> ]------------------------
  def do_config(self, arg):
    arg = re.split("\s+", arg, 1)
    (arg, val) = tuple(arg) if len(arg) > 1 else (arg[0], None)
    if arg in self.options_config.keys():
      key = self.options_config[arg]
      if arg == 'copies' and not val: return self.help_config()
      val = val or 'currentpagedevice (' + key + ') get not'
      output().info(self.cmd('serverdict begin 0 exitserver\n'
        '<< /' + key + ' ' + val + ' >> setpagedevice\n'
        '(' + key + ' ) print currentpagedevice (' + key + ') get\n'
        'dup type /integertype eq {(= ) print 8 string cvs print}\n'
        '{{(enabled)}{(disabled)} ifelse print} ifelse'))
    else:
      self.help_config()

  def help_config(self):
    print("Change printer settings:  config <setting>")
    print("  duplex        - Set duplex printing.")
    print("  copies #      - Set number of copies.")
    print("  economode     - Set economic mode.")
    print("  negative      - Set negative print.")
    print("  mirror        - Set mirror inversion.")

  options_config = {'duplex'   : 'Duplex',
                    'copies'   : 'NumCopies',
                    'economode': 'EconoMode',
                    'negative' : 'NegativePrint',
                    'mirror'   : 'MirrorPrint'}

  def complete_config(self, text, line, begidx, endidx):
    return [cat for cat in self.options_config if cat.startswith(text)]
























  def do_exitserver(self, arg):
    output().info(self.cmd('serverdict begin 0 exitserver\n'
      '/foobar {true ==} def'))



  def do_startjob(self, arg):
    output().info(self.cmd('true 0 startjob\n'
      '/foobar1 {true ==} def'))



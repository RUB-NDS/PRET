# -*- coding: utf-8 -*-

# python standard library
import re, os, sys, cmd, glob, errno, random, ntpath
import posixpath, hashlib, tempfile, subprocess

# local pret classes
from helper import log, output, conv, file, item, conn, const as c
from discovery import discovery
from fuzzer import fuzzer

class printer(cmd.Cmd, object):
  # cmd module config and customization
  intro = "Welcome to the pret shell. Type help or ? to list commands."
  doc_header = "Available commands (type help <topic>):"
  offline_str = "Not connected."
  undoc_header = None
  # do not change
  logfile = None
  debug = False
  status = False
  quiet = False
  fuzz = False
  conn = None
  mode = None
  error = None
  iohack = True
  timeout = 10
  target = ""
  vol = ""
  cwd = ""
  traversal = ""
  # can be changed
  editor = 'vim' # set to nano/edit/notepad/leafpad/whatever

  # --------------------------------------------------------------------
  def __init__(self, args):
    # init cmd module
    cmd.Cmd.__init__(self)
    self.debug = args.debug # debug mode
    self.quiet = args.quiet # quiet mode
    self.mode  = args.mode  # command mode
    # connect to device
    self.do_open(args.target, 'init')
    # log pjl/ps cmds to file
    if args.log:
      self.logfile = log().open(args.log)
      header = None
      if self.mode == 'ps': header = c.PS_HEADER
      if self.mode == 'pcl': header = c.PCL_HEADER
      if header: log().write(self.logfile, header + os.linesep)
    # run pret cmds from file
    if args.load:
      self.do_load(args.load)
    # input loop
    self.cmdloop()

  def set_defaults(self, newtarget):
    self.fuzz = False
    if newtarget:
      self.set_vol()
      self.set_traversal()
      self.error = None
    else:
      self.set_prompt()

  # --------------------------------------------------------------------
  # do noting on empty input
  def emptyline(self): pass

  # show message for unknown commands
  def default(self, line):
    if line and line[0] != "#": # interpret as comment
      output().chitchat("Unknown command: '" + line + "'")

  # suppress help message for undocumented commands
  def print_topics(self, header, cmds, cmdlen, maxcol):
    if header is not None:
      cmd.Cmd.print_topics(self, header, cmds, cmdlen, maxcol)

  # supress some chit-chat in quiet mode
  def chitchat(self, *args):
    if not self.quiet: output().chitchat(*args)

  # --------------------------------------------------------------------
  # code to be executed before command line is interpreted
  def precmd(self, line):
    # commands that can be run offline
    off_cmd = ['#', '?', 'help', 'exit', 'quit', 'EOF', 'timeout',
               'mode', 'load', 'loop', 'discover', 'open', 'debug']
    # remove whitepaces
    line = line.strip()
    if line and line.split()[0] not in off_cmd:
      # write non-empty lines to logfile
      log().comment(self.logfile, line)
      # only let "offline" functions pass if not connected
      if self.conn == None:
        print(self.offline_str)
        return os.linesep
    # finally return original command
    return line

  # --------------------------------------------------------------------
  # catch-all wrapper to guarantee continuation on unhandled exceptions
  def onecmd(self, line):
    try:
      cmd.Cmd.onecmd(self, line)
    except Exception as e:
      output().errmsg("Program Error", e)

  # ====================================================================

  # ------------------------[ exit ]------------------------------------
  def do_exit(self, *arg):
    # close logfile
    if self.logfile:
      log().close(self.logfile)
    sys.exit()

  # define alias but do not show alias in help
  do_quit = do_exit
  do_EOF  = do_exit
  def help_exit(self):
    print("Exit the interpreter.")

  # ------------------------[ debug ]-----------------------------------
  def do_debug(self, arg):
    "Enter debug mode. Use 'hex' for hexdump:  debug [hex]"
    self.debug = not self.debug
    # set hex mode (= ascii + hexdump)
    if arg == 'hex': self.debug = 'hex'
    if self.conn: self.conn.debug = self.debug
    print("Debug mode on" if self.debug else "Debug mode off")

  # ====================================================================

  # ------------------------[ load ]------------------------------------
  def do_load(self, arg):
    "Run commands from file:  load cmd.txt"
    if not arg:
      arg = raw_input("File: ")
    data = file().read(arg) or ""
    for cmd in data.splitlines():
      # simulate command prompt
      print(self.prompt + cmd)
      # execute command with premcd
      self.onecmd(self.precmd(cmd))

  # ------------------------[ loop <cmd> <arg1> <arg2> … ]--------------
  def do_loop(self, arg):
    "Run command for multiple arguments:  loop <cmd> <arg1> <arg2> …"
    args = re.split("\s+", arg)
    if len(args) > 1:
      cmd = args.pop(0)
      for arg in args:
        output().chitchat("Executing command: '" + cmd + " " + arg + "'")
        self.onecmd(cmd + " " + arg)
    else:
      self.onecmd("help loop")

  # ====================================================================

  # ------------------------[ discover ]--------------------------------
  def do_discover(self, arg):
    "Discover local printer devices via SNMP."
    discovery()

  # ------------------------[ open <target> ]---------------------------
  def do_open(self, arg, mode=""):
    "Connect to remote device:  open <target>"
    if not arg:
      arg = raw_input("Target: ")
    # open connection
    try:
      newtarget = (arg != self.target)
      self.target = arg # set new target
      self.conn = conn(self.mode, self.debug, self.quiet)
      self.conn.timeout(self.timeout)
      self.conn.open(arg)
      print("Connection to " + arg + " established")
      # hook method executed after successful connection
      self.on_connect(mode)
      # show some information about the device
      if not self.quiet and mode != 'reconnect':
        sys.stdout.write("Device:   ");
        self.do_id()
      print("")
      # set printer default values
      self.set_defaults(newtarget)
    except Exception as e:
      output().errmsg("Connection to " + arg + " failed", e)
      self.do_close()
      # exit if run from init function (command line)
      if mode == 'init':
        self.do_exit()

  # wrapper to send data
  def send(self, *args):
    if self.conn: self.conn.send(*args)

  # wrapper to recv data
  def recv(self, *args):
    return self.conn.recv_until(*args) if self.conn else ""

  # ------------------------[ close ]-----------------------------------
  def do_close(self, *arg):
    "Disconnect from device."
    if self.conn:
      self.conn.close()
      self.conn = None
    print("Connection closed.")
    self.set_prompt()

  # ------------------------[ timeout <seconds> ]-----------------------
  def do_timeout(self, arg, quiet=False):
    "Set connection timeout:  timeout <seconds>"
    try:
      if arg:
        if self.conn: self.conn.timeout(float(arg))
        self.timeout = float(arg)
      if not quiet:
        print("Device or socket timeout: " + str(self.timeout))
    except Exception as e:
      output().errmsg("Cannot set timeout", e)

  # send mode-specific command whith modified timeout
  def timeoutcmd(self, str_send, timeout, *stuff):
    timeout_old = self.timeout
    self.do_timeout(timeout, True)
    str_recv = self.cmd(str_send, *stuff)
    self.do_timeout(timeout_old, True)
    return str_recv

  # ------------------------[ reconnect ]-------------------------------
  def do_reconnect(self, *arg):
    self.do_close()
    self.do_open(self.target, 'reconnect')

  # re-open connection
  def reconnect(self, msg):
    # on incomplete command show error message
    if msg: output().errmsg("Command execution failed", msg)
    sys.stdout.write(os.linesep + "Forcing reconnect. ")
    # workaround to flush socket buffers
    self.do_close()
    self.do_open(self.target, 'reconnect')
    # on CTRL+C spawn a new shell
    if not msg: self.cmdloop(intro="")

  # --------------------------------------------------------------------
  # dummy functions to overwrite
  def on_connect(self, mode): pass
  def do_id(self, *arg): output().info("Unknown printer")

  # ====================================================================

  # ------------------------[ pwd ]-------------------------------------
  def do_pwd(self, arg):
    "Show working directory on remote device."
    path = ('' if self.vol else c.SEP) + self.rpath()
    output().raw(path)

  # ------------------------[ chvol <volume> ]--------------------------
  def do_chvol(self, arg):
    "Change remote volume:  chvol <volume>"
    if not arg:
      arg = raw_input("Volume: ")
    if arg and self.vol_exists(arg):
      if self.mode == 'ps':  self.set_vol('%' + arg.strip('%') + '%')
      if self.mode == 'pjl': self.set_vol(arg[0] + ':' + c.SEP)
      print("Volume changed to " + self.vol)
    else:
      print("Volume not available")

  # set volume
  def set_vol(self, vol=""):
    if not vol:
      # set default volumes
      if self.mode == 'ps' : vol = c.PS_VOL
      if self.mode == 'pjl': vol = c.PJL_VOL
    if self.vol != vol:
      # reset path traversal and cwd
      self.set_traversal()
      # set actual volume
      self.vol = vol

  # get volume
  def get_vol(self):
    vol = self.vol
    if vol and self.mode == 'ps' : vol = vol.strip('%')
    if vol and self.mode == 'pjl': vol = vol[0]
    return vol

  # ------------------------[ traversal <path> ]------------------------
  def do_traversal(self, arg):
    "Set path traversal:  traversal <path>"
    if not arg or self.dir_exists(self.tpath(arg)):
      self.set_traversal(arg)
      print("Path traversal " + ("" if arg else "un") + "set.")
    else:
      print("Cannot use this path traversal.")

  # set path traversal
  def set_traversal(self, traversal=''):
    self.traversal = traversal
    if not traversal: self.set_cwd()

  # ------------------------[ cd <path> ]-------------------------------
  def do_cd(self, arg):
    "Change remote working directory:  cd <path>"
    if not self.cpath(arg) or self.dir_exists(self.rpath(arg)):
      if re.match("^[\." + c.SEP + "]+$", self.cpath(arg)):
        output().raw("*** Congratulations, path traversal found ***")
        output().chitchat("Consider setting 'traversal' instead of 'cd'.")
      self.set_cwd(arg)
    else:
      print("Failed to change directory.")

  # set current working directory
  def set_cwd(self, cwd=''):
    self.cwd = self.cpath(cwd) if cwd else ""
    self.set_prompt()

  # set command prompt
  def set_prompt(self):
    target = self.target + ":" if self.conn else ""
    cwd = self.cwd if self.conn else ""
    self.prompt = target + c.SEP + cwd + "> "

  # get seperator
  def get_sep(self, path):
    # don't add seperator between ps volume and filename
    if self.mode == 'ps' and re.search("^%.*%$", path): return ''
    # add seperator if we have to deal with a directory
    return c.SEP if (path or self.cwd or self.traversal) else ''

  # --------------------------------------------------------------------
  # get path without traversal and cwd information
  def tpath(self, path):
    # remove leading seperators
    path = path.lstrip(c.SEP)
    return self.vol + self.normpath(path)

  # get path without volume and traversal information
  def cpath(self, path):
    # generate virtual path on remote device
    path = c.SEP.join((self.cwd, path))
    # remove leading seperators
    path = path.lstrip(c.SEP)
    return self.normpath(path)

  # get path without volume information
  def vpath(self, path):
    # generate virtual path on remote device
    path = c.SEP.join((self.traversal, self.cwd, path))
    # remove leading seperators
    path = path.lstrip(c.SEP)
    return self.normpath(path)

  # get path with volume information
  def rpath(self, path=""):
    # warn if path contains volume information
    if (path.startswith("%") or path.startswith('0:')) and not self.fuzz:
      output().warning("Do not refer to disks directly, use chvol.")
    # in fuzzing mode leave remote path as it is
    if self.fuzz: return path
    # prepend volume information to virtual path
    return self.vol + self.vpath(path)

  # get normalized pathname
  def normpath(self, path):
    path = posixpath.normpath(path)
    '''
    ┌───────────────────────────────────────────────────────┐
    │        problems when using posixpath.normpath         │
    ├───────────────────────────────────────────────────────┤
    │ [✗] breaks obscure traversal strategies like '.../..' │
    │ [✓] removes tailing seperators, we can deal with this │
    │ [✓] sets '.' for 'dir/..', refused by ps interpreters │
    └───────────────────────────────────────────────────────┘
    '''
    ### path = re.sub(r"(/)", "\\\\", path)      ### Epson/Samsung PJL
    ### path = re.sub(r"(/\.\.)", "/../.", path) ### HP path traversal
    return path if path != '.' else ''

  # --------------------------------------------------------------------
  # get filename, independent of path naming convention
  def basename(self, path):
    path = os.path.basename(posixpath.basename(ntpath.basename(path)))
    return path

  # ====================================================================

  # ------------------------[ get <file> ]------------------------------
  def do_get(self, arg, lpath="", r=True):
    "Receive file:  get <file>"
    if not arg:
      arg = raw_input("Remote file: ")
    if not lpath:
      lpath = self.basename(arg)
    path = self.rpath(arg) if r else arg
    str_recv = self.get(path)
    if str_recv != c.NONEXISTENT:
      rsize, data = str_recv
      lsize = len(data)
      # fix carriage return chars added by some devices
      if lsize != rsize and len(conv().nstrip(data)) == rsize:
        lsize, data = rsize, conv().nstrip(data)
      # write to local file
      file().write(lpath, data)
      if lsize == rsize:
        print(str(lsize) + " bytes received.")
      else:
        self.size_mismatch(rsize, lsize)

  def size_mismatch(self, size1, size2):
    size1, size2 = str(size1), str(size2)
    print("Size mismatch (should: " + size1 + ", is: " + size2 + ").")

  # ------------------------[ put <local file> ]------------------------
  def do_put(self, arg, rpath=""):
    "Send file:  put <local file>"
    if not arg:
      arg = raw_input("Local file: ")
    if not rpath:
      rpath = os.path.basename(arg)
    rpath = self.rpath(rpath)
    lpath = os.path.abspath(arg)
    # read from local file
    data = file().read(lpath)
    if data != None:
      self.put(rpath, data)
      lsize = len(data)
      rsize = self.file_exists(rpath)
      if rsize == lsize:
        print(str(rsize) + " bytes transferred.")
      elif rsize == c.NONEXISTENT:
        print("Permission denied.")
      else:
        self.size_mismatch(lsize, rsize)

  # ------------------------[ append <file> <string> ]------------------
  def do_append(self, arg):
    "Append to file:  append <file> <string>"
    arg = re.split("\s+", arg, 1)
    if len(arg) > 1:
      path, data = arg
      rpath = self.rpath(path)
      data = data + os.linesep
      self.append(rpath, data)
    else:
      self.onecmd("help append")

  # ------------------------[ touch <file> ]----------------------------
  def do_touch(self, arg):
    "Update file timestamps:  touch <file>"
    if not arg:
      arg = raw_input("Remote file: ")
    rpath = self.rpath(arg)
    self.append(rpath, '')

  # ------------------------[ delete <file> ]---------------------------
  def do_delete(self, arg):
    if not arg:
      arg = raw_input("File: ")
    self.delete(arg)

  # define alias but do not show alias in help
  do_rm = do_delete
  do_rmdir = do_delete
  def help_delete(self):
    print("Delete remote file:  delete <file>")

  # ------------------------[ cat <file> ]------------------------------
  def do_cat(self, arg):
    "Output remote file to stdout:  cat <file>"
    if not arg:
      arg = raw_input("Remote file: ")
    path = self.rpath(arg)
    str_recv = self.get(path)
    if str_recv != c.NONEXISTENT:
      rsize, data = str_recv
      output().raw(data.strip())

  # ------------------------[ edit <file> ]-----------------------------
  def do_edit(self, arg):
    # get name of temporary file
    t = tempfile.NamedTemporaryFile(delete=False)
    lpath = t.name; t.close
    # download to temporary file
    self.do_get(arg, lpath)
    # get md5sum for original file
    chksum1 = hashlib.md5(open(lpath,'rb').read()).hexdigest()
    try:
      subprocess.call([self.editor, lpath])
      # get md5sum for edited file
      chksum2 = hashlib.md5(open(lpath,'rb').read()).hexdigest()
      # upload file, if changed
      if chksum1 == chksum2: print("File not changed.")
      else: self.do_put(lpath, arg)
    except Exception as e:
      output().errmsg("Cannot edit file - Set self.editor", e)
    # delete temporary file
    os.remove(lpath)

  # define alias but do not show alias in help
  do_vim = do_edit
  def help_edit(self):
    print("Edit remote files with our favorite editor:  edit <file>")

  # ------------------------[ mirror <path> ]---------------------------
  def mirror(self, name, size):
    target, vol = self.basename(self.target), self.get_vol()
    root = os.path.abspath(os.path.join('mirror', target, vol))
    lpath = os.path.join(root, name)
    '''
    ┌───────────────────────────────────────────────────────────┐
    │                 mitigating path traversal                 │
    ├───────────────────────────────────────────────────────────┤
    │ creating a mirror can be a potential security risk if the │
    │ path contains traversal characters, environment variables │
    │ or other things we have not thought about; while the user │
    │ is in total control of the path (via 'cd' and 'traversal' │
    │ commands), she might accidentally overwrite her files...  │
    │                                                           │
    │ our strategy is to first replace trivial path traversal   │
    │ strings (while still beeing able to download the files)   │
    │ and simply give up on more sophisticated ones for now.    │
    └───────────────────────────────────────────────────────────┘
    '''
    # replace path traversal (poor man's version)
    lpath = re.sub(r'(\.)+' + c.SEP, '', lpath)
    # abort if we are still out of the mirror root
    if not os.path.realpath(lpath).startswith(root):
      output().errmsg("Not saving data out of allowed path",
              "I'm sorry Dave, I'm afraid I can't do that.")
    elif size: # download current file
      output().raw(self.vol + name + " -> " + lpath)
      self.makedirs(os.path.dirname(lpath))
      self.do_get(self.vol + name, lpath, False)
    else:      # create current directory
      self.chitchat("Traversing " + name)
      self.makedirs(lpath)

  # recursive directory creation
  def makedirs(self, path):
    try:
      os.makedirs(path)
    except OSError as e:
      if e.errno == errno.EEXIST and os.path.isdir(path): pass
      else: raise

  # --------------------------------------------------------------------
  # auto-complete dirlist for local fs
  def complete_lfiles(self, text, line, begidx, endidx):
    before_arg = line.rfind(" ", 0, begidx)
    if before_arg == -1:
      return # arg not found

    fixed = line[before_arg+1:begidx] # fixed portion of the arg
    arg = line[before_arg+1:endidx]
    pattern = arg + '*'

    completions = []
    for path in glob.glob(pattern):
      if path and os.path.isdir(path) and path[-1] != os.sep:
        path = path + os.sep
      completions.append(path.replace(fixed, "", 1))
    return completions

  # define alias
  complete_load  = complete_lfiles # files or directories
  complete_put   = complete_lfiles # files or directories
  complete_print = complete_lfiles # files or directories

  # ====================================================================

  # ------------------------[ fuzz <category> ]-------------------------
  def do_fuzz(self, arg):
    if arg in self.options_fuzz:
      # enable global fuzzing
      self.fuzz = True
      if arg == 'path': self.fuzz_path()
      if arg == 'write': self.fuzz_write()
      if arg == 'blind': self.fuzz_blind()
      self.chitchat("Fuzzing finished.")
      # disable global fuzzing
      self.fuzz = False
    else:
      self.help_fuzz()

  def fuzz_path(self):
    output().raw("Checking base pathes first.")
    # get a cup of coffee, fuzzing will take some time
    output().fuzzed('PATH', '', ('', 'EXISTS',  'DIRLIST'))
    output().hline()
    found = {} # pathes found
    # try base pathes first
    for path in self.vol_exists() + fuzzer().path:
      self.verify_path(path, found)
    output().raw("Checking filesystem hierarchy standard.")
    # try direct access to fhs dirs
    for path in fuzzer().fhs:
      self.verify_path(path)
    # try path traversal strategies
    if found:
      output().raw("Now checking traversal strategies.")
      output().fuzzed('PATH', '', ('', 'EXISTS',  'DIRLIST'))
      output().hline()
      # only check found volumes
      for vol in found:
        sep  = '' if vol[-1:] in ['', '/', '\\' ] else '/'
        sep2 = vol[-1:] if vol[-1:] in ['/', '\\'] else '/'
        # 1st level traversal
        for dir in fuzzer().dir:
          path = vol + sep + dir + sep2
          self.verify_path(path)
          # 2nd level traversal
          for dir2 in fuzzer().dir:
            path = vol + sep + dir + sep2 + dir2 + sep2
            self.verify_path(path)

  def fuzz_write(self):
    output().raw("Writing temporary files.")
    # get a cup of tea, fuzzing will take some time
    output().fuzzed('PATH', 'COMMAND', ('GET', 'EXISTS', 'DIRLIST'))
    output().hline()
    # test data to put/append
    data = "test"; data2 = "test2"
    # try write to disk strategies
    for vol in self.vol_exists() + fuzzer().write:
      sep = '' if vol[-1:] in ['', '/', '\\' ] else '/'
      name = "dat" + str(random.randrange(10000))
      # FSDOWNLOAD
      self.put(vol + sep + name, data)
      fsd_worked = self.verify_write(vol+sep, name, data, 'PUT')
      # FSAPPEND
      self.append(vol + sep + name, data2)
      data = (data + data2) if fsd_worked else data2
      self.verify_write(vol + sep, name, data, 'APPEND')
      # FSDELETE
      self.do_delete(vol + sep + name)
      output().hline()

  def fuzz_blind(self):
    output().raw("Blindly trying to read files.")
    # get a bottle of beer, fuzzing will take some time
    output().fuzzed('PATH', '', ('', 'GET', 'EXISTS'))
    output().hline()
    # try blind file access strategies (relative path)
    for path in fuzzer().rel:
      self.verify_blind(path, "")
    output().hline()
    # try blind file access strategies (absolute path)
    for vol in self.vol_exists() + fuzzer().blind:
      sep  = '' if vol[-1:] in ['', '/', '\\' ] else '/'
      sep2 = vol[-1:] if vol[-1:] in ['/', '\\'] else '/'
      # filenames to look for
      for file in fuzzer().abs:
        # set current delimiter
        if isinstance(file, list): file = sep2.join(file)
        path = vol + sep
        self.verify_blind(path, file)
        # vol name out of range error
        if self.error == '30054':
          output().raw("Volume nonexistent, skipping.")
          break
        # no directory traversal
        for dir in fuzzer().dir:
          # n'th level traversal
          for n in range(1, 3):
            path = vol + sep + n * (dir + sep2)
            self.verify_blind(path, file)

  # check for path traversal
  def verify_path(self, path, found={}):
    # 1st method: EXISTS
    opt1 = (self.dir_exists(path) or False)
    # 2nd method: DIRLIST
    dir2 = self.dirlist(path, False)
    opt2 = (True if dir2 else False)
    # show fuzzing results
    output().fuzzed(path, "", ('', opt1, opt2))
    if opt2: # DIRLIST successful
      # add path if not already listed
      if dir2 not in found.values():
        found[path] = dir2
        output().raw("Listing directory.")
        self.do_ls(path)
    elif opt1: # only EXISTS successful
      found[path] = None

  # check for remote files (write)
  def verify_write(self, path, name, data, cmd):
    # 1st method: GET
    opt1 = (data in self.get(path+name, len(data))[1])
    # 2nd method: EXISTS
    opt2 = (self.file_exists(path+name) != c.NONEXISTENT)
    # 3rd method: DIRLIST
    opt3 = (name in self.dirlist(path, False))
    # show fuzzing results
    output().fuzzed(path+name, cmd, (opt1, opt2, opt3))
    return opt1

  # check for remote files (blind)
  def verify_blind(self, path, name):
    # 1st method: GET
    opt1 = self.get(path+name, 10)[1] # file size is unknown :/
    opt1 = (True if opt1 and not "FILEERROR" in opt1 else False)
    # 2nd method: EXISTS
    opt2 = (self.file_exists(path+name) != c.NONEXISTENT)
    # show fuzzing results
    output().fuzzed(path+name, "", ('', opt1, opt2))

  def help_fuzz(self):
    print("File system fuzzing:  fuzz <category>")
    print("  fuzz path   - Explore fs structure with path traversal strategies.")
    print("  fuzz write  - First put/append file, then check for its existence.")
    print("  fuzz blind  - Read-only tests for existing files like /etc/passwd.")

  options_fuzz = ('path', 'write', 'blind')
  def complete_fuzz(self, text, line, begidx, endidx):
    return [cat for cat in self.options_fuzz if cat.startswith(text)]

  # ====================================================================

  # ------------------------[ site <command> ]--------------------------
  def do_site(self, arg):
    "Execute custom command on printer:  site <command>"
    if not arg:
      arg = raw_input("Command: ")
    str_recv = self.cmd(arg)
    output().info(str_recv)

  # ------------------------[ print <file>|"text" ]----------------------------
  def do_print(self, arg):
    'Print image file or raw text:  print <file>|"text"'
    '''
    ┌──────────────────────────────────────────────────────────┐
    │ Poor man's driverless printing (PCL based, experimental) │
    └──────────────────────────────────────────────────────────┘
    '''
    if not arg: arg = raw_input('File or "text": ')
    if arg.startswith('"'): data = arg.strip('"')     # raw text string
    elif arg.endswith('.ps'): data = file().read(arg) # postscript file
    else: data = self.convert(arg, 'pcl')             # anything else…
    if data: self.send(c.UEL + data + c.UEL) # send pcl datastream to printer

  # convert image to page description language
  def convert(self, path, pdl='pcl'):
    '''
    ┌──────────────────────────────────────────────────────────┐
    │ Warning: ImageMagick and Ghostscript are used to convert │
    │ the document to be printed into a language understood be │
    │ the printer. Don't print anything from untrusted sources │
    │ as it may be a security risk (CVE-2016–3714, 2016-7976). │
    └──────────────────────────────────────────────────────────┘
    '''
    try:
      self.chitchat("Converting '" + path + "' to " + pdl + " format")
      pdf = ['-density', '300'] if path.endswith('.pdf') else []
      cmd = ['convert'] + pdf + [path, '-quality', '100', pdl + ':-']
      out, err = subprocess.PIPE, subprocess.PIPE
      p = subprocess.Popen(cmd, stdout=out, stderr=err)
      data, stderr = p.communicate()
    except: stderr = "ImageMagick or Ghostscript missing"
    if stderr: output().errmsg("Cannot convert", stderr)
    else: return data

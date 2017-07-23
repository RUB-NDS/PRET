# -*- coding: utf-8 -*-

class fuzzer():
  vol = ["", ".", "\\", "/", "file:///", "C:/"]
  var = ["~", "$HOME"]
  win = ["%WINDIR%", "%SYSTEMROOT%", "%HOMEPATH%", "%PROGRAMFILES%"]
  smb = ["\\\\127.0.0.1\\"]
  web = ["http://127.0.0.1/"] # "http://hacking-printers.net/log.me"
  dir = ["..", "...", "...."] # also combinations like "./.."
# sep = ["", "\\", "/", "\\\\", "//", "\\/"] 
  fhs = ["/etc", "/bin", "/sbin", "/home", "/proc", "/dev", "/lib",
         "/opt", "/run",  "/sys", "/tmp", "/usr", "/var",  "/mnt",]
  abs = [".profile", ["etc", "passwd"], ["bin", "sh"], ["bin", "ls"],
         "boot.ini", ["windows", "win.ini"], ["windows", "cmd.exe"]]
  rel = ["%WINDIR%\\win.ini",
         "%WINDIR%\\repair\\sam",
         "%WINDIR%\\repair\\system",
         "%WINDIR%\\system32\\config\\system.sav",
         "%WINDIR%\\System32\\drivers\\etc\\hosts",
         "%SYSTEMDRIVE%\\boot.ini",
         "%USERPROFILE%\\ntuser.dat",
         "%SYSTEMDRIVE%\\pagefile.sys",
         "%SYSTEMROOT%\\repair\\sam",
         "%SYSTEMROOT%\\repair\\system"]

  # define prefixes to use in fuzzing modes
  path  = vol+var+win+smb+web # path fuzzing
  write = vol+var+win+smb+fhs # write fuzzing
  blind = vol+var             # blind fuzzing

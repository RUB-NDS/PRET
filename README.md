## PRET - Printer Exploitation Toolkit

**Is your printer secure? Check before someone else does...**

### Installation

PRET requires 3rd-party modules for colored output and SNMP support. For a quick install, use:

    # pip install colorama pysnmp

If unicode characters are not displayed correctly on a Windoze console, try this:

    # pip install win_unicode_console

### Usage

```
usage: pret.py [-h] [-s] [-q] [-d] [-i file] [-o file] target {ps,pjl,pcl}

positional arguments:
  target                printer device or hostname
  {ps,pjl,pcl}          printing language to abuse

optional arguments:
  -h, --help            show this help message and exit
  -s, --safe            verify if language is supported
  -q, --quiet           suppress warnings and chit-chat
  -d, --debug           enter debug mode (show traffic)
  -i file, --load file  load and run commands from file
  -o file, --log file   log raw data sent to the target
```

###### Example usage:

    $ ./pret.py laserjet.lan ps
    $ ./pret.py /dev/usb/lp0 pjl

###### Flags and Arguments:

`--safe` tries to check via IPP, HTTP and SNMP if the selected printing language (PS/PJL/PCL) is actually supported by the device before connection via port 9100/tcp. On non-networked connections (USB, parallel cable), this test will fail.

`--quit` suppresses printer model determination, intro and other chit-chat.

`--debug` shows the PS/PJL/PCL commands actually sent to the device and the feedback received. Note that header data and other overhead is filtered. The see the whole traffic, use e.g. wireshark. Debugging can also be switched on/off within a PRET session using the `debug` command 

`--load filename` reads and executes PRET commands from a text file. This is usefull for automation. Command files can also be invoked later within a PRET session via the `load` command.

`--log filename` writes a copy of the raw PS/PJL/PCL datastream sent to the printer into a file. This can be useful to build a malicious print job, which can be deployed to another printer not directly reachable via port 9100/tcp.

### Generic Commands

After connecting to a printer (e.g. via network or USB cable), you will see the PRET shell and can execute various commands:

```
$ ./pret.py laserjet.lan pjl
      ________________
    _/_______________/|
   /___________/___//||   PRET | Printer Exploitation Toolkit v0.25
  |===        |----| ||    by Jens Mueller <jens.a.mueller@rub.de>
  |           |   ô| ||
  |___________|   ô| ||
  | ||/.´---.||    | ||        「 cause your device can be
  |-||/_____\||-.  | |´           more fun than paper jams 」
  |_||=L==H==||_|__|/

     (ASCII art by
     Jan Foerster)

Connection to laserjet.lan established
Device:   hp LaserJet 4250

Welcome to the pret shell. Type help or ? to list commands.
laserjet.lan:/> help

Available commands (type help <topic>):
=======================================
append  debug    edit    free  id    ls       open      restart   timeout  
cat     delete   env     fuzz  info  mirror   printenv  selftest  touch    
cd      df       exit    get   load  mkdir    put       set       traversal
chvol   disable  find    help  lock  nvram    pwd       site      unlock   
close   display  format  hold  loop  offline  reset     status    version  

laserjet.lan:/> ls ../../
-      834   .profile
d        -   bin
d        -   dev
d        -   etc
d        -   hp
d        -   hpmnt
-     1276   init
d        -   lib
d        -   pipe
d        -   tmp
laserjet.lan:/> exit
```

Generic commands are:

```
help      List available commands or get detailed help with 'help cmd'.
debug     Enter debug mode. Use 'hex' for hexdump.
load      Run commands from file:  load cmd.txt
loop      Run command for multiple arguments:  loop <cmd> <arg1> <arg2> …
open      Connect to remote device:  open <target>
close     Disconnect from device.
timeout   Set connection timeout:  timeout <seconds>
site      Execute custom command on printer:  site <command>
discover  Discover local printer devices via SNMP.
exit      Exit the interpreter.
```

Generic (file) operations with a PS/PJL/PCL specific implementation are:

```
┌───────────┬─────┬─────┬─────┬────────────────────────────────────────┐
│ Command   │ PS  │ PJL │ PCL │ Description                            │
├───────────┼─────┼─────┼─────┼────────────────────────────────────────┤
│ ls        │  ✓  │  ✓  │  ✓  │ List contents of remote directory.     │
│ get       │  ✓  │  ✓  │  ✓  │ Receive file: get <file>               │
│ put       │  ✓  │  ✓  │  ✓  │ Send file: put <local file>            │
│ append    │  ✓  │  ✓  │     │ Append to file: append <file> <str>    │
│ delete    │  ✓  │  ✓  │  ✓  │ Delete remote file: delete <file>      │
│ rename    │  ✓  │     │     │ Rename remote file: rename <old> <new> │
│ find      │  ✓  │  ✓  │     │ Recursively list directory contents.   │
│ mirror    │  ✓  │  ✓  │     │ Mirror remote filesystem to local dir. │
│ cat       │  ✓  │  ✓  │  ✓  │ Output remote file to stdout.          │
│ edit      │  ✓  │  ✓  │  ✓  │ Edit remote files with vim.            │
│ touch     │  ✓  │  ✓  │     │ Update file timestamps: touch <file>   │
│ mkdir     │  ✓  │  ✓  │     │ Create remote directory: mkdir <path>  │
├───────────┼─────┼─────┼─────┼────────────────────────────────────────┤
│ cd        │  ✓  │  ✓  │     │ Change remote working directory.       │
│ pwd       │  ✓  │  ✓  │     │ Show working directory on device.      │
│ chvol     │  ✓  │  ✓  │     │ Change remote volume: chvol <volume>   │
│ traversal │  ✓  │  ✓  │     │ Set path traversal: traversal <path>   │
├───────────┼─────┼─────┼─────┼────────────────────────────────────────┤
│ format    │  ✓  │  ✓  │     │ Initialize printer's file system.      │
│ fuzz      │  ✓  │  ✓  │     │ File system fuzzing: fuzz <category>   │
├─ ─ ─ ─ ─ ─┴─ ─ ─┴─ ─ ─┴─ ─ ─┴─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┤
│   path   - Explore fs structure with path traversal strategies.      │
│   write  - First put/append file, then check for its existence.      │
│   blind  - Read-only tests for existing files like /etc/passwd.      │
├───────────┬─────┬─────┬─────┬────────────────────────────────────────┤
│ df        │  ✓  │  ✓  │     │ Show volume information.               │
│ free      │  ✓  │  ✓  │  ✓  │ Show available memory.                 │
└───────────┴─────┴─────┴─────┴────────────────────────────────────────┘
```

### Commands in PS mode

```
id         Show device information.
version    Show PostScript interpreter version.
devices    Show available I/O devices.
uptime     Show system uptime (might be random).
date       Show printer's system date and time.
pagecount  Show printer's page counter.

lock       Set startjob and system parameters password.
unlock     Unset startjob and system parameters password.
restart    Restart PostScript interpreter.
reset      Reset PostScript settings to factory defaults.
disable    Disable printing functionality.
destroy    Cause physical damage to printer's NVRAM.
hang       Execute PostScript infinite loop.

overlay    Put overlay eps file on all hardcopies:  overlay <file.eps>
cross      Put printer graffiti on all hardcopies:  cross <font> <text>
replace    Replace string in documents to be printed:  replace <old> <new>
capture    Capture further jobs to be printed on this device.
hold       Enable job retention.

set        Set key to value in topmost dictionary:  set <key=value>
known      List supported PostScript operators:  known <operator>
search     Search all dictionaries by key:  search <key>
dicts      Return a list of dictionaries and their permissions.
resource   List or dump PostScript resource:  resource <category> [dump]

dump       Dump dictionary:  dump <dict>
  Dictionaries: - systemdict - statusdict - userdict 
                - globaldict - serverdict - errordict
                - internaldict - currentsystemparams
                - currentuserparams - currentpagedevice

config     Change printer settings:  config <setting>
  duplex        - Set duplex printing.
  copies #      - Set number of copies.
  economode     - Set economic mode.
  negative      - Set negative print.
  mirror        - Set mirror inversion.
```

### Commands in PJL mode

```
id         Show device information.
status     Enable status messages.
version    Show firmware version or serial number (from 'info config').
pagecount  Manipulate printer's page counter:  pagecount <number>
printenv   Show printer environment variable:  printenv <VAR>
env        Show environment variables (alias for 'info variables').
set        Set printer environment variable:  set <VAR=VALUE>

display    Set printer's display message:  display <message>
offline    Take printer offline and display message:  offline <message>
restart    Restart printer.
reset      Reset to factory defaults.
selftest   Perform various printer self-tests.
disable    Disable printing functionality.
destroy    Cause physical damage to printer's NVRAM.
flood      Flood user input, may reveal buffer overflows.

lock       Lock control panel settings and disk write access.
unlock     Unlock control panel settings and disk write access.
hold       Enable job retention.

nvram      NVRAM operations:  nvram <operation>
  nvram dump [all]           - Dump (all) NVRAM to local file.
  nvram read addr            - Read single byte from address.
  nvram write addr value     - Write single byte to address.

info       Show information:  info <category>
  info config      - Provides configuration information.
  info filesys     - Returns PJL file system information.
  info id          - Provides the printer model number.
  info memory      - Identifies amount of memory available.
  info pagecount   - Returns the number of pages printed.
  info status      - Provides the current printer status.
  info ustatus     - Lists the unsolicited status variables.
  info variables   - Lists printer's environment variables.
```

Not that many commands are supported exclusively by HP printers, because other vendors have only implemented a subset of the PJL standard. This is especially true for PML based commands like `restart`or `reset`. Enabling long-term job retention via the `hold` command seems to be possible for Epson devices only. NVRAM access via the `nvram` command seems to work on printers by Brother (and Konica Minolta?). Access to the file system (inclusing path traversal) seems to be supported by HP only. Xerox, Kyocera, Ricoh and Dell (which only shell rebranded devices) do partially read/write operations, however limited to a certain, sandboxed directory.

### Commands in PCL mode

```
selftest   Perform printer self-test.
info       Show information:  info <category>
  info fonts      - Show installed fonts.
  info macros     - Show installed macros.
  info patterns   - Show user-defined patterns.
  info symbols    - Show symbol sets.
  info extended   - Show extended fonts.
```

PCL is a very limited page description language without access to the file system. The to get/put/ls commands therefore use on a virtual file system based on PCL macros and mostly for the hack value :)

### The Files

- `pret.py` - Executable main program
- `capabilities.py` - Routines to check for printer langauge support
- `printer.py` - Generic code to describe a printer
- `postscript.py` - PS spezific code (inherits from class printer)
- `pjl.py` - PJL spezific code (inherits from class printer)
- `pcl.py` - PCL spezific code (inherits from class printer)
- `helper.py` - Help functions for output and debugging, logging, file system access, sending and recveiving via socket or character device and printer language constants
- `codebook.py` - Static tabelle of PJL status/error codes
- `fuzzer.py` - Constants for file system fuzzing
- `mibs/*` - Printer specific MIBs used by snimpy
- `db/*` - database of supported models
- `lpd/*` - Scripts for LPD fuzzing

*Happy Hacking!*

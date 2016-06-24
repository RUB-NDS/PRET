## PRET
### Printer Exploitation Toolkit


### Python Files

* pret.py:          Ausführbares Hauptprogramm
* capabilities.py:  Routinen zum Checken ob Sprache supported wird

* printer.py:       Generischer Code der einen Drucker beschreibt
* postscript.py:    PS-spezifischer Code (erbt von Klasse printer)
* pjl.py:           PJL-spezifischer Code (erbt von Klasse printer)
* pcl.py:           PCL-spezifischer Code (erbt von Klasse printer)

* helper.py:        Hilfsfunktionen für Ausgaben und Debugging,
                    Logging, Dateizugriff, Senden und Empfangen
                    von Daten über Socket oder Character Device
                    sowie druckerspezifische Konstanten
* codebook.py:      Statische Tabelle an PJL Status/Error Codes
* fuzzer.py:        Konstanten fürs Dateisystem-Fuzzing

### ----------------------[ INSTALLATION ]----------------------

Die folgenden 3rd-party Module werden von PRET benötigt (für farbenfrohe
Ausgabe und SNMP-support, könnte ggf. zukünftig optional gemacht werden
um Abhändigkeiten zu reduzieren und damit die Installation
benutzerfreundlicher zu machen):

    # pip install colorama snimpy

### -----------------------[ BENUTZUNG ]------------------------

```
usage: pret.py [-h] [-s] [-q] [-d] [-i file] [-o file] target {ps,pjl,pcl}

Printer Exploitation Toolkit.

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

Beispiel-Aufrufe:

    $ ./pret.py laserjet.lan ps
    $ ./pret.py /dev/usb/lp0 pjl

Zuschaltbare Flags:

--safe  versucht, vor dem Verbinden auf Port 9100 zu über IPP, HTTP
        und SNMP herauszufinden, ob der Drucker die angegebene Sprache
        (ps/pjl/pcl) überhaupt spricht (siehe capabilities.py bzw. die
        TBD-Section 8.2. - Printer Discovery in der Thesis). Bei einer
        Verbindung über USB/Parallel schlägt --safe logischerweise fehl.

--quit  versucht nicht, anfangs das Druckermodell zu bestimmen und
        unterdrückt nicht ganz so wichtige Ausgaben (sinnvoll für
        automatisierte Tests).

--debug erlaubt es zu sehen, welche PS/PJL/PCL Befehle tatsächlich
        übertragen werden und was empfangen wird. Die Ausgabe ist
        bewusst auf die eigentliche Druckersprache reduziert und
        versucht jeglichen Overhead (z.B. Header) rauszufiltern
        (siehe conn.beautify() in helper.py). Für den vollständigen
        Traffic: wireshark. Debug kann auch bei Bedarf per 'debug'
        Kommando innerhalb einer PRET-Session zu/abgeschaltet werden.

--load  erlaubt es, PRET-Kommandos aus einer Textdatei auszuführen
        (sinnvoll z.B. für automatisierte Tests auf eine Vielzahl an
        Geräten). Die Datei kann auch innerhalb einer PRET-Session
        über das Kommando 'load' geladen werden.

--log   erlaubt es, die PS/PJL/PCL Befehle (inkl. Headern) in eine
        Datei zu schreiben. Es handelt sich hier nicht um die Ausgabe
        des Druckers, sondern um die dort hin gesendeten Rohdaten.
        Dies ist sinnvoll, um sich einen "malicious print job" zu
        erstellen, der dann beispielsweise auf anderem Wege ohne
        Port-9100 Rückkanal an den Drucker geschickt werden kann
        (siehe Table 9.1 - Printing Channels in der Thesis).

### ----------------------[ GENERISCHE BEFEHLE ]----------------------

Nach dem Verbinden zu einem Drucker kommt man in die PRET-eigene Shell und kann -- ähnlich eines kommandozeilenbasierenden FTP-Clients -- verschiedene Kommandos ausführen, z.B.:

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
append debug   edit     free   hold loop   offline  reset   status
cat    delete  env      fsinit id   ls     open     restart timeout
cd     df      exit     fuzz   info mirror printenv serial  touch
chvol  disable find     get    load mkdir  put      set     traversal
close  display firmware help   lock nvram  pwd      site    unlock

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

Generische Kommandos sind:

help     List available commands or get detailed help with 'help cmd'.
debug    Enter debug mode. Use 'hex' for hexdump.
load     Run commands from file:  load cmd.txt
loop     Run command for multiple arguments:  loop <cmd> <arg1> <arg2> …
open     Connect to remote device:  open <target>
close    Disconnect from device.
timeout  Set connection timeout:  timeout <seconds>
site     Execute custom command on printer:  site <command>
         (sinnvoll um PS/PJL/PCL Befehle die noch nicht implementiert
         sind testweise direkt einzugeben und Ausgabe abzuwarten)
exit     Exit the interpreter.

Generische (Datei-)operationen mit je spezifische Implementierung sind:

┌───────────┬─────┬─────┬─────┬────────────────────────────────────────┐
│ Command   │ PS  │ PJL │ PCL │ Description                            │
├───────────┼─────┼─────┼─────┼────────────────────────────────────────┤
│ id        │  ✓  │  ✓  │     │ Show device information.               │
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
│ mkdir     │     │  ✓  │     │ Create remote directory: mkdir <path>  │
├───────────┼─────┼─────┼─────┼────────────────────────────────────────┤
│ cd        │  ✓  │  ✓  │     │ Change remote working directory        │
│ pwd       │  ✓  │  ✓  │     │ Show working directory on device.      │
│ chvol     │  ✓  │  ✓  │     │ Change remote volume: chvol <volume>   │
│ traversal │  ✓  │  ✓  │     │ Set path traversal: traversal <path>   │
├───────────┼─────┼─────┼─────┼────────────────────────────────────────┤
│ fsinit    │ TBD │  ✓  │     │ Initialize printer's file system.      │
│ fuzz      │  ✓  │  ✓  │     │ File system fuzzing: fuzz <category>   │
├─ ─ ─ ─ ─ ─┴─ ─ ─┴─ ─ ─┴─ ─ ─┴─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┤
│   path   - Explore fs structure with path traversal strategies.      │
│   write  - First put/append file, then check for its existence.      │
│   blind  - Read-only tests for existing files like /etc/passwd.      │
├───────────┬─────┬─────┬─────┬────────────────────────────────────────┤
│ df        │  ✓  │  ✓  │     │ Show volume information.               │
│ free      │  ✓  │  ✓  │  ✓  │ Show available memory.                 │
└───────────┴─────┴─────┴─────┴────────────────────────────────────────┘

### ----------------------[ BEFEHLE IM MODUS 'ps' ]-----------------------

shell      Open interactive PostScript shell.
uptime     Show system uptime (might be random).
devices    Show available I/O devices.

Es lässt sich bereits sagen: Dateisystemzugriff ist in PostScript
wesentlich öfters möglich als in PJL. Inwieweit dies zu Code Execution
oder ähnlich kritischen Sachen führt muss aber noch je nach Gerät
analysiert werden (TBD: Exploitation/Evaluation).

### ----------------------[ BEFEHLE IM MODUS 'pjl' ]----------------------

status     Enable status messages.
printenv   Show printer environment variable:  printenv <VAR>
env        Show environment variables (alias for 'info variables').
set        Set printer environment variable:  set <VAR=VALUE>

display    Set printer's display message:  display <message>
offline    Take printer offline and display message:  offline <message>
restart    Restart printer.
reset      Reset to factory defaults. (überschreibt z.B. Passwörter)
disable    Disable printing functionality.

lock       Lock control panel settings and disk write access.
unlock     Unlock control panel settings and disk write access.
hold       Enable job retention. (Scheint be Epson zu klappen)
serial     Show serial number (from 'info config').
firmware   Show firmware datecode/version (from 'info config')

nvram      NVRAM operations:  nvram <operation>
  nvram dump                 - Dump NVRAM to local file.
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

Viele Kommandos sind nur auf HP-Druckern möglich, da andere Hersteller
meist nur eine Untermenge deren Standards implementiert haben. Dies gilt
insbesondere für PML-basierende (siehe TBD-Subsection 2.3.3. - PML in
der Thesis) Kommandos wie 'restart' und 'reset'. Druckjobs (nicht den
aktuellen, sondern auch alle zukünftigen) via 'hold' auf dem Gerät zu
speichern scheint nur bei Epson möglich. NVRAM auslesen geht nur auf
Brother (und Konica Minolta?) Geräten. Dateisystemoperationen scheinen
nur HP unterstüzt zu werden (inkl. Path Traversal). Xerox, Kyocera,
Ricoh und Dell (wobei letztere nur rebranden und keine eigenen Drucker
herstellen) erlauben zwar teilweise Dateisystemzugriff, aber nur auf ein
bestimmtes, gesandboxtes Verzeichnis. Die Untersuchungen hierzu sind
aber noch nicht abgeschlossen (TBD: Exploitation/Evaluation).

### ----------------------[ BEFEHLE IM MODUS 'pcl' ]----------------------

selftest   Perform printer self-test.
info       Show information:  info <category>
  info fonts      - Show installed fonts.
  info macros     - Show installed macros.
  info patterns   - Show user-defined patterns.
  info symbols    - Show symbol sets.
  info extended   - Show extended fonts.

PCL ist eine sehr simple Seitenbeschreibungssprache ohne
Dateisystemzugriff. Die in PRET implementierten put/get/ls Befehle
arbeiten deshalb auf einem virtuellen, auf PCL-Macros basierenden
Dateisystem welches eher für den Hack Value geschrieben wurde und keine
Exploitation des realen Druckers-FS ermöglicht (siehe Presentation vom
2016-06-06).

Happy Hacking!


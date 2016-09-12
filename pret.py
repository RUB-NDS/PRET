#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# python standard library
import argparse

# local pret classes
from postscript import postscript
from pjl import pjl
from pcl import pcl
from capabilities import capabilities

# ----------------------------------------------------------------------

def usage():
  parser = argparse.ArgumentParser(description="Printer Exploitation Toolkit.")
  parser.add_argument("target", help="printer device or hostname")
  parser.add_argument("mode", choices=['ps', 'pjl', 'pcl'], help="printing language to abuse")
  parser.add_argument("-s", "--safe", help="verify if language is supported", action="store_true")
  parser.add_argument("-q", "--quiet", help="suppress warnings and chit-chat", action="store_true")
  parser.add_argument("-d", "--debug", help="enter debug mode (show traffic)", action="store_true")
  parser.add_argument("-i", "--load", metavar="file",  help="load and run commands from file")
  parser.add_argument("-o", "--log", metavar="file", help="log raw data sent to the target")
  return parser.parse_args()

# ----------------------------------------------------------------------

def intro(quiet):
  if not quiet:
    print("      ________________                                             ")
    print("    _/_______________/|                                            ")
    print("   /___________/___//||   PRET | Printer Exploitation Toolkit v0.30")
    print("  |===        |----| ||    by Jens Mueller <jens.a.mueller@rub.de> ")
    print("  |           |   ô| ||                                            ")
    print("  |___________|   ô| ||                                            ")
    print("  | ||/.´---.||    | ||        「 cause your device can be         ")
    print("  |-||/_____\||-.  | |´           more fun than paper jams 」      ")
    print("  |_||=L==H==||_|__|/                                              ")
    print("                                                                   ")
    print("     (ASCII art by                                                 ")
    print("     Jan Foerster)                                                 ")
    print("                                                                   ")

# ----------------------------------------------------------------------

def main():
  args = usage()     # parse args/options #
  intro(args.quiet)  # show asciitainment #
  capabilities(args) # check capabilities #
  # connect to printer, use this language #
  if args.mode == 'ps':  postscript(args)
  if args.mode == 'pjl': pjl(args)
  if args.mode == 'pcl': pcl(args)

# ----------------------------------------------------------------------

# clean exit
if __name__ == '__main__':
  try:
    main()
  # catch CTRL-C
  except (KeyboardInterrupt):
    pass
  finally:
    print("")

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

# python standard library
import os
import sys
import argparse

# local pret classes
from discovery import discovery
from capabilities import capabilities
from postscript import postscript
from pjl import pjl
from pcl import pcl

# ----------------------------------------------------------------------


def usage():
    parser = argparse.ArgumentParser(
        description="Printer Exploitation Toolkit.")
    parser.add_argument("target", help="printer device or hostname")
    parser.add_argument(
        "mode", choices=['ps', 'pjl', 'pcl'], help="printing language to abuse")
    parser.add_argument(
        "-s", "--safe", help="verify if language is supported", action="store_true")
    parser.add_argument(
        "-q", "--quiet", help="suppress warnings and chit-chat", action="store_true")
    parser.add_argument(
        "-d", "--debug", help="enter debug mode (show traffic)", action="store_true")
    parser.add_argument("-i", "--load", metavar="file",
                        help="load and run commands from file")
    parser.add_argument("-o", "--log", metavar="file",
                        help="log raw data sent to the target")
    if len(sys.argv) < 2:
        discovery(True)  # list local printers if no arguments given at all
    if len(sys.argv) == 2:
        print("No printer language given, please select one" + os.linesep)
    return parser.parse_args()

# ----------------------------------------------------------------------


def intro(quiet):
    if not quiet:
        print(r"      ________________                                             ")
        print(r"    _/_______________/|                                            ")
        print(r"   /___________/___//||   PRET | Printer Exploitation Toolkit v0.40")
        print(r"  |===        |----| ||    by Jens Mueller <jens.a.mueller@rub.de> ")
        print(r"  |           |   ô| ||                                            ")
        print(r"  |___________|   ô| ||                                            ")
        print(r"  | ||/.´---.||    | ||      「 pentesting tool that made          ")
        print(r"  |-||/_____\||-.  | |´         dumpster diving obsolete‥ 」       ")
        print(r"  |_||=L==H==||_|__|/                                              ")
        print(r"                                                                   ")
        print(r"     (ASCII art by                                                 ")
        print(r"     Jan Foerster)                                                 ")
        print(r"                                                                   ")

# ----------------------------------------------------------------------


def main():
    args = usage()     # parse args/options #
    intro(args.quiet)  # show asciitainment #
    capabilities(args)  # check capabilities #
    # connect to printer, use this language #
    if args.mode == 'ps':
        postscript(args)
    if args.mode == 'pjl':
        pjl(args)
    if args.mode == 'pcl':
        pcl(args)

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

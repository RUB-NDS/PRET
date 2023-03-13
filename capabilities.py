#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# python standard library
import re
import os
import sys  # , urllib.error, urllib.parse

import requests

import urllib3

# local pret classes
from helper import output, item

# third party modules
try:
    from pysnmp.entity.rfc3413.oneliner import cmdgen
except ImportError:
    pass


class capabilities():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    # set defaults
    support = False
    # be quick and dirty
    timeout = 1.5
    # set pret.py directory
    rundir = os.path.dirname(os.path.realpath(__file__)) + os.path.sep
    '''
  ┌──────────────────────────────────────────────────────────┐
  │            how to get printer's capabilities?            │
  ├──────┬───────────────────────┬───────────────────────────┤
  │      │ model (for db lookup) │ lang (ps/pjl/pcl support) │
  ├──────┼───────────────────────┼───────────────────────────┤
  │ IPP  │ printer-description   │ printer-description       │
  │ SNMP │ hrDeviceDescr         │ prtInterpreterDescription │
  │ HTTP │ html-title            │ -                         │
  | HTTPS| html-title            | -                         |
  └──────┴───────────────────────┴───────────────────────────┘
  '''

    def __init__(self, args):
        # skip this in unsafe mode
        if not args.safe:
            return
        # set printer language
        if args.mode == 'ps':
            lang = ["PS", "PostScript", "BR-Script", "KPDL"]
        if args.mode == 'pjl':
            lang = ["PJL"]
        if args.mode == 'pcl':
            lang = ["PCL"]
        # get list of PostScript/PJL/PCL capable printers
        self.models = self.get_models(args.mode + ".dat")
        # try to get printer capabilities via IPP/SNMP/HTTP
        if not self.support:
            self.ipp(args.target, lang)
        if not self.support:
            self.http(args.target)
        if not self.support:
            self.https(args.target)
        if not self.support:
            self.snmp(args.target, lang)
        # feedback on PostScript/PJL/PCL support
        self.feedback(self.support, lang[0])
        # in safe mode, exit if unsupported
        if args.safe and not self.support:
            print((os.linesep + "Quitting as we are in safe mode."))
            sys.exit()
        print("")

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # get capabilities via IPP
    def ipp(self, host, lang):
        try:
            # poor man's way to get printer info via IPP
            sys.stdout.write("Checking for IPP support:         ")
            body = ("\x01\x01\x00\x0b\x00\x01\xab\x10\x01G\x00\x12attributes-charset\x00\x05utf-8H"
                    + "\x00\x1battributes-natural-language\x00\x02enE\x00\x0bprinter-uri\x00\x14ipp:"
                    + "//localhost/ipp/D\x00\x14requested-attributes\x00\x13printer-description\x03").encode()
            request = requests.get("http://" + host + ":631/",
                                   data=body, headers={'Content-type': 'application/ipp'})
            response = request.content.decode()
            # get name of device
            # e.g. MDL:hp LaserJet 4250
            model = item(re.findall("MDL:(.+?);", response))
            # get language support
            # e.g. CMD:PCL,PJL,POSTSCRIPT
            langs = item(re.findall("CMD:(.+?);", response))
            self.support = [_f for _f in [re.findall(
                re.escape(pdl), langs, re.I) for pdl in lang] if _f]
            self.set_support(model)
            output().green("found")
        except Exception as e:
            output().errmsg("not found", e)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # get capabilities via HTTP
    def http(self, host):
        try:
            # poor man's way get http title
            sys.stdout.write("Checking for HTTP support:        ")
            html = requests.get("http://" + host).text
            # cause we are to parsimonious to import BeautifulSoup ;)
            title = re.findall("<title.*?>\n?(.+?)\n?</title>",
                               html, re.I | re.M | re.S)
            # get name of device
            model = item(title)
            # get language support
            self.set_support(model)
            output().green("found")
        except Exception as e:
            output().errmsg("not found", e)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # get capabilities via HTTPS
    def https(self, host):
        try:
            # poor man's way get https title
            sys.stdout.write("Checking for HTTPS support:       ")
            html = requests.get("https://" + host, verify=False).text
            # cause we are to parsimonious to import BeautifulSoup ;)
            title = re.findall("<title.*?>\n?(.+?)\n?</title>",
                               html, re.I | re.M | re.S)
            # get name of device
            model = item(title)
            # get language support
            self.set_support(model)
            output().green("found")
        except Exception as e:
            output().errmsg("not found", e)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # get capabilities via SNMP
    def snmp(self, host, lang):
        try:
            sys.stdout.write("Checking for SNMP support:        ")
            # query device description and supported languages
            # HOST-RESOURCES-MIB → hrDeviceDescr
            desc, desc_oid = [], '1.3.6.1.2.1.25.3.2.1.3'
            # Printer-MIB → prtInterpreterDescription
            pdls, pdls_oid = [], '1.3.6.1.2.1.43.15.1.1.5.1'
            error, error_status, idx, binds = cmdgen.CommandGenerator().nextCmd(
                cmdgen.CommunityData('public', mpModel=0), cmdgen.UdpTransportTarget(
                    (host, 161), timeout=self.timeout, retries=0), desc_oid, pdls_oid)
            # exit on error
            if error:
                raise Exception(error)
            if error_status:
                raise Exception(error_status.prettyPrint())
            # parse response
            for row in binds:
                for key, val in row:
                    if desc_oid in str(key):
                        desc.append(str(val))
                    if pdls_oid in str(key):
                        pdls.append(str(val))
            # get name of device
            model = item(desc)
            # get language support
            langs = ','.join(pdls)
            self.support = [_f for _f in [re.findall(
                re.escape(pdl), langs, re.I) for pdl in lang] if _f]
            # self.set_support(model)
            output().green("found")
        except NameError:
            output().errmsg("not found", "pysnmp module not installed")
        except Exception as e:
            output().errmsg("not found", e)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # feedback on language support

    def feedback(self, support, lang):
        sys.stdout.write("Checking for %-21s" % (lang + " support: "))
        if support:
            output().green("found")
        else:
            output().warning("not found")

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # set language support
    def set_support(self, model):
        # model_stripped = re.sub(r'(\d|\s|-)[a-zA-Z]+$', '', model)
        '''
        ┌───────────────────────────────────────────────────────┐
        │ Experimental -- This might introduce false positives! │
        ├───────────────────────────────────────────────────────┤
        │ The stripped down version of the model string removes │
        │ endings like '-series', ' printer' (maybe localized), │
        │ 'd' (duplex), 't' (tray), 'c' (color), 'n' (network). │
        └───────────────────────────────────────────────────────┘
        '''
        self.support = [_f for _f in [re.findall(
            re.escape(m), model, re.I) for m in self.models] if _f]

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # open database of supported devices
    def get_models(self, file):
        try:
            with open(self.rundir + "db" + os.path.sep + file, 'r') as f:
                models = [_f for _f in (line.strip() for line in f) if _f]
            f.close()
            return models
        except IOError as e:
            output().errmsg("Cannot open file", e)
            return []

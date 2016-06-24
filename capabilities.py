# -*- coding: utf-8 -*-

# python standard library
import re, os, sys, urllib2

# third party modules
from snimpy.manager import Manager, load

# local pret classes
from helper import output, item

class capabilities():
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
  └──────┴───────────────────────┴───────────────────────────┘
  '''

  def __init__(self, args):
    # skip this in unsafe mode
    if not args.safe: return
    # set printer language
    if args.mode == 'ps': lang = "PostScript"
    if args.mode == 'pjl': lang = "PJL"
    if args.mode == 'pcl': lang = "PCL"
    # get list of PostScript/PJL/PCL capable printers
    self.models = self.get_models(args.mode + ".dat")
    # try to get printer capabilities via IPP/SNMP/HTTP
    if not self.support: self.ipp(args.target, lang)
    if not self.support: self.http(args.target)
    if not self.support: self.snmp(args.target, lang)
    # feedback on PostScript/PJL/PCL support
    self.feedback(self.support, lang)
    # in safe mode, exit if unsupported
    if args.safe and not self.support:
      print(os.linesep + "Quitting as we are in safe mode.")
      sys.exit()
    print("")

  #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  # get capabilities via IPP
  def ipp(self, host, lang):
    try:
      # poor man's way to get printer info via IPP
      sys.stdout.write("Checking for IPP support:         ")
      body = ("\x01\x01\x00\x0b\x00\x01\xab\x10\x01G\x00\x12attributes-charset\x00\x05utf-8H"
            + "\x00\x1battributes-natural-language\x00\x02enE\x00\x0bprinter-uri\x00\x14ipp:"
            + "//localhost/ipp/D\x00\x14requested-attributes\x00\x13printer-description\x03")
      request  = urllib2.Request("http://" + host + ":631/ipp/port1",
                 data=body, headers={'Content-type': 'application/ipp'})
      response = urllib2.urlopen(request, timeout=self.timeout).read()
      model = re.findall("MDL:(.+?);", response) # e.g. MDL:hp LaserJet 4250
      langs = re.findall("CMD:(.+?);", response) # e.g. CMD:PCL,PJL,POSTSCRIPT
      # get name of device
      model = item(model)
      # get language support
      self.support = re.findall(lang, item(langs), re.I)
      self.set_support(model)
      output().green("found")
    except Exception as e:
      output().errmsg("not found", str(e))

  #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  # get capabilities via HTTP
  def http(self, host):
    try:
      # poor man's way get http title
      sys.stdout.write("Checking for HTTP support:        ")
      html = urllib2.urlopen("http://" + host, timeout=self.timeout).read()
      # cause we are to parsimonious to import BeautifulSoup ;)
      title = re.findall("<title.*?>\n?(.+?)\n?</title>", html, re.I|re.M|re.S)
      # get name of device
      model = item(title)
      # get language support
      self.set_support(model)
      output().green("found")
    except Exception as e:
      output().errmsg("not found", str(e))

  #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  # get capabilities via SNMP
  def snmp(self, host, lang):
    try:
      sys.stdout.write("Checking for SNMP support:        ")
      # load MIBs
      load(self.rundir + "mibs" + os.path.sep + "SNMPv2-MIB")
      load(self.rundir + "mibs" + os.path.sep + "Printer-MIB")
      load(self.rundir + "mibs" + os.path.sep + "HOST-RESOURCES-MIB")
      # create snimpy manager
      m = Manager(host, timeout=float(self.timeout)/4)
      descr = m.hrDeviceDescr.items()
      # get name of device
      model = item(descr)[1] if len(descr) > 1 else None
      # get language support
      langs = ','.join(m.prtInterpreterDescription.values())
      self.support = re.findall(lang, langs, re.I)
      self.set_support(model)
      output().green("found")
    except Exception as e:
      output().errmsg("not found", str(e))

  #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  # feedback on language support
  def feedback(self, support, lang):
    sys.stdout.write("Checking for %-21s" % (lang + " support: "))
    if support: output().green("found")
    else: output().warning("not found")

  #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  # set language support
  def set_support(self, model):
    model_stripped = re.sub(r'(\d|\s|-)[a-zA-Z]+$', '', model)
    '''
    ┌───────────────────────────────────────────────────────┐
    │ Experimental -- This might introduce false positives! │
    ├───────────────────────────────────────────────────────┤
    │ The stripped down version of the model string removes │
    │ endings like '-series', ' printer' (maybe localized), │
    │ 'd' (duplex), 't' (tray), 'c' (color), 'n' (network). │
    └───────────────────────────────────────────────────────┘
    '''
    if model in self.models or model_stripped in self.models:
      self.support = True

  #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  # open database of supported devices
  def get_models(self, file):
    models = []
    try:
      f = open(self.rundir + "db" + os.path.sep + file, 'r')
      for item in f.readlines():
        models.append(item.strip())
      f.close()
      return models
    except IOError as e:
      output().errmsg("Cannot open file", str(e))
      return []

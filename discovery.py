# -*- coding: utf-8 -*-

# python standard library
import socket

# local pret classes
from helper import output, conv

# third party modules
try:
  from pysnmp.carrier.asyncore.dispatch import AsyncoreDispatcher
  from pysnmp.carrier.asyncore.dgram import udp
  from pysnmp.proto import api
  from pyasn1.codec.ber import encoder, decoder
  snmp_modules_found = True
except ImportError:
  snmp_modules_found = False

########################################################
### Most of this code comes from the PySNMP examples ###
### and needs to be refactored into an 'snmp' class! ###
########################################################

start = conv().now()  # get current time
timeout = 0.5         # be quick and dirty
maxhost = 999         # max printers to list
results = {}          # dict of found printers

try:
  # use snmp v1 because it is most widely supported among printers
  pmod = api.protoModules[api.protoVersion1]
  pdu_send = pmod.GetRequestPDU() # build protocol data unit (pdu)
except:
  pass

# cause timeout interrupt
class stop_waiting(Exception): pass

# check for timeout
def timer(date):
  if date - start > timeout:
    raise stop_waiting()

# noinspection PyUnusedLocal,PyUnusedLocal
def recv(dispatcher, domain, address, msg):
  while msg:
    msg_recv, msg = decoder.decode(msg, asn1Spec=pmod.Message())
    pdu_recv = pmod.apiMessage.getPDU(msg_recv)
    # match response to request as we're broadcasting
    if pmod.apiPDU.getRequestID(pdu_send) == pmod.apiPDU.getRequestID(pdu_recv):
      ipaddr = address[0]; device = '?'; uptime = '?'; status = '?'; prstat = 0
      # retrieve device properties
      for oid, val in pmod.apiPDU.getVarBinds(pdu_recv):
        oid, val = oid.prettyPrint(), val.prettyPrint()
        # skip non-printer devices
        if oid == '1.3.6.1.2.1.25.3.2.1.2.1' and val != '1.3.6.1.2.1.25.3.1.5': return
        # harvest device information
        if oid == '1.3.6.1.2.1.25.3.2.1.3.1': device = val
        if oid == '1.3.6.1.2.1.1.3.0': uptime = conv().elapsed(val, 100, True)
        if oid == '1.3.6.1.2.1.43.16.5.1.2.1.1': status = val
        if oid == '1.3.6.1.2.1.25.3.2.1.5.1' and val: prstat = val[:1]
      dispatcher.jobFinished(1)
      results[ipaddr] = [device, uptime, status, prstat]

class discovery():
  # discover local network printers
  def __init__(self, usage=False):
    # abort if pysnmp is not installed
    if not snmp_modules_found:
      output().warning("Please install the 'pysnmp' module for SNMP support.")
      if usage: print("")
      return
    # skip when running 'discover' in interactive mode
    if usage: print("No target given, discovering local printers")
    oid = (('1.3.6.1.2.1.25.3.2.1.2.1',    None), # HOST-RESOURCES-MIB → hrDeviceType
           ('1.3.6.1.2.1.25.3.2.1.3.1',    None), # HOST-RESOURCES-MIB → hrDeviceDescr
           ('1.3.6.1.2.1.25.3.2.1.5.1',    None), # HOST-RESOURCES-MIB → hrDeviceStatus
           ('1.3.6.1.2.1.43.16.5.1.2.1.1', None), # Printer-MIB        → Printer status
           ('1.3.6.1.2.1.1.3.0',           None)) # SNMPv2-MIBv        → sysUpTime
    try:
      # build protocol data unit (pdu)
      pmod.apiPDU.setDefaults(pdu_send)
      pmod.apiPDU.setVarBinds(pdu_send, oid)
      # build message
      msg_send = pmod.Message()
      pmod.apiMessage.setDefaults(msg_send)
      pmod.apiMessage.setCommunity(msg_send, 'public')
      pmod.apiMessage.setPDU(msg_send, pdu_send)
      # ...
      dispatcher = AsyncoreDispatcher()
      dispatcher.registerRecvCbFun(recv)
      dispatcher.registerTimerCbFun(timer)
      # use ipv4 udp broadcast
      udpSocketTransport = udp.UdpSocketTransport().openClientMode().enableBroadcast()
      dispatcher.registerTransport(udp.domainName, udpSocketTransport)
      # pass message to dispatcher
      target = ('255.255.255.255', 161)
      dispatcher.sendMessage(encoder.encode(msg_send), udp.domainName, target)
      # wait for timeout or max hosts
      dispatcher.jobStarted(1, maxhost)
      # dispatcher will finish as all jobs counter reaches zero
      try:
        dispatcher.runDispatcher()
      except stop_waiting:
        dispatcher.closeDispatcher()
      # list found network printers
      if results:
        print("")
        output().discover(('address', ('device', 'uptime', 'status', None)))
        output().hline(79)
        for printer in sorted(results.items(), key=lambda item: socket.inet_aton(item[0])):
          output().discover(printer)
      else:
        output().info("No printers found via SNMP broadcast")
      if usage or results: print("")
    except Exception as e:
      output().errmsg("SNMP Error", e)
      if usage: print("")

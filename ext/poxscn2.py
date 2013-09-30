# Copyright 2013 ARCCN

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.revent import *
from pox.lib.util import dpid_to_str
from pox.lib.util import str_to_bool
from pox.lib.recoco import Timer
from pox.lib.packet.vlan import vlan
from pox.lib.packet.dhcp import dhcp
from pox.lib.packet.arp import arp
from pox.lib.packet.lldp import lldp, chassis_id, port_id, end_tlv
from pox.lib.packet.lldp import ttl, system_description
from pox.lib.packet.ethernet import ethernet
from pox.lib.addresses import EthAddr

import pickle
import scapy
import time
import BaseHTTPServer
import threading
import re
import json
import sqlite3 as db

#TODO: GLOBALLY
#TODO: -) Add comments to all functions and classes

# Logger initialization
log = core.getLogger()

# HTTP Server options
HOST_NAME = 'localhost'
PORT_NUMBER = 8008

ORC_HTTP_TIMER_INTERVAL = 2


class ExchangeServer():
  """Class for exchanging information between HTTP server and SDN APP."""

  def __init__(self):
    """Exchange server initialization."""
    self.data = []
    self.critical = threading.BoundedSemaphore(value=1)

  def push_data(self, string_data):
    """Push data to exchange server.

    Keyword arguments:
    string_data -- the pushed data string

    """
    self.critical.acquire()
    self.data.append(string_data)
    self.critical.release()

  def pop_data(self):
    """Pop data from exchange server and return the data string."""
    self.critical.acquire()
    data = self.data.pop(0)
    self.critical.release()
    return data

  def get_len(self):
    """Get number of buffered strings on exchange server."""
    self.critical.acquire()
    length = len(self.data)
    self.critical.release()
    return length


# Exchange server initialization.
ex_ser = ExchangeServer()


class OrchestratorHandler(BaseHTTPServer.BaseHTTPRequestHandler):
  """Handler Class for HTTP server requests processing form Orchestrator."""

  def do_HEAD(self):
    """Process HEAD request."""
    self.send_response(200)
    self.send_header("Content-type", "text/html")
    self.end_headers()

  def do_GET(self):
    """Process GET request."""
    self.send_response(200)

  def do_POST(self):
    """Process POST request."""
    global  ex_ser

    # Read and parse POST request string
    req_line = self.requestline
    req_words = re.split(' ',req_line)
    method = req_words[0]
    data_len = int(self.headers['Content-Length'])
    data_string = self.rfile.read(data_len)
    # Send parsed data to the exchange server
    ex_ser.push_data(method + " " + data_string)

    # Answer OK
    self.send_response(200)

  def do_DELETE(self):
    """Process DELETE request."""
    global  ex_ser

    # Read and parse DELETE request string
    req_line = self.requestline
    req_words = re.split(' ',req_line)
    method = req_words[0]
    data_string = req_words[1]

    # Send parsed data to the exchange server
    ex_ser.push_data(method + " " + data_string)

    # Answer OK
    self.send_response(200)


class OrcestratorHttpServer(threading.Thread):
  """HTTP server Class for relieving information from Orchestrator.
  Inherits Thread Class. Execute in single thread.
  """

  def __init__(self):
    """HTTP server initialization."""
    threading.Thread.__init__(self)
    self.server_class = BaseHTTPServer.HTTPServer
    self.httpd = self.server_class((HOST_NAME, PORT_NUMBER), OrchestratorHandler)
    self.start()

  def run(self):
    """Runs server main loop."""
    log.info(time.asctime() + " Orchestrator Communication Server Starts - %s:%s" % (HOST_NAME, PORT_NUMBER))
    try:
      self.httpd.serve_forever()
    except KeyboardInterrupt:
      pass
    self.httpd.server_close()
    log.info(time.asctime() + " Orchestrator Communication Server Stops - %s:%s" % (HOST_NAME, PORT_NUMBER))


class VDC_APP(EventMixin):
  """Virtual data center control application Class.
    Inherits EventMixin Class to receive Openflow events from POX core.
  """

  def __init__ (self):
    """Virtual data center control application initialization."""
    # Listen to ALL Openflow events from POX core.
    self.listenTo(core.openflow)

    # Initialize active connections to Openflow switches table.
    self.swTable = {}
    
    self.vidTable = {}

    # Initialize timer for HTTP server status update.
    self.timer = Timer(ORC_HTTP_TIMER_INTERVAL, self.handler_orc_ex_timer)

    # Start HTTP server for communication with Orchestrator
    OrcestratorHttpServer()

    self.macToPort = {}
    self.routes = []
    self.dpid = ''

  #TODO: Why reccuring Timer not working - POX?! WTF!?
  def handler_orc_ex_timer(self):
    """Handle timer event. Exchanging information with HTTP server."""
    while ex_ser.get_len() > 0:
      s = ex_ser.pop_data() # get action plus data string
      s = re.split(" ",s) # split action and data
      data = s[1]
      action = s[0]
      self.processing_data_from_orc(data, action)

    # Define new timer. Cos regular timer in this POX version does not want to work.
    self.timer = Timer(ORC_HTTP_TIMER_INTERVAL, self.handler_orc_ex_timer)

  def processing_data_from_orc(self, data, action):
    """Process data from Orchestrator.

    Keyword arguments:
    data   -- the information about virtual data centers
    action -- action to do with virtual data center

    """

    def delete_routes(porta, portb):
      for_del=[]
      for i in self.routes:
#         print i, porta, portb
         if (porta == i[0] and portb == i[2]) or porta == i[2] and portb == i[0]:
             msg = of.ofp_flow_mod(command=of.OFPFC_DELETE)
             print i[0],i[1],i[2],i[3]
#             msg.match.in_port = i[0]
             msg.match.dl_dst = i[3]
             msg.match.dl_src = i[1]
             self.swTable[self.dpid].send(msg)
             for_del.append(i)
      for i in for_del:
         self.routes.remove(i)
      print self.routes, porta, portb    

    def listdelports(port, vid):
      list = []
      old_ports = []
      new_ports = []
      print port, vid, "deleted", self.vidTable
      for i in self.vidTable:
       if port in self.vidTable[i]:
         for j in self.vidTable[i]:
             if j != port and j not in old_ports:
                old_ports.append(j)
             if j != port and j not in new_ports and i != vid:
                new_ports.append(j)
      for i in old_ports:
        if i not in new_ports:
          list.append(i)
      return list

    print data, action, "orc"
    if action == "POST":
      json_data = json.loads(data)
      vid = int(json_data['vid'])
      if 'add' in json_data:
          port = int(json_data['add'])

          if vid in self.vidTable:
            if port not in self.vidTable[vid]:
              self.vidTable[vid].append(port)
          else:
              self.vidTable[vid] = [port]
      elif 'del' in json_data:
          port = int(json_data['del'])
          list_del = listdelports(port, vid)
          for i in list_del:
             delete_routes(port, i)
#             delete_routes(i, port)
          if vid in self.vidTable:
            if port in self.vidTable[vid]:
              index=self.vidTable[vid].index(port)
              del self.vidTable[vid][index]
      else:
          return
      print self.vidTable


  def _handle_ConnectionUp (self, event):
    """Handle ConnectionUp event

    Keyword arguments:
    event -- Openflow event

    """

    log.debug("Connection to " + dpid_to_str(event.dpid))
    self.swTable[dpid_to_str(event.dpid)] = event.connection

    # Create ofp_flow_mod message to delete all flows
    msg = of.ofp_flow_mod(command=of.OFPFC_DELETE)
    self.swTable[dpid_to_str(event.dpid)].send(msg)
    self.dpid = dpid_to_str(event.dpid)


  def _handle_ConnectionDown (self, event):
    """Handle ConnectionDown event

    Keyword arguments:
    event -- Openflow event

    """
    log.debug("Connection closed with " + dpid_to_str(event.dpid))
    del self.swTable[dpid_to_str(event.dpid)]


  def _handle_PacketIn(self, event):
    """Handle PacketIn event

    Keyword arguments:
    event -- Openflow event

    """
    packet = event.parse()


    def possible_ports():
      ports = []
      ports_clear = []
      for port in self.vidTable:
         if event.port in self.vidTable[port]:
            ports = ports + self.vidTable[port]
      while event.port in ports:
         ports.remove(event.port)
      for p in ports:
        if p not in ports_clear:
          ports_clear.append(p)
      return ports_clear

    def flood ():
      """ Floods the packet """
      ports = possible_ports()
      if len(ports) > 0 :
         msg = of.ofp_packet_out()
         for action in ports:
            msg.actions.append(of.ofp_action_output(port = action))
         msg.data = event.ofp
         msg.in_port = event.port
         self.swTable[dpid_to_str(event.dpid)].send(msg)
         print "Flood to ", ports

    def install_route():
      ports = possible_ports()
      port = self.macToPort[packet.dst]
      if port in ports:
        print "Route installed to", port, packet.dst, "from", packet.src
        msg = of.ofp_flow_mod()
        msg.match.dl_dst = packet.dst
        msg.match.dl_src = packet.src
        msg.match.in_port = event.port
        msg.buffer_id = event.ofp.buffer_id
        msg.actions.append(of.ofp_action_output(port = port))
        self.swTable[dpid_to_str(event.dpid)].send(msg)
        if [event.port, packet.src, port, packet.dst] not in self.routes:
           self.routes.append([event.port, packet.src, port, packet.dst])
        print self.routes
      
    self.macToPort[packet.src] = event.port
    if packet.dst.is_multicast:
      flood() # 3a
    else:
      if packet.dst not in self.macToPort: # 4
        flood()
      else:
        install_route()
    #else:
    #  if packet.dst not in self.macToPort: # 4
    #    flood("Port for %s unknown -- flooding" % (packet.dst,)) # 4a
    #  else:
    #    port = self.macToPort[packet.dst]
    


def launch():
  """Launch virtual data center controlled application."""
  core.registerNew(VDC_APP)




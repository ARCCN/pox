# Copyright 2013 ARCCN 


from pox.core import core
import pox
import pox.openflow.libopenflow_01 as of
import pox.lib.packet as pkt
from pox.lib.addresses import EthAddr
from pox.lib.addresses import IPAddr
from pox.lib.revent import *
from pox.lib.util import dpid_to_str
import sqlite3 as db

log = core.getLogger()

cl_net=["172.16.1.","172.16.2."]
lb_ip="172.16.3.2"
LAN_IP=["172.16.1.1","172.16.2.1","172.16.3.1"]
LAN_MAC="02:00:DE:AD:BE:EF"

class l3_router (EventMixin):

 def __init__ (self):
    # For each switch, we map IP addresses to Entries
    self.macToPort = {}
    self.ipTomac = {}
    self.macBuffId = {}
    self.listenTo(core)
    #self.listenTo(connection)
    self.swTable = {}
    self.srvMacs = []
    self.num = 0
    self.rules = {}
    self.srvPorts = []

 def _handle_GoingUpEvent (self, event):
    self.listenTo(core.openflow)
    log.debug("Up...")

 def _handle_PortStatus (self, event):
    print "+++++++New state port+++++++++", event.ofp.desc.state
    if event.ofp.desc.state == 0 or event.ofp.desc.state == 512:
      print "Port action", event.port, event.dpid, "connection up"
      self.arp_send(dpid_to_str(event.dpid), IPAddr(lb_ip))
      print("***SRV ports=", self.list_srv_ports())

    else:
      print "Port action", event.port, event.dpid, "connection down" 
      print self.rules
      for_del_keys=[]
      for i in self.macToPort:
         if self.macToPort[i] == event.port:
            print i, event.port
            for_del_keys.append(i)
            #del self.macToPort[i]
            if i in self.srvMacs:
               self.srvMacs.remove(i)
      if event.port in self.rules:
       for i in self.rules[event.port]:
         msg = of.ofp_flow_mod(command=of.OFPFC_DELETE)
         print i, "src_deleted"
         msg.match.nw_src = i
         msg.match.dl_type = 0x800
         self.swTable[dpid_to_str(event.dpid)].send(msg)
    
      for i in for_del_keys:
         del self.macToPort[i]
      if event.port in self.rules:
         del self.rules[event.port]
      print("***SRV ports=", self.list_srv_ports())

 def list_srv_ports (self):
    srv_ports=[]
    for i in self.srvMacs:
        srv_ports.append(self.macToPort[i])
    print self.srvMacs, self.macToPort
    return srv_ports

 def to_server_rule (self, nw_src, mac, event):
         msg = of.ofp_flow_mod()
         msg.match.dl_type = 0x800
         msg.match.nw_dst = IPAddr(lb_ip)
         msg.match.nw_src = nw_src
         print(mac)
         action = of.ofp_action_dl_addr.set_dst(mac)
         msg.actions.append(action)
         action = of.ofp_action_dl_addr.set_src(EthAddr(LAN_MAC))
         msg.actions.append(action)
         msg.actions.append(of.ofp_action_output(port = self.macToPort.get(mac)))
         msg.actions.append(action)

         event.connection.send(msg)


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
    
     
    # Create init flows
#    msg = of.ofp_flow_mod()
#    msg.actions.append(of.ofp_action_output(port = of.))
#    self.swTable[dpid_to_str(event.dpid)].send(msg)


 def arp_send (self, dpid, dst):
         print("ARP flood send", dst)
         arp_reply = pkt.arp()
         arp_reply.hwsrc = EthAddr(LAN_MAC)
         arp_reply.hwdst = EthAddr("00:00:00:00:00:00") #packet.src
         arp_reply.opcode = pkt.arp.REQUEST
         arp_reply.protodst = dst
         print(dst)
         for key in range(len(LAN_IP)):
              ip = LAN_IP[key]
              if arp_reply.protodst.inNetwork(ip[:ip.rfind(".")]+".0"):
                                        #NETWORKS[key]):
                 arp_reply.protosrc = IPAddr(ip)
         ether = pkt.ethernet()
         ether.type = pkt.ethernet.ARP_TYPE
         ether.dst = EthAddr("FF:FF:FF:FF:FF:FF")
         ether.src = EthAddr(LAN_MAC)
         ether.payload = arp_reply
         msg = of.ofp_packet_out()
         msg.data = ether.pack()
         msg.actions.append(of.ofp_action_output(port = of.OFPP_ALL))
         msg.in_port = of.OFPP_NONE
         #self.macBuffId[packet.find("ipv4").dstip]=event.ofp.buffer_id
         #print(event.ofp.buffer_id)
         self.swTable[dpid].send(msg)


 def move_rules(self, rules_to_move, event):
   print rules_to_move, event.port
   for j in self.macToPort:
      print(j, self.srvMacs)
      if j in self.srvMacs and event.port == self.macToPort[j]:
            print "MAC = ", j
            mac = j
   
   for i in rules_to_move:
      del self.rules[i][0]
      self.to_server_rule(rules_to_move[i], mac, event)
      if event.port in self.rules:
             self.rules[event.port].append(rules_to_move[i])
      else:
             self.rules[event.port]=[rules_to_move[i]]

 def update_rules(self,event):
   print self.rules, self.srvMacs, "<Optim>"
   middle=0.0
   ports=self.list_srv_ports()
   for i in ports:
       if self.rules.has_key(i):
          num = len(self.rules[i])
       else:
          num = 0
       middle = middle + num
   middle = middle/len(ports)
   rules_to_move = {}
   for i in ports:
       if self.rules.has_key(i):
          if len(self.rules[i]) >= (middle + 1):
             rules_to_move[i] = self.rules[i][0]
   if len(rules_to_move) > 0:
      self.move_rules(rules_to_move, event)

 def _handle_PacketIn (self, event):
  dpid = event.connection.dpid
  inport = event.port
  packet = event.parsed
  if not packet.parsed:
      log.warning("%i %i ignoring unparsed packet", dpid, inport)
      return

  if inport != 0:
      self.macToPort[packet.src] = inport
 # print(self.macToPort.keys(), inport)
  
  print("Packet_in", inport, packet.src, packet.dst)
  if packet.type == packet.ARP_TYPE:
    # Reply to ARP
    a = packet.find("arp")
    if (a.hwdst == EthAddr(LAN_MAC)) and (a.opcode == a.REPLY):
     #   print("Arp reply") 
        inport = event.port
        self.ipTomac[a.protosrc]=a.hwsrc
        print("Arp reply", a.protosrc, a.hwsrc, dpid, inport)
        if a.protosrc == lb_ip and not(a.hwsrc in self.srvMacs):
#            if a.hwsrc not in self.srvMacs:
               l = len(self.srvMacs)
               self.srvMacs.append(a.hwsrc) 
               if len(self.srvMacs) > l:
                  print("-------------NUM of srv's updated-------------")
                  print("SRV_mac=", self.srvMacs)
                  self.update_rules(event)
         

    for key in range(len(LAN_IP)):
      if (LAN_IP[key] == a.protodst) and (a.opcode == a.REQUEST):
        r = pkt.arp()
        r.hwtype = a.hwtype
        r.prototype = a.prototype
        r.hwlen = a.hwlen
        r.protolen = a.protolen
        r.opcode = r.REPLY
        r.hwdst = a.hwsrc
        r.protodst = a.protosrc
        r.protosrc = a.protodst
        r.hwsrc = EthAddr(LAN_MAC)
        e = pkt.ethernet(type=packet.type, src=r.hwsrc, dst=a.hwsrc)
        e.payload = r

        msg = of.ofp_packet_out()
        msg.data = e.pack()
        msg.actions.append(of.ofp_action_output(port = of.OFPP_IN_PORT))
        msg.in_port = event.port
        event.connection.send(msg)
        self.ipTomac[a.protosrc]=a.hwsrc
        log.info("%s ARPed for %s", r.protodst, r.protosrc)
 
  elif packet.find("icmp"):
    mypacket='false'
    for key in range(len(LAN_IP)):
      if (LAN_IP[key] == packet.find("ipv4").dstip): 
       # Reply to pings

       # Make the ping reply
       icmp = pkt.icmp()
       icmp.type = pkt.TYPE_ECHO_REPLY
       icmp.payload = packet.find("icmp").payload

       # Make the IP packet around it
       ipp = pkt.ipv4()
       ipp.protocol = ipp.ICMP_PROTOCOL
       ipp.srcip = packet.find("ipv4").dstip
       ipp.dstip = packet.find("ipv4").srcip

       # Ethernet around that...
       e = pkt.ethernet()
       e.src = packet.dst
       e.dst = packet.src
       e.type = e.IP_TYPE

       # Hook them up...
       ipp.payload = icmp
       e.payload = ipp

       # Send it back to the input port
       msg = of.ofp_packet_out()
       msg.actions.append(of.ofp_action_output(port = of.OFPP_IN_PORT))
       msg.data = e.pack()
       msg.in_port = event.port
       event.connection.send(msg)
       mypacket = 'true'
       log.debug("%s pinged %s", ipp.dstip, ipp.srcip)

    if mypacket == 'false':
       print('Need to arp')
       print(self.ipTomac.keys(), self.macToPort.keys())
       mac=self.ipTomac.get(packet.find("ipv4").dstip)
       if packet.find("ipv4").dstip in self.ipTomac:
         print("Install Route")
         ip_addr=packet.find("ipv4").dstip
         if ip_addr == lb_ip:
           if len(self.srvMacs) > 0:
             print("srv_macs==", self.srvMacs)
             mac = self.srvMacs[self.num]
             if self.num < (len(self.srvMacs)-1):
                self.num = self.num+1
             else:
                self.num = 0
           else:
             self.arp_send(dpid_to_str(event.dpid), packet.find("ipv4").dstip)
             return 

         msg = of.ofp_flow_mod()
         msg.match.dl_type = 0x800
         msg.match.nw_dst = packet.find("ipv4").dstip
         msg.match.nw_src = packet.find("ipv4").srcip

         action = of.ofp_action_dl_addr.set_dst(mac)
         msg.actions.append(action)
         action = of.ofp_action_dl_addr.set_src(EthAddr(LAN_MAC))
         msg.actions.append(action)
         msg.actions.append(of.ofp_action_output(port = self.macToPort.get(mac)))
         msg.actions.append(action)
         #msg.buffer_id = self.macBuffId[packet.find("ipv4").dstip]
         #print(self.macBuffId)
         #self.macBuffId[packet.find("ipv4").dstip]=0
         #msg.hard_timeout = 30
         if self.macToPort.get(mac) in self.rules:
             self.rules[self.macToPort.get(mac)].append(msg.match.nw_src)
         else:
             self.rules[self.macToPort.get(mac)]=[msg.match.nw_src]

         event.connection.send(msg)
         print("Send action mac renew OK*****")
       else:
         self.arp_send(dpid_to_str(event.dpid), packet.find("ipv4").dstip)



def launch ():

  core.registerNew(l3_router)
  log.info("l3 component running.")

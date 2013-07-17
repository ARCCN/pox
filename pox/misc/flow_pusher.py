# Copyright 2013 ARCCN
#
# POX is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# POX is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with POX.  If not, see <http://www.gnu.org/licenses/>.


cfg_filename = ''

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.revent import EventMixin
from pox.lib.util import dpid_to_str
from pox.lib.addresses import *
import re

log = core.getLogger()

class flow_pusher (EventMixin):

 def __init__ (self):
   self.listenTo(core.openflow)
   self.msgQueue = []
   self.connections = {}
   
   cfg = open(cfg_filename, 'r')
   for line in cfg :
     msg = of.ofp_flow_mod()
     #print msg
     fields = line.split(' ')
     for field in fields :
       opt = field.split('=')
       
       if opt[0] == 'switch' :
         dpid = int(opt[1])
     
       #Match
       elif opt[0] == 'in_port' :
         msg.match.in_port = int(opt[1])
       elif opt[0] == 'dl_src' :
         msg.match.dl_src = EthAddr(opt[1])
       elif opt[0] == 'dl_dst' :
         msg.match.dl_dst = EthAddr(opt[1])
       elif opt[0] == 'dl_vlan' :
         msg.match.dl_vlan = int(opt[1])
       elif opt[0] == 'dl_vlan_pcp' :
         msg.match.dl_vlan_pcp = int(opt[1])
       elif opt[0] == 'dl_type' :
         msg.match.dl_type = int(opt[1],16)
       elif opt[0] == 'nw_tos' :
         msg.match.nw_tos = int(opt[1])
       elif opt[0] == 'nw_proto' :
         msg.match.nw_proto = int(opt[1])
       elif opt[0] == 'nw_src' :
         msg.match.nw_src = opt[1]
       elif opt[0] == 'nw_dst' :
         msg.match.nw_dst = opt[1]
       elif opt[0] == 'tp_src' :
         msg.match.tp_src = int(opt[1])
       elif opt[0] == 'tp_dst' :
         msg.match.tp_dst = int(opt[1])
       
       # Action
       elif opt[0] == 'cookie' :
         msg.cookie = int(opt[1])
       elif opt[0] == 'command' :
         msg.command = of.ofp_flow_mod_command_rev_map[opt[1]]
       elif opt[0] == 'idle_timeout' :
         msg.idle_timeout = int(opt[1])
       elif opt[0] == 'hard_timeout' :
         msg.hard_timeout = int(opt[1])
       elif opt[0] == 'priority' :
         msg.priority = int(opt[1])
       elif opt[0] == 'buffer_id' :
         msg.buffer_id = int(opt[1])
       elif opt[0] == 'out_port' :
         msg.out_port = int(opt[1])
       elif opt[0] == 'flags' :
         msg.flags = of.ofp_flow_mod_flags_rev_map[opt[1]]
       elif opt[0] == 'actions' :
           opt = opt[1].split(':')
           if opt[0] == 'OFPAT_OUTPUT' :
             if re.search('OFPP', opt[1]) :
               port = of.ofp_port_rev_map[opt[1]]
             else :
               port = int(opt[1])
             action = of.ofp_action_output(port=port)
           elif opt[0] == 'OFPAT_SET_VLAN_VID' :
             vlan_vid = int(opt[1])
             action = of.ofp_action_vlan_vid(vlan_vid=vlan_vid)
           elif opt[0] == 'OFPAT_SET_VLAN_PCP' :
             vlan_pcp = int(opt[1])
             action = of.ofp_action_vlan_pcp(vlan_pcp=vlan_pcp)
           elif opt[0] == 'OFPAT_SET_DL_SRC' :
             dl_addr = EthAddr(opt[1])
             action = of.ofp_action_dl_addr.set_src(dl_addr)
           elif opt[0] == 'OFPAT_SET_DL_DST' :
             dl_addr = EthAddr(opt[1])
             action = of.ofp_action_dl_addr.set_dst(dl_addr)
           elif opt[0] == 'OFPAT_SET_NW_SRC' :
             nw_addr = IPAddr(opt[1])
             action = of.ofp_action_nw_addr.set_src(nw_addr)
           elif opt[0] == 'OFPAT_SET_NW_DST' :
             nw_addr = IPAddr(opt[1])
             action = of.ofp_action_nw_addr.set_dst(nw_addr)
           elif opt[0] == 'OFPAT_SET_NW_TOS' :
             nw_tos = int(opt[1])
             action = of.ofp_action_nw_tos(nw_tos=nw_tos)
           elif opt[0] == 'OFPAT_SET_TP_SRC' :
             tp_port = int(opt[1])
             action = of.ofp_action_tp_port.set_src(tp_port)
           elif opt[0] == 'OFPAT_SET_TP_DST' :
             tp_port = int(opt[1])
             action = of.ofp_action_tp_port.set_dst(tp_port)
           elif opt[0] == 'OFPAT_ENQUEUE' :
             port = int(opt[1])
             queue_id = int(opt[2])
             action = of.ofp_action_enqueue(port=port,queue_id=queue_id)
           
           msg.actions.append(action) 
       
     if dpid in self.connections.keys() :
       connections[dpid].send(msg)
     else :
       self.msgQueue.append((dpid,msg))
       

 def _handle_ConnectionUp (self, event):
    log.debug("Connection to " + dpid_to_str(event.dpid))
    self.connections[dpid_to_str(event.dpid)] = event.connection
    
    for dpid, msg in self.msgQueue :
      if dpid == event.dpid :
        event.connection.send(msg)
    
 def _handle_ConnectionDown (self, event):
    log.debug("Disconnected: " + dpid_to_str(event.dpid))
    del self.connections[dpid_to_str(event.dpid)]
   
    

def launch (cfg = 'flows.cfg'):
  global cfg_filename
  cfg_filename = cfg
  core.registerNew(flow_pusher)


"""
This module provide l2-routing functions. Can be used with different
strategies of installing path:
(1) With barriers. 
    The path will be completely installed, when we received 
    all BarrierIn messages from switches, where we installed path
(2) Without barriers with reinstalling path. 
    For each Packet In message we install all path, if needed
(3) Without barriers with reinstalling only next hop rules. 
    For each Packet In message we install only next hop rules
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.revent import *
from pox.lib.recoco import Timer
from pox.openflow.discovery import Discovery
from pox.lib.util import dpid_to_str
import time
import topo as to

log = core.getLogger()

FLOW_IDLE_TIMEOUT = 10
FLOW_HARD_TIMEOUT = 30
PATH_SETUP_TIME = 40

class WaitingPath (object):
    """
    A path which is waiting for its path to be established.
    Used to implement barriers strategy.
    """
    
    def __init__(self, path, packet, waiting_paths):
        """
        xids is a sequence of (dpid, xid)
        first_switch is the DPID where the packet came from
        xid - transaction id associated with this packet.
        Replies use the same id as was in the request
        to facilitate pairing.
        path is a sequence of tuples (switch, in_port, out_port)
        """

        self.expires_at = time.time() + PATH_SETUP_TIME
        self.path = path
        self.first_switch = path[0][0].dpid
        self.xids = set()
        self.packet = packet
        self.waiting_paths = waiting_paths

    def add_xid(self, dpid, xid):
        self.xids.add((dpid, xid))
        self.waiting_paths[(dpid, xid)] = self

    @property
    def is_expired(self):
        return time.time() >= self.expires_at

    def notify(self, event):
        """
        Called when a barrier has been received.
        Send PacketOut message if all barriers has been received.
        """
        self.xids.discard((event.dpid, event.xid))
        if len(self.xids) == 0:
            if self.packet:
                log.debug("Sending delayed packet out %s"
                      % (dpid_to_str(self.first_switch),))
                msg = of.ofp_packet_out(data=self.packet,
                    action=of.ofp_action_output(port=of.OFPP_TABLE))
                core.openflow.sendToDPID(self.first_switch, msg)

            core.dynamic_routing.raiseEvent(PathInstalled(self.path))


class PathInstalled (Event):

    def __init__(self, path):
        Event.__init__(self)
        self.path = path


class Switch (EventMixin):
    """
    Class corresponds to a switch, connected to the controller.
    Used to handle PacketIn messages and install paths.
    """

    def __init__ (self):
        """Switch class instance use information about path installation strategy"""
        self.connection = None
        self.ports = None
        self.dpid = None
        self._listeners = None
        self._connected_at = None

    def __repr__ (self):
        return dpid_to_str(self.dpid)

    
    def _install (self, in_port, out_port, match, buf = None):
        """Install rule to the switch"""
        msg = of.ofp_flow_mod()
        msg.match = match
        msg.match.in_port = in_port
        msg.idle_timeout = FLOW_IDLE_TIMEOUT
        msg.hard_timeout = FLOW_HARD_TIMEOUT
        msg.actions.append(of.ofp_action_output(port = out_port))
        msg.buffer_id = buf
        self.connection.send(msg)

    def disconnect(self):
        if self.connection is not None:
            log.debug("Disconnect %s" % (self.connection,))
            self.connection.removeListeners(self._listeners)
            self.connection = None
            self._listeners = None

    def connect(self, connection):
        if self.dpid is None:
            self.dpid = connection.dpid
        assert self.dpid == connection.dpid
        if self.ports is None:
            self.ports = connection.features.ports
        self.disconnect()
        log.debug("Connect %s" % (connection,))
        self.connection = connection
        self._listeners = self.listenTo(connection)
        self._connected_at = time.time()


class dynamic_routing (EventMixin):
    """
    Module main class. It's functions:
    (1) Initiate updates in routing algorithm network representation:
    - Handle LinkEvents messages, and
    - Handle ConnectionUp/Down messages;
    (2) Receive information about ports bandwidth:
    - Handle BarrierIn messages
    """
    _eventMixin_events = set([PathInstalled,])
    def __init__(self, barrier, next_hop):
        """
        Subscribe to modules and initiate routing class instance.
        """
        #map (switch, port) to bandwith
        self.bw_map = {}
        #map switch dpid to switch
        self.switches = {}
        #map MAC to pair (switch_dpid, switch_port)
        self.mac_map = {}
        #map edge (src, dst) to (src_port, dst_port)
        self.link_map = {}
        # Waiting path.  (dpid,xid)->WaitingPath
        self.waiting_paths = {}
        #default link weight
        self.default_weight = 1
        self.routing = to.Topology()
        self.barrier = barrier
        self.next_hop = next_hop

        def startup():
            core.openflow.addListeners(self, priority=0)
            core.openflow_discovery.addListeners(self)

        core.call_when_ready(startup, ('openflow','openflow_discovery'))
    
    def raw_path(self, dpid1, port1, dpid2, port2):
        """Get path from the routing algorithm and convert each node in the path
        into tuple: (node, in_port, out_port).
        """
        path = self.routing.make_path(dpid1, dpid2)
        if path == None: 
            return
        port = port1
        raw_path = []
        i = 0
        while i < len(path) - 1:
            raw_path.append((self.switches[path[i]], port, self.link_map[(path[i], path[i+1])][0],))
            port = self.link_map[(path[i], path[i+1])][1]
            i += 1
        raw_path.append((self.switches[dpid2], port, port2,))
        return raw_path

    def _install_path (self, p, match, packet_in=None):
        """Install path p, using preferred strategy"""
        first_switch = p[0][0]
        if self.barrier == "True":
            wp = WaitingPath(p, packet_in, self.waiting_paths)
            rev_path = p[:]
            rev_path.reverse()
            for sw, in_port, out_port in rev_path:
                sw._install(in_port, out_port, match)
                msg = of.ofp_barrier_request()
                sw.connection.send(msg)
                wp.add_xid(sw.dpid,msg.xid)
        else:
            if self.next_hop == "True":
                for sw,in_port,out_port in p:
                    sw._install(in_port, out_port, match)
                    break
                msg = of.ofp_packet_out(data=packet_in,
                action=of.ofp_action_output(port=of.OFPP_TABLE))
                core.openflow.sendToDPID(first_switch.dpid, msg)
                return
            else:
                for sw,in_port,out_port in p:
                    sw._install(in_port, out_port, match)
                msg = of.ofp_packet_out(data=packet_in,
                action=of.ofp_action_output(port=of.OFPP_TABLE))
                core.openflow.sendToDPID(first_switch.dpid, msg)
                return
                
    def install_path (self, src_sw, dst_sw, last_port, match, event):
        """
        Attempts to install a path between this switch and some destination
        """
        p = self.raw_path(src_sw.dpid, event.port, dst_sw.dpid, last_port)
        if not p:
            log.warning("Can't get from %s to %s", match.dl_src, match.dl_dst)

            import pox.lib.packet as pkt

            if (match.dl_type == pkt.ethernet.IP_TYPE and
                event.parsed.find('ipv4')):
                # It's IP -- let's send a destination unreachable
                log.debug("Dest unreachable (%s -> %s)",
                      match.dl_src, match.dl_dst)

                from pox.lib.addresses import EthAddr
                e = pkt.ethernet()
                e.src = EthAddr(dpid_to_str(src_sw.dpid))
                e.dst = match.dl_src
                e.type = e.IP_TYPE
                ipp = pkt.ipv4()
                ipp.protocol = ipp.ICMP_PROTOCOL
                ipp.srcip = match.nw_dst
                ipp.dstip = match.nw_src
                icmp = pkt.icmp()
                icmp.type = pkt.ICMP.TYPE_DEST_UNREACH
                icmp.code = pkt.ICMP.CODE_UNREACH_HOST
                orig_ip = event.parsed.find('ipv4')

                d = orig_ip.pack()
                d = d[:orig_ip.hl * 4 + 8]
                import struct
                d = struct.pack("!HH", 0,0) + d
                icmp.payload = d
                ipp.payload = icmp
                e.payload = ipp
                msg = of.ofp_packet_out()
                msg.actions.append(of.ofp_action_output(port = event.port))
                msg.data = e.pack()
                src_sw.connection.send(msg)

            return
        
        # We have a path -- install it
        self._install_path(p, match, event.ofp)

        # Now reverse it and install it backwards
        # (we'll just assume that will work)
        p = [(sw,out_port,in_port) for sw,in_port,out_port in p]
        self._install_path(p, match.flip())


    def _handle_PacketIn (self, event):
        """Handle PacketIn message and initiates installing path process if needed"""

        def flood ():
            """ Floods the packet """
            msg = of.ofp_packet_out()
            # OFPP_FLOOD is optional; some switches may need OFPP_ALL
            msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
            msg.buffer_id = event.ofp.buffer_id
            msg.in_port = event.port
            event.connection.send(msg)

        def drop ():
            """Drops the packet"""
            # Kill the buffer
            if event.ofp.buffer_id is not None:
                msg = of.ofp_packet_out()
                msg.buffer_id = event.ofp.buffer_id
                event.ofp.buffer_id = None
                msg.in_port = event.port
                event.connection.send(msg)

        if event.dpid in self.switches:
            switch_src = self.switches[event.dpid]
        else:
            drop()
            return

        packet = event.parsed
        if packet.effective_ethertype == packet.LLDP_TYPE:
            drop()
            return

        loc = (switch_src, event.port)
        oldloc = self.mac_map.get(packet.src)
        #print loc
        #print oldloc
        #print "-------------------------------------------------"
        if oldloc is None:
            # ethaddr unknown
            if packet.src.is_multicast == False:
                self.mac_map[packet.src] = loc # Learn position for ethaddr
                log.debug("Learned %s at %s.%i", packet.src, loc[0], loc[1])
        elif oldloc != loc:
            # ethaddr seen at different place!
            flag = True
            for key in self.link_map:
                if (key[0], self.link_map[key][0]) == (loc[0].dpid, loc[1]) or \
                (key[1], self.link_map[key][1]) == (loc[0].dpid, loc[1]):
                    flag = False
            if flag:        
                if packet.src.is_multicast == False:
                      self.mac_map[packet.src] = loc # Learn position for ethaddr
                      log.debug("Learned %s at %s.%i", packet.src, loc[0], loc[1])
                elif packet.dst.is_multicast == False:
                # New place is a switch-to-switch port!
                    log.warning("Packet from %s arrived at %s.%i without flow",
                            packet.src, dpid_to_str(switch_src.dpid), event.port)

        if packet.dst.is_multicast:
            log.debug("Flood multicast from %s", packet.src)
            flood()
        else:
            if packet.dst not in self.mac_map:
                log.debug("%s unknown -- flooding" % (packet.dst,))
                flood()
            else:
                dest = self.mac_map[packet.dst]
                match = of.ofp_match.from_packet(packet)
                self.install_path(switch_src, dest[0], dest[1], match, event)

    def get_weight (self, struct):
        """Parse ofp_port_features structure and get information about port bandwidth"""
        if struct <= 0:
            return self.default_weight
        if (struct >> 6) > 0:
            return 1
        if (struct >> 4) > 0:
            return 10
        if (struct >> 2) > 0:
            return 100
        return 1000
        
    def _handle_ConnectionUp(self, event):
        """
        Connect switch and update self.routing
        """
        dpid = event.dpid
        sw = self.switches.get(dpid)
        for port in event.ofp.ports:
            if port.port_no <= 0xff00:
                self.bw_map[(dpid, port.port_no)] = self.get_weight(port.curr)
        if sw is None:
            sw = Switch()
            self.switches[dpid] = sw
            sw.connect(event.connection)
            self.routing.add_node(dpid)
        else:
            sw.connect(event.connection)
            log.warning("WARNING: Switch with dpid= %s already connected!!!", dpid)
        
    def _handle_ConnectionDown(self, event):
        """Disconnect switch"""
        dpid = event.connection.dpid
        sw = self.switches.get(dpid)
        if sw is None:
            log.warning("WARNING: Switch with dpid= %s already disconnected!!!", dpid)
        if dpid in self.switches:
            sw.disconnect()
            del self.switches[dpid]
        else:
            log.warning("WARNING: Switch with dpid= %s already disconnected!!!", dpid)
                
        
    def _handle_LinkEvent(self, event):
        """
        Process link add/remove event and initiates update in self.routing
        """
        if (event.link.dpid1 not in self.switches or event.link.dpid2 not in self.switches) and event.added:
            log.warning("WARNING: Can't add link. Switch doesn't exist")
            return
        if event.link.dpid1 in self.switches and event.link.dpid2 in self.switches and event.added:
            bw = min(self.bw_map[(event.link.dpid1, event.link.port1)], self.bw_map[(event.link.dpid2, event.link.port2)]) 
            self.link_map[(event.link.dpid1, event.link.dpid2)] = (event.link.port1, event.link.port2)
            self.routing.add_link(event.link.dpid1, event.link.dpid2, bw)
            return
        if event.link.dpid1 in self.switches and event.link.dpid2 in self.switches and not event.added:
            if (event.link.dpid1, event.link.dpid2) in self.link_map:
                del self.link_map[(event.link.dpid1, event.link.dpid2)]
                self.routing.remove_link(event.link.dpid1, event.link.dpid2)
            else:
                log.warning("WARNING: Trying to remove link, which doesn't exist")
                
    def _handle_BarrierIn (self, event):
        """Handle BarrierIn message and try to complete path installation"""
        wp = self.waiting_paths.pop((event.dpid, event.xid), None)
        if not wp:
            return
        wp.notify(event)
              
def launch(barrier=False, next_hop=False):
    core.registerNew(dynamic_routing, barrier, next_hop)

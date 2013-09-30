"""
Designed for Yet Another Conference 2013.
Contains a control a specialized application for POX controller.

The application suppose the following network configuration:

Network consists of two (or more switches). However, POX is connected to only one of them (s1).
External network switches provide a loop for the first pair of s1 interfaces.
Specifically, all packets that go out of s1 through its first interface return back through its second interface
with a decremented value of Time To Live field in IPv4 header (if s1 sends a packet with zero TTL, it is dropped).

There are HOST_NUM hosts connected to s1 interfaces starting from 3.
A host number X has a statically configured MAC and IP addresses in accordance with a following pattern:
host MAC:  00:00:00:00:0X:10
host IP:   10.0.X.10

Using s1 application mimics a network router that is available for a host X by the following addresses
(to achieve this application responses to ARP and ICMP requests):
s1 MAC:  00:00:00:00:00:01
s1 IP:   10.0.X.1

As a result each host is free to any of s1 IP addresses.
Although hosts are also free to ping each other, the routing in this case is quite unusual.
Upon receiving an IP packet designed for one of the other hosts, s1 sends it to the first interface with
TOS (Type of Service) field changed in accordance to a predefined number Q specific for each sender-receiver pair
(TOS value should be a multiple of 4, and is set to the value of Q multiplied by 4).

External network loops this packet to the second interface of s1 or drops it, if its TTL is zero.
Upon receiving the packet on a second interface, s1 looks to its TOS field and make one of the following actions:
1. if TOS value is not equal to zero, s1 decrements TOS by 4 and sends a packet through interface 1 once more.
2. otherwise, s1 forwards packet to its destination host.

Application implements the described loop using a set of proactive static rules.

As a result, the hop distance between hosts, as it can be found with traceroute command,
would be equal to a number of loop iterations that is set for a selected sender-receiver pair + 2.
This number is always positive due to program logic, and cannot exceed 63 due to a limited TOS field size.
Thereby, the number of hops may take value from 3 up to 65.

Application provides a user friendly gui to control the hop number.
It can be accessed with a web browser by the address http://HOST:PORT

This package includes a subsidiary file with a corresponding Mininet configuration for testing purposes.
HINT: Use traceroute -N3 to disable concurrent sending of packets with different TTL.

Author: Eugene Chemeritskiy
Email: echemeritskiy@arccn.ru
date: 26 August 2013

"""


from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.addresses import EthAddr, IPAddr
import pox.lib.packet as pkt
import control
import copy


HOST = '127.0.0.1'
PORT = 8080
BASE = 'ext/yac/html'

HOST_NUM = 3
MAX_ITER_NUM = 63
DEFAULT_PAIR_MAP = {}
for src in range(1, 1 + HOST_NUM):
    for dst in range(1, 1 + HOST_NUM):
        DEFAULT_PAIR_MAP[(src, dst)] = 3


class LoopSwitch(object):
    def __init__(self, connection):
        self.web_gui = control.WebGUI(HOST, PORT, BASE)
        self.pair_map = DEFAULT_PAIR_MAP
        self.connection = connection

        self.drop_external()
        self.set_tos_loop()
        self.withdraw_flows()
        self.tighten_flows()

        connection.addListeners(self)
        self.web_gui.start()

        core.callDelayed(1, LoopSwitch.check_updates, self)

    def drop_external(self):
        msg = of.ofp_flow_mod()
        msg.priority = 10
        msg.actions = [
            of.ofp_action_output(port=of.OFPP_NONE)
        ]
        self.connection.send(msg)

        for src in range(1, 1 + HOST_NUM):
            msg = of.ofp_flow_mod()
            msg.priority = 50
            msg.match.dl_src = EthAddr("00:00:00:00:0{}:10".format(src))
            msg.actions = [
                of.ofp_action_output(port=of.OFPP_CONTROLLER)
            ]
            self.connection.send(msg)

    def set_tos_loop(self):
        for nw_tos in range(4 * MAX_ITER_NUM, 0, -4):
            msg = of.ofp_flow_mod()
            msg.priority = 100
            msg.match.in_port = 2
            msg.match.dl_dst = EthAddr("00:00:00:00:00:01")
            msg.match.dl_type = 0x800
            msg.match.nw_tos = nw_tos
            msg.actions = [
                of.ofp_action_nw_tos(nw_tos - 4),
                of.ofp_action_output(port=1)
            ]
            self.connection.send(msg)

    def withdraw_flows(self):
        for src in range(1, 1 + HOST_NUM):
            for dst in range(1, 1 + HOST_NUM):
                if src == dst:
                    continue
                self.withdraw_flow(src, dst)

    def withdraw_flow(self, src, dst):
        msg = of.ofp_flow_mod()
        msg.priority = 100
        msg.match.in_port = 2
        msg.match.dl_src = EthAddr("00:00:00:00:0{}:10".format(src))
        msg.match.dl_dst = EthAddr("00:00:00:00:00:01")
        msg.match.dl_type = 0x800
        msg.match.nw_src = IPAddr("10.0.{}.10".format(src))
        msg.match.nw_dst = IPAddr("10.0.{}.10".format(dst))
        msg.match.nw_tos = 0
        msg.actions = [
            of.ofp_action_dl_addr.set_src(EthAddr("00:00:00:00:00:01")),
            of.ofp_action_dl_addr.set_dst(EthAddr("00:00:00:00:0{}:10".format(dst))),
            of.ofp_action_output(port=2 + dst)
        ]
        self.connection.send(msg)

    def tighten_flows(self):
        for src in range(1, 1 + HOST_NUM):
            for dst in range(1, 1 + HOST_NUM):
                if src == dst:
                    continue
                self.tighten_flow(src, dst, self.pair_map[(src, dst)])

    def tighten_flow(self, src, dst, hop_num):
        msg = of.ofp_flow_mod()
        msg.priority = 100
        msg.match.in_port = 2 + src
        msg.match.dl_src = EthAddr("00:00:00:00:0{}:10".format(src))
        msg.match.dl_dst = EthAddr("00:00:00:00:00:01")
        msg.match.dl_type = 0x800
        msg.match.nw_src = IPAddr("10.0.{}.10".format(src))
        msg.match.nw_dst = IPAddr("10.0.{}.10".format(dst))
        msg.actions = [
            of.ofp_action_nw_tos(4 * (hop_num - 2)),
            of.ofp_action_output(port=1)
        ]
        self.connection.send(msg)

    def check_updates(self):
        """Interacting with web GUI"""
        if self.web_gui.ctl_conn[0].poll():
            reply = {}

            pair_map = {}
            query = self.web_gui.ctl_conn[0].recv()
            raw = query['pair_map']

            try:
                # checking the received configuration
                for key, val in raw.items():
                    src, dst = map(int, key.split(','))
                    if min(src, dst) < 1 or HOST_NUM < max(src, dst) or src == dst:
                        raise ValueError("wrong src-dst pair")
                    val = int(val)
                    if not 3 <= val <= MAX_ITER_NUM + 2:
                        raise ValueError("wrong value")
                    pair_map[src, dst] = int(val)
                print(pair_map)

            except BaseException as e:
                reply['result'] = False
                reply['status'] = 'Wrong configuration!'
                print("exception: " + e.message)

            else:
                if pair_map == self.pair_map:
                    reply['result'] = True
                    reply['status'] = 'Specified configuration is already active!'

                else:
                    for (src, dst), hops in pair_map.items():
                        if self.pair_map[(src, dst)] != hops:
                            self.tighten_flow(src, dst, hops)
                    self.pair_map = pair_map
                    reply['result'] = True
                    reply['status'] = 'Specified configuration applied!'

            self.web_gui.srv_conn[1].send(reply)
        core.callDelayed(1, LoopSwitch.check_updates, self)

    def _handle_PacketIn(self, event):
        packet = event.parsed
        print(event.port, str(packet))

        if packet.type == packet.ARP_TYPE:
            packet_arp = packet.find("arp")
            if packet_arp.opcode == pkt.ARP.arp.REQUEST:
                my_ip = IPAddr(packet_arp.protosrc.toUnsigned() & 0xFFFFFF00 | 1)
                if my_ip == packet_arp.protodst:

                    dst_host = int((packet_arp.protosrc.toUnsigned() & 0xFF00) >> 8)

                    arp = copy.copy(packet_arp)
                    arp.opcode = pkt.ARP.arp.REPLY
                    arp.hwsrc = EthAddr("00:00:00:00:00:01")
                    arp.protosrc = packet_arp.protodst
                    arp.protodst = packet_arp.protosrc

                    e = pkt.ETHERNET.ethernet()
                    e.type = packet.type
                    e.src = EthAddr("00:00:00:00:00:01")
                    e.dst = packet_arp.hwsrc
                    e.payload = arp

                    msg = of.ofp_packet_out()
                    msg.data = e.pack()
                    msg.actions = [
                        of.ofp_action_output(port=2 + dst_host)
                    ]

                    print("reacting arp")
                    self.connection.send(msg)

        elif packet.find("icmp"):
            packet_ipv4 = packet.find("ipv4")
            if packet_ipv4.dstip.toUnsigned() & 0xFFFF00FF == IPAddr('10.0.0.1').toUnsigned():

                dst_host = int((packet_ipv4.srcip.toUnsigned() & 0xFF00) >> 8)

                icmp = pkt.ICMP.icmp()
                icmp.type = pkt.TYPE_ECHO_REPLY
                icmp.payload = packet.find("icmp").payload

                ipp = pkt.IPV4.ipv4()
                ipp.srcip = packet_ipv4.dstip
                ipp.dstip = packet_ipv4.srcip
                ipp.protocol = ipp.ICMP_PROTOCOL
                ipp.payload = icmp

                e = pkt.ETHERNET.ethernet()
                e.src = EthAddr("00:00:00:00:00:01")
                e.dst = EthAddr("00:00:00:00:0{}:10".format(dst_host))
                e.type = e.IP_TYPE
                e.payload = ipp

                msg = of.ofp_packet_out()
                msg.data = e.pack()
                msg.actions = [
                    of.ofp_action_output(port=2 + dst_host)
                ]

                print("reacting icmp")
                self.connection.send(msg)


class manager(object):
    def __init__(self):
        core.openflow.addListeners(self)

    def _handle_ConnectionUp(self, event):
        print("Connection up", event.connection)
        LoopSwitch(event.connection)


def launch():
    core.registerNew(manager)

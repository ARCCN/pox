#!/usr/bin/python
# -*- coding: utf-8 -*-


__author__ = 'Eugene Chemeritskiy'


import mininet.topo as mntopo


class Topology(mntopo.Topo):
    def __init__(self):
        mntopo.Topo.__init__(self)

        s1 = self.addSwitch('s1', ip="10.0.0.101/24")
        s2 = self.addSwitch('s2', ip="10.0.0.102/24")
        s3 = self.addSwitch('s3', ip="10.0.0.103/24")

        self.addLink(s1, s2, 1, 2)
        self.addLink(s2, s3, 1, 2)
        self.addLink(s3, s1, 1, 2)

        HOST_NUM = 3
        assert(HOST_NUM < 8)
        for x in range(1, 1 + HOST_NUM):
            name = 'h{}'.format(x)
            ip = '10.0.{}.10/24'.format(x)
            mac = '00:00:00:00:0{}:10'.format(x)
            h = self.addHost(name, ip=ip, mac=mac)
            self.addLink(s1, h, 2 + x, 1)

if __name__ == '__main__':
    # build a simple topology and feed it to Mininet

    import argparse

    parser = argparse.ArgumentParser(description='Build linear network topology and feed it to Mininet.')
    parser.add_argument('--remote', default='127.0.0.1:6633', type=str, help='ip:port of the remote controller ip')
    args = parser.parse_args()

    CTRL_IP = args.remote.split(':')[0]
    CTRL_PORT = int(args.remote.split(':')[1])

    # start Mininet with a given topology
    import mininet.node as mnnode
    import mininet.net as mnnet
    import mininet.log as mnlog

    mnlog.setLogLevel('info')
    topology = Topology()
    net = mnnet.Mininet(
        topo=topology, controller=lambda name: mnnode.RemoteController(name, ip=CTRL_IP, port=CTRL_PORT)
    )

    net.start()

    # unbind switches 2 and 3 from the controller
    import subprocess

    subprocess.call('ovs-vsctl del-controller s2'.split())
    subprocess.call('ovs-vsctl del-controller s3'.split())

    subprocess.call('ovs-ofctl add-flow s2 in_port=2,dl_type=0x0800,actions=dec_ttl,output:1'.split())
    subprocess.call('ovs-ofctl add-flow s3 in_port=2,dl_type=0x0800,actions=output:1'.split())
    subprocess.call('ovs-ofctl add-flow s3 in_port=2,dl_type=0x0800,nw_ttl=0,actions=drop'.split())

    # set default gateway for all connected hosts
    for h in net.hosts:
        n = int(h.name[1:])
        h.cmd("route add default gw 10.0.{}.1".format(n))

    # start Mininet command line
    import mininet.cli as mncli
    mncli.CLI(net)
    net.stop()
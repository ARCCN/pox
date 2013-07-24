"""
This module handles network changes and provides shortest path between any vertex pair.
We use networkx DiGraph class to maintain network topology and calculate shortest paths.
This is directed graph with weighted edges. Algorithm don't work with parallel edges.
"""

import networkx as nx
import algorithm as al


class Topology:
    """
    Class Topology provides interfaces to work with routing algorithm.
    Class functions are trivial and not documented.
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self.alg = al.DIA(self.graph)
    
    def add_node(self, n):
        self.graph.add_node(n)
        self.alg.update_DIA(self.graph)
    
    def remove_node(self, n):
        """This event is covered by link_down event"""
        return

    def add_link(self, u, v, w):
        self.graph.add_weighted_edges_from([(u, v, w)])
        self.alg.update_DIA(self.graph)
        self.alg.fully_update(u, 1)
        #self.alg.update(u, 1)
    
    def remove_link(self, u, v):
        self.graph.remove_edge(u, v)
        self.alg.update_DIA(self.graph)
        self.alg.fully_update(u, 1)
        #self.alg.update(u, 1)
        if len(self.graph.edges(u)) == 0:
            self.remove_node(u)
            
    def make_path(self, u, v):
        return self.alg.get_path(u, v)


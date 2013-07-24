"""
This module implements Demetrescu and Italiano Dynamic APSP algorithm,
described in the paper "A New Approach to Dynamic All Pairs Shortest Paths".
"""

import networkx as nx
import math


class Path:
    """
    Class represents a path between two nodes in the weighted directed graph.
    Class instance is a tuple of a path (tuple of node numbers) and a weight of the path.
    """

    def __init__(self, path = None, weight = None):
        """Initialize Path class instance with sequence of nodes and weight of path"""
        if path is None:
            self.vseq = ()
        else:
            self.vseq = path
        if weight is None:
            self.weight = -1
        else:
            self.weight = weight

    def terminals(self):
        """Return first and last nodes of the path"""
        if len(self.vseq) == 0:
            return None
        return self.vseq[0], self.vseq[-1]

def combine_left_path(path, new_vert, new_vert_weight):
    return Path((new_vert,) + path.vseq, path.weight + new_vert_weight)
        
def combine_right_path(path, new_vert, new_vert_weight):
    return Path(path.vseq + (new_vert,), path.weight + new_vert_weight)


def find_path(set_path, target):
    """Find in set_path container path equal to target path"""
    return next((x for x in set_path if x.vseq == target.vseq), None)


# TODO: why do l_path and r_path include this edge checking?
def l_path(path, G):
    """Subpath Pi(x,b) of Pi(x,y), where <b,y> is an edge"""
    if G.has_edge(path.vseq[-2], path.vseq[-1]):
        return Path(path.vseq[:-1], path.weight - G[path.vseq[-2]][path.vseq[-1]]["weight"])
    else:
        return Path(path.vseq[:-1], path.weight)


def r_path(path, G):
    """Subpath Pi(a,y) of Pi(x,y), where <a,x> is an edge"""
    if G.has_edge(path.vseq[0], path.vseq[1]):
        return Path(path.vseq[1:], path.weight - G[path.vseq[0]][path.vseq[1]]["weight"])
    else:
        return Path(path.vseq[1:], path.weight)


def min_path(set_path):
    """Returns from container set_path path with minimal weight"""
    if len(set_path) == 0:
        return Path()
    return min(set_path, key=lambda x: x.weight)


class DIA:
    """
    Class implements Demetrescu and Italiano Algorithm (DIA).
    Class instance contains list of Shortest Paths (Historical Paths),
    list of Local Shortest Paths (Local Historical Paths), their pre and post
    (left and right) extensions and a Graph for updating weights
    """

    def __init__(self, G):
        """
        SP stores all Shortest Paths for each pair of nodes;
        LSP stores all Local Shortest Paths for each pair of nodes;
        L and R stores all left and right extensions of each Shortest Path in SP;
        LL and LR stores all left and right extensions of each Local Shortest Path in LSP;
        time and v_time variables are used for smoothing strategy.
        """
        self.SP = {}
        self.LSP = {}

        self.L = {}
        self.R = {}

        self.LL = {}
        self.LR = {}

        self.time = 0
        self.v_time = {}
        
        self.G = G.copy()
        for i in self.G.nodes():
            self.v_time[i] = 0
            for j in self.G.nodes():
                self.SP[(i, j)] = []
                self.LSP[(i, j)] = []
                
    def update_DIA(self, G):
        """Update class items in response to deleting/adding graph elements"""
        old_size = self.G.number_of_nodes()
        self.G = G.copy()
        new_size = self.G.number_of_nodes()
        #if new number of nodes is less or equal to old, 
        #we don't need to initialize new lists in dictionaries
        if new_size - old_size <= 0:
            return
        for i in G.nodes():
            if i not in self.v_time:
                self.v_time[i] = self.time
            for j in G.nodes():
                if (i, j) not in self.SP:
                    self.SP[(i, j)] = []
                if (i, j) not in self.LSP:
                    self.LSP[(i, j)] = []
                    
    def remove_path(self, path_dict, key, target_path, check):
        try:
            path_dict[key].remove(target_path)
        except ValueError:
            return
        if len(path_dict[key]) == 0 and check == True:
            del path_dict[key]

    def cleanup(self, u):
        """Delete all path, including node u, from paths lists"""
        num = self.G.number_of_nodes()
        #Forming list of vertices to delete
        Q = [(u,)]
        while len(Q) != 0:
            cur_vseq = Q.pop()
            #Look for path to delete in all Local Shortest Paths left extensions
            #Deleting paths are in paths lists
            if cur_vseq in self.LL.keys():
                for path in self.LL[cur_vseq]:
                    right_path = r_path(path, self.G).vseq
                    left_path = l_path(path, self.G).vseq
                    #Append deleting path to list Q
                    #Delete path
                    Q.append(path.vseq)
                    self.remove_path(self.LSP, path.terminals(), path, False)
                    self.remove_path(self.LL, right_path, path, True)
                    self.remove_path(self.LR, left_path, path, True)
                    if path in self.SP[path.terminals()]:
                        self.remove_path(self.SP, path.terminals(), path, False)
                        self.remove_path(self.L, right_path, path, True)
                        self.remove_path(self.R, left_path, path, True)
            #Look for path to delete in all Local Shortest Paths right extensions
            #Deleting paths are in paths lists
            if cur_vseq in self.LR.keys():
                for path in self.LR[cur_vseq]:
                    right_path = r_path(path, self.G).vseq
                    left_path = l_path(path, self.G).vseq
                    Q.append(path.vseq)
                    self.remove_path(self.LSP, path.terminals(), path, False)
                    self.remove_path(self.LL, right_path, path, True)
                    self.remove_path(self.LR, left_path, path, True)
                    if path in self.SP[path.terminals()]:
                        self.remove_path(self.SP, path.terminals(), path, False)
                        self.remove_path(self.L, right_path, path, True)
                        self.remove_path(self.R, left_path, path, True)
                        
    def adjust_node(self, v, u, weight):
        path = Path((v, u), weight)
        self.LSP[(v, u)].append(path)
        if (u,) not in self.LL:
            self.LL[(u,)] = [path]
        else:
            self.LL[(u,)].append(path)
        if (v,) not in self.LR:
            self.LR[(v,)] = [path]
        else:
            self.LR[(v,)].append(path)

    def add_local_path(self, new_path, vseq_in_LL, vseq_in_RR):
        self.LSP[new_path.terminals()].append(new_path)
        if vseq_in_LL not in self.LL:
            self.LL[vseq_in_LL] = [new_path]
        else:
            self.LL[vseq_in_LL].append(new_path)
        if vseq_in_RR not in self.LR:
            self.LR[vseq_in_RR] = [new_path]
        else:
            self.LR[vseq_in_RR].append(new_path)

    def fixup(self, u, w):
        """
        Update edges of node u and create new SPs and LSPs,
        using left and right extensions.
        """
        #Phase 1
        #If updating node wasn't deleted, add all trivial (just with 1 edge) path
        if w != -1:
            for edge in self.G.out_edges(u):
                self.adjust_node(edge[0], edge[1], self.G[edge[0]][edge[1]]["weight"])
            for edge in self.G.in_edges(u):
                self.adjust_node(edge[0], edge[1], self.G[edge[0]][edge[1]]["weight"])

        # Phase 2
        # Form a list of minimum paths for each pair of nodes
        H = [min_path(x) for x in self.LSP.values() if len(x) != 0]

        # Phase 3
        # Combine paths from H to create new LSPs and SPs.
        # Each pair of nodes is handled for a single path only.
        # processed is a list of pairs of nodes that have already been handled.
        # If the pair is in the :processed, it is skipped.

        processed = set()
        while len(H) != 0:
            cur_path = min_path(H)
            H.remove(cur_path)
            r_cur = r_path(cur_path, self.G).vseq
            l_cur = l_path(cur_path, self.G).vseq
            cur_terminals = cur_path.terminals()
            if cur_terminals not in processed:
                processed.add(cur_terminals)
                #If current path isn't in list of Shortest Path, add it in Shortest paths and left/right extensions
                if cur_path not in self.SP[cur_terminals]:
                    self.SP[cur_terminals].append(cur_path)
                    if r_cur not in self.L:
                        self.L[r_cur] = [cur_path]
                    else:
                        self.L[r_cur].append(cur_path)
                    if l_cur not in self.R:
                        self.R[l_cur] = [cur_path]
                    else: 
                        self.R[l_cur].append(cur_path)                    
                    #combine new Local Shortest Paths and Shortest Paths
                    #and append new paths to H
                    for left_path in self.L.get(l_cur, []):
                        if self.G.has_edge(left_path.vseq[0], left_path.vseq[1]):
                            new_path = combine_left_path(cur_path, left_path.vseq[0], self.G[left_path.vseq[0]][left_path.vseq[1]]["weight"])
                            self.add_local_path(new_path, cur_path.vseq, left_path.vseq)
                            H.append(new_path)

                    for right_path in self.R.get(r_cur, []):
                        if self.G.has_edge(right_path.vseq[-2], right_path.vseq[-1]):
                            new_path = combine_right_path(cur_path, right_path.vseq[-1], self.G[right_path.vseq[-2]][right_path.vseq[-1]]["weight"])
                            self.add_local_path(new_path, right_path.vseq, cur_path.vseq)
                            H.append(new_path)
        
    #Update lists of paths, with node u
    def update(self, v, w):
        """Update DIA containers to maintain shortest paths in graph.
        Update called as an response to some changes with node v.
        """    
        self.cleanup(v)
        self.fixup(v, w)
    
    def fully_update(self, v, w):
        """A Fully Dynamic version of update function, used as a front-end for
        the update operations.
        """
        self.time += 1
        self.v_time[v] = self   .time
        self.update(v, w)
        for node in self.G.nodes():
            if node != v and self.v_time[node] != 0:
                diff = self.time - self.v_time[node]
                if diff > 0 and (diff & (diff - 1)) == 0:
                    self.update(node, 1)
    
    def distance(self, u, v):
        """Return weight of shortest path between nodes u and v"""
        if u == v:
            return 0
        if (u, v) in self.LSP != 0:
            return min_path(self.LSP[(u, v)]).weight
        return -1

    def get_path(self, u, v):
        """Return shortest path between nodes u and v"""
        if u == v:
            return u,
        if (u, v) in self.LSP != 0:
            return min_path(self.LSP[(u, v)]).vseq
        return None

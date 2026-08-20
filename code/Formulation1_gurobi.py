

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from graphviz import Digraph
import gurobipy as gp
import networkx as nx
from gurobipy import GRB

Vertex = str
Edge = Tuple[Vertex, Vertex]

_STATUS_NAME = {
    getattr(GRB.Status, name): name for name in dir(GRB.Status) if not name.startswith("_")
}


# --------------------------------------------------------------------------
# 1. Maximal zig-zag trail decomposition
# --------------------------------------------------------------------------

class ZigZagTrail:
    __slots__ = ("edges", "is_crown")

    def __init__(self, edges: List[Edge], is_crown: bool):
        self.edges = edges
        self.is_crown = is_crown

    def __len__(self) -> int:
        return len(self.edges)

    def __repr__(self) -> str:
        kind = "Crown" if self.is_crown else "Fence"
        return f"{kind}(len={len(self.edges)}, {self.edges})"


def zigzag_trail_decomposition(N: nx.DiGraph) -> List[ZigZagTrail]:
    link_graph = nx.Graph()
    link_graph.add_nodes_from(N.edges())

    for v in N.nodes():
        out_e = list(N.out_edges(v))
        if len(out_e) == 2:
            link_graph.add_edge(out_e[0], out_e[1])
        in_e = list(N.in_edges(v))
        if len(in_e) == 2:
            link_graph.add_edge(in_e[0], in_e[1])

    trails: List[ZigZagTrail] = []
    for component in nx.connected_components(link_graph):
        sub = link_graph.subgraph(component)
        endpoints = [n for n in sub.nodes() if sub.degree(n) < 2]
        if endpoints:
            order = _trace_path(sub, endpoints[0])
            trails.append(ZigZagTrail(order, is_crown=False))
        else:
            order = _trace_cycle(sub, next(iter(sub.nodes())))
            trails.append(ZigZagTrail(order, is_crown=True))
    return trails


def _trace_path(sub: nx.Graph, start: Edge) -> List[Edge]:
    order = [start]
    prev: Optional[Edge] = None
    cur = start
    while True:
        nbrs = [n for n in sub.neighbors(cur) if n != prev]
        if not nbrs:
            return order
        nxt = nbrs[0]
        order.append(nxt)
        prev, cur = cur, nxt


def _trace_cycle(sub: nx.Graph, start: Edge) -> List[Edge]:
    order = [start]
    prev: Optional[Edge] = None
    cur = start
    while True:
        nbrs = [n for n in sub.neighbors(cur) if n != prev]
        nxt = nbrs[0]
        if nxt == start:
            return order
        order.append(nxt)
        prev, cur = cur, nxt


# --------------------------------------------------------------------------
# 2. The compact "cycle label" ILP
# --------------------------------------------------------------------------

@dataclass
class LevelOneResult:
    feasible: Optional[bool]  # None if the solver did not reach optimal/infeasible (e.g. timeout)
    status: str
    support_edges: Optional[Set[Edge]] = None
    reticulations: Optional[Set[Vertex]] = None
    timings: Dict[str, float] = field(default_factory=dict)


class LevelLe1Model:
    def __init__(
        self,
        N: nx.DiGraph,
        root: Optional[Vertex] = None,
        verbose: bool = True,
        time_limit: Optional[float] = None,
    ):
        self.verbose = verbose
        self.timings: Dict[str, float] = {}

        t0 = time.perf_counter()
        self.N = N
        self.root = root if root is not None else self._detect_root()
        self.R = sorted(v for v in N.nodes() if N.in_degree(v) == 2)
        self.R_label = {t: i + 1 for i, t in enumerate(self.R)}  # labels 1..m
        self.m = len(self.R)
        # "root or tree vertex": the only vertices that can head a cycle,
        # i.e. send two cycle edges out (S in LP-idea2.md section 1/3).
        self.S = sorted(v for v in N.nodes() if N.out_degree(v) == 2)
        self.trails = zigzag_trail_decomposition(N)
        self.timings["preprocess"] = time.perf_counter() - t0

        if self.verbose:
            self._report_preprocessing()

        t1 = time.perf_counter()
        self.env = gp.Env(empty=True)
        self.env.setParam("OutputFlag", 1 if verbose else 0)
        self.env.start()
        self.model = gp.Model("level-le-1-support-network-compact", env=self.env)
        if time_limit is not None:
            self.model.setParam("TimeLimit", time_limit)

        self.s: Dict[Edge, gp.Var] = {}
        self.z: Dict[Edge, gp.Var] = {}
        self.r: Dict[Vertex, gp.Var] = {}
        self.p: Dict[Vertex, gp.Var] = {}
        self.h: Dict[Vertex, gp.Var] = {}
        self.lam: Dict[Vertex, gp.Var] = {}

        self._build_variables()
        self._build_constraints()
        self.model.setObjective(0, GRB.MINIMIZE)
        self.model.update()
        self.timings["model_build"] = time.perf_counter() - t1

        if self.verbose:
            print(
                f"[timing] preprocess={self.timings['preprocess']:.4f}s "
                f"model_build={self.timings['model_build']:.4f}s"
            )

    # ---- setup ----

    def _detect_root(self) -> Vertex:
        roots = [v for v in self.N.nodes() if self.N.in_degree(v) == 0]
        if len(roots) != 1:
            raise ValueError(
                f"expected exactly one root (indeg 0), found {roots}; "
                "pass root=... explicitly for multi-rooted networks"
            )
        return roots[0]

    def _report_preprocessing(self) -> None:
        n_crown = sum(tr.is_crown for tr in self.trails)
        print(
            f"[preprocess] |V|={self.N.number_of_nodes()} |E|={self.N.number_of_edges()} "
            f"root={self.root} |R|={len(self.R)} |S|={len(self.S)}"
        )
        print(
            f"[preprocess] {len(self.trails)} maximal zig-zag trails "
            f"({n_crown} crowns, {len(self.trails) - n_crown} fences)"
        )

    # ---- variables ----

    def _build_variables(self) -> None:
        m = self.model
        for e in self.N.edges():
            self.s[e] = m.addVar(vtype=GRB.BINARY, name=f"s_{e[0]}_{e[1]}")
            self.z[e] = m.addVar(vtype=GRB.BINARY, name=f"z_{e[0]}_{e[1]}")
        for t in self.R:
            self.r[t] = m.addVar(vtype=GRB.BINARY, name=f"r_{t}")
        for v in self.S:
            self.p[v] = m.addVar(vtype=GRB.BINARY, name=f"p_{v}")
        for v in self.N.nodes():
            self.h[v] = m.addVar(vtype=GRB.BINARY, name=f"h_{v}")
            self.lam[v] = m.addVar(
                vtype=GRB.INTEGER, lb=0.0, ub=float(self.m), name=f"lam_{v}"
            )

    # ---- helper expressions ----

    def r_bar(self, v: Vertex):
        return self.r[v] if v in self.r else 0

    def p_bar(self, v: Vertex):
        return self.p[v] if v in self.p else 0

    # ---- constraints ----

    def _build_constraints(self) -> None:
        self._add_B_admissibility()
        self._add_r_definition()
        self._add_cycle_degree_constraints()
        self._add_label_constraints()

    def _add_B_admissibility(self) -> None:
        m = self.model
        for tr in self.trails:
            es = tr.edges
            mi = len(es)
            if tr.is_crown:
                for j in range(mi):
                    m.addConstr(self.s[es[j]] + self.s[es[(j + 1) % mi]] >= 1, name="B4")
                for j in range(mi):
                    m.addConstr(
                        self.s[es[j]] + self.s[es[(j + 1) % mi]] + self.s[es[(j + 2) % mi]] <= 2,
                        name="B5",
                    )
            else:
                m.addConstr(self.s[es[0]] == 1, name="B1_first")
                m.addConstr(self.s[es[-1]] == 1, name="B1_last")
                for j in range(mi - 1):
                    m.addConstr(self.s[es[j]] + self.s[es[j + 1]] >= 1, name="B2")
                for j in range(mi - 2):
                    m.addConstr(
                        self.s[es[j]] + self.s[es[j + 1]] + self.s[es[j + 2]] <= 2, name="B3"
                    )

    def _add_r_definition(self) -> None:
        # (R): r_t = sum_{e in delta^-(t)} s_e - 1
        m = self.model
        for t in self.R:
            m.addConstr(
                self.r[t] == gp.quicksum(self.s[e] for e in self.N.in_edges(t)) - 1,
                name=f"R_{t}",
            )

    def _add_cycle_degree_constraints(self) -> None:
        m = self.model
        for e in self.N.edges():
            m.addConstr(self.z[e] <= self.s[e], name=f"Z1_{e[0]}_{e[1]}")  # (Z1)


        for v in self.N.nodes():
            in_expr = gp.quicksum(self.z[e] for e in self.N.in_edges(v))
            out_expr = gp.quicksum(self.z[e] for e in self.N.out_edges(v))
            r_bar_v = self.r_bar(v)
            p_bar_v = self.p_bar(v)
            m.addConstr(in_expr == self.h[v] + 2 * r_bar_v, name=f"Z2_{v}")
            m.addConstr(out_expr == self.h[v] + 2 * p_bar_v, name=f"Z3_{v}")
            m.addConstr(self.h[v] + p_bar_v + r_bar_v <= 1, name=f"Z4_{v}")

    def _add_label_constraints(self) -> None:
        m = self.model
        M = float(self.m)

        for e in self.N.edges():
            u, v = e
            m.addConstr(self.lam[u] - self.lam[v] <= M * (1 - self.z[e]), name=f"L2_hi_{u}_{v}")
            m.addConstr(self.lam[v] - self.lam[u] <= M * (1 - self.z[e]), name=f"L2_lo_{u}_{v}")

        for t in self.R:
            i = self.R_label[t]
            m.addConstr(self.lam[t] - i <= M * (1 - self.r[t]), name=f"L3_hi_{t}")
            m.addConstr(i - self.lam[t] <= M * (1 - self.r[t]), name=f"L3_lo_{t}")


    # ---- solve / extract ----

    def solve(self) -> LevelOneResult:
        t0 = time.perf_counter()
        self.model.optimize()
        self.timings["solve"] = time.perf_counter() - t0

        if self.verbose:
            print(
                f"[timing] solve={self.timings['solve']:.4f}s "
                f"total={sum(self.timings.values()):.4f}s"
            )

        status_code = self.model.Status
        status = _STATUS_NAME.get(status_code, str(status_code))
        if status_code == GRB.INFEASIBLE:
            return LevelOneResult(feasible=False, status=status, timings=dict(self.timings))
        if status_code != GRB.OPTIMAL:
            # e.g. TIME_LIMIT, INTERRUPTED: the solver did not settle the question.
            return LevelOneResult(feasible=None, status=status, timings=dict(self.timings))

        support_edges = {e for e, var in self.s.items() if var.X > 0.5}
        reticulations = {t for t in self.R if self.r[t].X > 0.5}
        return LevelOneResult(
            feasible=True,
            status=status,
            support_edges=support_edges,
            reticulations=reticulations,
            timings=dict(self.timings),
        )

    def close(self) -> None:
        """Release the Gurobi model and environment."""
        self.model.dispose()
        self.env.dispose()


def has_level_le1_support_network(
    N: nx.DiGraph, root: Optional[Vertex] = None, verbose: bool = True
) -> LevelOneResult:
    """Convenience entry point: build the compact model, solve with Gurobi, and return the result."""
    model = LevelLe1Model(N, root=root, verbose=verbose)
    result = model.solve()
    model.close()
    return result


# --------------------------------------------------------------------------
# 3. Loading a network from data/
# --------------------------------------------------------------------------

def load_network_from_file(path: str) -> nx.DiGraph:
    """Load a network from an edge-list file where each line is 'u v',
    read as a directed edge u -> v."""
    N = nx.DiGraph()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            u, v = line.split()
            N.add_edge(u, v)
    return N

def draw_subnetwork(network, subnetwork, filename="network"):
    dot = Digraph()
    for u, v in network.edges():
        if (u, v) in subnetwork.edges():
            dot.edge(u, v)
        else:
            dot.edge(u, v, color="gray", style="dashed")
    dot.render(filename, format="pdf", cleanup=True)

if __name__ == "__main__":

    filename = input("File Name: ")

    N = load_network_from_file(filename + ".txt")

    result = has_level_le1_support_network(N, verbose=True)
    print()
    if result.feasible:
        print("FEASIBLE: N has a level-<=1 support network.")
        out_path = f"{filename}_support.txt"
        with open(out_path, "w") as f:
            for u, v in result.support_edges():
                f.write(f"{u} {v}\n")
        print(f"wrote a support network to {out_path}")
        G = nx.DiGraph(list(result.support_edges))
        draw_subnetwork(N, G, filename=f"{filename}_support")
        print(f"wrote a support network to {filename}_support.pdf")
    
    else:
        print("INFEASIBLE: N has no level-<=1 support network.")

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
    """A maximal zig-zag trail, stored as an ordered list of edges."""

    __slots__ = ("edges", "is_crown", "kind")

    def __init__(self, edges: List[Edge], is_crown: bool):
        self.edges = edges
        self.is_crown = is_crown
        self.kind = _classify_trail(edges, is_crown)

    def __len__(self) -> int:
        return len(self.edges)

    def __repr__(self) -> str:
        return f"{self.kind}(len={len(self.edges)}, {self.edges})"


def _classify_trail(edges: List[Edge], is_crown: bool) -> str:
    if is_crown:
        return "crown"
    if len(edges) % 2 == 1:
        return "N-fence"
    if edges[0][0] == edges[1][0]:
        return "M-fence"
    return "W-fence"


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


def _resolve_fence_edges(tr: ZigZagTrail) -> Set[Edge]:
    edges = tr.edges
    if tr.kind == "N-fence":
        return {edges[i] for i in range(0, len(edges), 2)}
    if tr.kind == "M-fence":
        selected = {edges[0], edges[1]}
        selected.update(edges[i] for i in range(3, len(edges), 2))
        return selected
    raise ValueError(f"_resolve_fence_edges called on a {tr.kind} trail")


def support_network_level(N: nx.DiGraph, support_edges: Set[Edge]) -> int:
    G = nx.DiGraph()
    G.add_nodes_from(N.nodes())
    G.add_edges_from(support_edges)
    undirected = G.to_undirected()
    max_reticulations = 0
    for comp in nx.biconnected_components(undirected):
        reticulation_count = sum(1 for node in comp if G.in_degree(node) > 1)
        max_reticulations = max(max_reticulations, reticulation_count)
    return max_reticulations


# --------------------------------------------------------------------------
# 2. The edge-multiplicity heuristic ILP
# --------------------------------------------------------------------------
@dataclass
class MinLevelHeurResult:
    solved: bool
    status: str
    support_edges: Optional[Set[Edge]] = None
    reticulations: Optional[Set[Vertex]] = None  # active reticulations (t_i = 1)
    objective: Optional[float] = None
    extra_edge_uses: Optional[float] = None  # sum_e q_e
    level: Optional[int] = None  # actual level(G), see support_network_level
    timings: Dict[str, float] = field(default_factory=dict)


class MinLevelHeurModel:
    
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
        self.m = len(self.R)
        self.trails = zigzag_trail_decomposition(N)
        self.timings["preprocess"] = time.perf_counter() - t0

        self.trivial_zero_level = not any(tr.kind in ("crown", "W-fence") for tr in self.trails)

        self.env: Optional[gp.Env] = None
        self.model: Optional[gp.Model] = None
        self.s: Dict[Edge, gp.Var] = {}
        self.t: Dict[Vertex, gp.Var] = {}
        self.z: Dict[Tuple[Edge, Vertex], gp.Var] = {}
        self.c: Dict[Tuple[Vertex, Vertex], gp.Var] = {}
        self.p: Dict[Tuple[Vertex, Vertex], gp.Var] = {}
        self.q_e: Dict[Edge, gp.Var] = {}

        if self.verbose:
            self._report_preprocessing()

        if self.trivial_zero_level:
            self.timings["model_build"] = 0.0
            if self.verbose:
                print("[preprocess] no crown/W-fence found: min level(G) = 0, skipping the ILP")
            return

        t1 = time.perf_counter()
        self.env = gp.Env(empty=True)
        self.env.setParam("OutputFlag", 1 if verbose else 0)
        self.env.start()
        self.model = gp.Model("min-level-heuristic", env=self.env)
        if time_limit is not None:
            self.model.setParam("TimeLimit", time_limit)

        self._build_variables()
        self._build_constraints()
        self._set_objective()
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
        kind_counts: Dict[str, int] = {}
        for tr in self.trails:
            kind_counts[tr.kind] = kind_counts.get(tr.kind, 0) + 1
        print(
            f"[preprocess] |V|={self.N.number_of_nodes()} |E|={self.N.number_of_edges()} "
            f"root={self.root} |R|={self.m}"
        )
        breakdown = ", ".join(f"{count} {kind}" for kind, count in sorted(kind_counts.items()))
        print(f"[preprocess] {len(self.trails)} maximal zig-zag trails ({breakdown})")

    # ---- variables ----

    def _build_variables(self) -> None:
        m = self.model
        for e in self.N.edges():
            self.s[e] = m.addVar(vtype=GRB.BINARY, name=f"s_{e[0]}_{e[1]}")
        for r in self.R:
            self.t[r] = m.addVar(vtype=GRB.BINARY, name=f"t_{r}")

        for r in self.R:
            for e in self.N.edges():
                self.z[(e, r)] = m.addVar(vtype=GRB.BINARY, name=f"z_{e[0]}_{e[1]}__{r}")
            for v in self.N.nodes():
                self.c[(v, r)] = m.addVar(vtype=GRB.BINARY, name=f"c_{v}__{r}")
                self.p[(v, r)] = m.addVar(vtype=GRB.BINARY, name=f"p_{v}__{r}")

        q_ub = float(max(self.m - 1, 0))
        for e in self.N.edges():
            self.q_e[e] = m.addVar(vtype=GRB.INTEGER, lb=0.0, ub=q_ub, name=f"q_{e[0]}_{e[1]}")

    # ---- constraints ----

    def _build_constraints(self) -> None:
        self._add_B_admissibility()  # (2)-(6)
        self._add_subgraph_containment()  # (16)
        self._add_vertex_roles()  # (17)
        self._add_cycle_degree_constraints()  # (18)-(19)
        self._add_reticulation_activation()  # (20)
        self._add_multiplicity()  # (20)

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


    def _add_subgraph_containment(self) -> None:
        # (16): z_{e,r} <= s_e
        m = self.model
        for r in self.R:
            for e in self.N.edges():
                m.addConstr(self.z[(e, r)] <= self.s[e], name=f"Contain_{e[0]}_{e[1]}__{r}")

    def _add_vertex_roles(self) -> None:
        # (17): c_{v,r} + p_{v,r} + 1[v=r] t_r <= 1
        m = self.model
        for r in self.R:
            t_r = self.t[r]
            for v in self.N.nodes():
                indicator_term = t_r if v == r else 0
                m.addConstr(
                    self.c[(v, r)] + self.p[(v, r)] + indicator_term <= 1, name=f"Role16_{v}__{r}"
                )

    def _add_cycle_degree_constraints(self) -> None:
        # (18): sum_{e in delta^-(v)} z_{e,r} = c_{v,r} + 2*1[v=r] t_r
        # (19): sum_{e in delta^+(v)} z_{e,r} = c_{v,r} + 2 p_{v,r}
        m = self.model
        for r in self.R:
            t_r = self.t[r]
            for v in self.N.nodes():
                in_expr = gp.quicksum(self.z[(e, r)] for e in self.N.in_edges(v))
                out_expr = gp.quicksum(self.z[(e, r)] for e in self.N.out_edges(v))
                indicator_term = 2 * t_r if v == r else 0
                m.addConstr(in_expr == self.c[(v, r)] + indicator_term, name=f"Deg18_{v}__{r}")
                m.addConstr(
                    out_expr == self.c[(v, r)] + 2 * self.p[(v, r)], name=f"Deg19_{v}__{r}"
                )


    def _add_reticulation_activation(self) -> None:
        # (20): t_r = sum_{e in delta_N^-(r)} s_e - 1
        m = self.model
        for r in self.R:
            m.addConstr(
                self.t[r] == gp.quicksum(self.s[e] for e in self.N.in_edges(r)) - 1,
                name=f"Ret_{r}",
            )


    def _add_multiplicity(self) -> None:
        # (21): q_e >= sum_r z_{e,r} - 1
        m = self.model
        for e in self.N.edges():
            m.addConstr(
                self.q_e[e] >= gp.quicksum(self.z[(e, r)] for r in self.R) - 1,
                name=f"QE_{e[0]}_{e[1]}",
            )

    def _set_objective(self) -> None:
        obj = gp.quicksum(self.q_e[e] for e in self.N.edges())
        self.model.setObjective(obj, GRB.MINIMIZE)

    # ---- solve / extract ----

    def _solve_trivial_zero_level(self) -> MinLevelHeurResult:
        support_edges: Set[Edge] = set()
        for tr in self.trails:
            support_edges.update(_resolve_fence_edges(tr))

        if self.verbose:
            print(
                f"[timing] solve=0.0000s total={sum(self.timings.values()):.4f}s "
                f"(trivial: no crown/W-fence)"
            )

        return MinLevelHeurResult(
            solved=True,
            status="TRIVIAL_ZERO_LEVEL",
            support_edges=support_edges,
            reticulations=set(),
            objective=0.0,
            extra_edge_uses=0.0,
            level=0,
            timings=dict(self.timings),
        )

    def solve(self) -> MinLevelHeurResult:
        if self.trivial_zero_level:
            self.timings["solve"] = 0.0
            return self._solve_trivial_zero_level()

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
            return MinLevelHeurResult(solved=False, status=status, timings=dict(self.timings))
        if self.model.SolCount == 0:
            return MinLevelHeurResult(solved=False, status=status, timings=dict(self.timings))

        support_edges = {e for e, var in self.s.items() if var.X > 0.5}
        reticulations = {r for r in self.R if self.t[r].X > 0.5}
        extra_edge_uses = sum(var.X for var in self.q_e.values()) if self.q_e else None

        return MinLevelHeurResult(
            solved=(status_code == GRB.OPTIMAL),
            status=status,
            support_edges=support_edges,
            reticulations=reticulations,
            objective=self.model.ObjVal,
            extra_edge_uses=extra_edge_uses,
            level=support_network_level(self.N, support_edges),
            timings=dict(self.timings),
        )

    def close(self) -> None:
        if self.model is not None:
            self.model.dispose()
        if self.env is not None:
            self.env.dispose()


def solve_min_level_heuristic(
    N: nx.DiGraph,
    root: Optional[Vertex] = None,
    verbose: bool = True,
    time_limit: Optional[float] = None,
) -> MinLevelHeurResult:
    """Convenience entry point: build the model, solve with Gurobi, and return the result."""
    model = MinLevelHeurModel(
        N, root=root, verbose=verbose,
        time_limit=time_limit,
    )
    result = model.solve()
    model.close()
    return result


# --------------------------------------------------------------------------
# 3. Loading a network from a file
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

    result = solve_min_level_heuristic(N, verbose=True)
    print()
    if result.solved:
        print(f"objective = {result.objective}")
        print(f"actual level(G) = {result.level}")
        out_path = f"{filename}_support.txt"
        with open(out_path, "w") as f:
            for u, v in result.support_edges:
                f.write(f"{u} {v}\n")
        print(f"wrote a support network to {out_path}")
        G = nx.DiGraph(list(result.support_edges))
        draw_subnetwork(N, G, filename=f"{filename}_support")
        print(f"wrote a support network to {filename}_support.pdf")
        
    else:
        print(f"Solver did not find a solution (status={result.status}).")

import random
import networkx as nx


def multigraph_to_digraph(G):
    G = G.copy()
    changed = True
    while changed:
        changed = False

        # drop duplicate parallel edges, keeping one copy of each (u, v)
        seen = set()
        for u, v, key in list(G.edges(keys=True)):
            if (u, v) in seen:
                G.remove_edge(u, v, key=key)
                changed = True
            else:
                seen.add((u, v))

        # smooth vertices left with indegree 1 and outdegree 1
        for v in list(G.nodes()):
            if G.in_degree(v) == 1 and G.out_degree(v) == 1:
                u, _, key_in = list(G.in_edges(v, keys=True))[0]
                _, w, key_out = list(G.out_edges(v, keys=True))[0]
                G.remove_edge(u, v, key=key_in)
                G.remove_edge(v, w, key=key_out)
                G.remove_node(v)
                G.add_edge(u, w)
                changed = True

    return nx.DiGraph(G)

def _add_G1(G, entry, max_idx):
    a, b, c, d, e, f = (max_idx + i for i in range(1, 7))
    G.add_edges_from([(entry, a), (entry, b), (a, c), (a, d), (b, c), (b, d), (c, e), (d, f)])
    return max_idx + 6, [e, f]

def _add_G3(G, entry, max_idx):
    a, b, c, d, e, f = (max_idx + i for i in range(1, 7))
    G.add_edges_from([(entry, a), (entry, c), (a, b), (a, d), (b, c), (b, d), (c, e), (d, f)])
    return max_idx + 6, [e, f]


def _add_G2(G, u, v, max_idx):
    a, b, c, d = max_idx + 1, max_idx + 2, max_idx + 3, max_idx + 4
    G.add_edges_from([(u, a), (a, b), (a, c), (b, c), (b, d), (c, d), (d, v)])
    return max_idx + 4, d

def _add_G4(G, u, v, max_idx):
    a, b, c, d = max_idx + 1, max_idx + 2, max_idx + 3, max_idx + 4
    G.add_edges_from([(u, a), (a, b), (a, d), (b, c), (b, c), (c, d), (d, v)])
    return max_idx + 4, d


def _add_L1(G, u, v, max_idx):
    a, b = max_idx + 1, max_idx + 2
    G.add_edges_from([(u, a), (a, b), (a, b), (b, v)])
    return max_idx + 2, b


def _insert_edge_kind_generator(add_fn, G, max_idx, trivial_edges):
    u, v = random.choice(list(trivial_edges))
    G.remove_edge(u, v)
    entry_node = max_idx + 1  # every add_fn allocates its entry node first
    max_idx, exit_node = add_fn(G, u, v, max_idx)

    trivial_edges.remove((u, v))
    trivial_edges.add((u, entry_node))
    trivial_edges.add((exit_node, v))

    return max_idx





def _insert_leaf_kind_generator(add_fn, G, max_idx):
    leaves = [node for node in G.nodes() if G.out_degree(node) == 0]
    entry_leaf = random.choice(leaves)
    max_idx, new_leaves = add_fn(G, entry_leaf, max_idx)
    leaf_count_delta = len(new_leaves) - 1  # entry_leaf consumed, new leaves added
    return max_idx, leaf_count_delta


# generate random level-2 network with n leaves, l level-2 blocks, and k level-1 blocks
def generate_random_level2_network(n, l, m=0):
    G = nx.MultiDiGraph()
    G.add_edges_from([(0, 1), (0, 2)])
    max_idx = 2
    leaf_count = 2

    trivial_edges = set(G.edges())


    ops = ["level2"] * l + ["level1"] * m
    random.shuffle(ops)

    for op in ops:
        if op == "level1":
            max_idx = _insert_edge_kind_generator(_add_L1, G, max_idx, trivial_edges)
            continue

        if leaf_count < n:
            name = random.choice(["G1", "G2", "G3", "G4"])
        else:
            name = random.choice(["G2", "G4"])

        if name == "G2":
            max_idx = _insert_edge_kind_generator(_add_G2, G, max_idx, trivial_edges)
        elif name == "G4":
            max_idx = _insert_edge_kind_generator(_add_G4, G, max_idx, trivial_edges)
        elif name == "G1":
            max_idx, delta = _insert_leaf_kind_generator(_add_G1, G, max_idx)
            leaf_count += delta
        else:  # "G3"
            max_idx, delta = _insert_leaf_kind_generator(_add_G3, G, max_idx)
            leaf_count += delta

    while leaf_count < n:
        u, v = random.choice(list(G.edges()))
        G.remove_edge(u, v)
        G.add_edges_from([
            (u, max_idx + 1),
            (max_idx + 1, v),
            (max_idx + 1, max_idx + 2),
        ])
        max_idx += 2
        leaf_count += 1

    return G


def _add_reticulation(network, base_net, edges=None):
    e1, e2 = random.sample(edges if edges is not None else list(base_net.edges()), 2)
    t1, h1 = e1
    t2, h2 = e2
    if nx.has_path(network, h2, h1):
        (t1, h1), (t2, h2) = (t2, h2), (t1, h1)

    new1, new2 = max(network.nodes()) + 1, max(network.nodes()) + 2
    network.remove_edge(t1, h1)
    network.remove_edge(t2, h2)
    network.add_edges_from(
        [
            (t1, new1),
            (new1, h1),
            (t2, new2),
            (new2, h2),
            (new1, new2)
        ]
    )

    base_net.remove_edge(t1, h1)
    base_net.remove_edge(t2, h2)
    base_net.add_edges_from(
        [
            (t1, new1),
            (new1, h1),
            (t2, new2),
            (new2, h2)
        ]
    )


def _non_duplicate_edges(base_net):
    counts = {}
    for e in base_net.edges():
        counts[e] = counts.get(e, 0) + 1
    return [e for e in base_net.edges() if counts[e] == 1]


def generate_random_L2B_network(n, r, l, m=0):
    # start with tree with n leaves
    base_net = generate_random_level2_network(n, l, m=0)
    network = base_net.copy()

    for i in range(r-2*l):
        _add_reticulation(network, base_net)

    while True:
        collapsed = multigraph_to_digraph(network)
        actual_r = sum(1 for v in collapsed.nodes() if collapsed.in_degree(v) == 2)
        if actual_r >= r:
            break
        safe_edges = _non_duplicate_edges(base_net)
        _add_reticulation(network, base_net, edges=safe_edges if len(safe_edges) >= 2 else None)

    return multigraph_to_digraph(network), multigraph_to_digraph(base_net)






if __name__ == "__main__":
    # e.g. "hoge 8 100 2 20" -> output filename=hoge, n=8, r=100, l=2, m=20
    line = input("Output filename, n, r, l, m: ")
    parts = line.split()
    if len(parts) != 5:
        raise ValueError(
            "expected 5 space-separated values: <output filename> <n> <r> <l> <m>, "
            f"e.g. 'hoge 8 100 2 20' (got {len(parts)}: {parts})"
        )
    filename, n, r, l, m = parts
    n, r, l, m = int(n), int(r), int(l), int(m)

    network, base_net = generate_random_L2B_network(n, r, l, m)

    out_path = f"{filename}.txt"
    with open(out_path, "w") as f:
        for u, v in network.edges():
            f.write(f"{u} {v}\n")

    print(f"wrote level-2-based network (n={n}, r={r}, l={l}, m={m}) to {out_path}")

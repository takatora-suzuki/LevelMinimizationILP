import networkx as nx
from graphviz import Digraph


def load_network_from_file(path: str) -> nx.DiGraph:
    N = nx.DiGraph()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            u, v = line.split()
            N.add_edge(u, v)
    return N

def draw_network(network, filename="network"):
    dot = Digraph()
    for u, v in network.edges():
        dot.edge(u, v)
    dot.render(filename, format="pdf", cleanup=True)


if __name__ == "__main__":
    filename = input("File Name: ")

    network = load_network_from_file(filename + ".txt")

    draw_network(network, filename=filename)
    print(f"drew a network in {filename}.pdf")

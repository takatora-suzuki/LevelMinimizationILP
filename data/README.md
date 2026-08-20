# Networks generated for the experiments

This directory contains the data set, which we used in the experiments.

There are two directories:
* `Form1_Experiment`: Random networks used in the Experiment 1. For each `r ∈ {100, 200, ..., 800}`, there are 100 instances with `r` reticulations. Each instance was generated using `code/generate_instances_EXP1.py` with `n=8`, `l=2`, and `m=r/5`.
* `ARG_Application`: Two ancestral recombination graphs (ARGs) used in the biological case study in our paper. Each ARG was originally provided as a JSON representation in [this GitHub repository](https://github.com/tskit-dev/what-is-an-arg-paper/tree/main/illustrations/assets), and converted here into the edge-list format described below.

The dataset used in Experiment 2 is *not* stored in this directory; it is reused from the `structure-support-networks` repository (see [`results/README.md`](../results/README.md) for the citation and link).

## File format

Each line of the file represents the tail and the head of a directed edge in the network. For example, a line `a b` represents the edge (a, b) of the network.

For example, the contents of [`sample-input.txt`](../sample-input.txt) are as follows:

```
1 2
1 10
2 3
2 4
3 5
3 8
4 9
4 10
5 6
5 7
6 11
6 x1
7 11
7 12
8 12 
8 15
9 13
9 15
10 16
11 14
12 14
13 16
13 18
14 17
15 17
16 18
17 x2
18 x3
```

This content represents the network visualized in [`sample-input.pdf`](../sample-input.pdf). Any file in this format can be visualized with [`draw_network.py`](../code/draw_network.py).
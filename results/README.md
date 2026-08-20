# Experiment results

This directory contains the experimental results obtained for the networks in [`data`](../data/), organized into three subdirectories matching Sections 5.1, 5.2 and 6 of the paper (see the root [README](../README.md)).

## Experiment 1 (Section 5.1): scalability of Formulation 1

`Form1_Experiment/` contains the results of running [`Formulation1_gurobi.py`](../code/Formulation1_gurobi.py) on every instance in [`data/Form1_Experiment`](../data/Form1_Experiment).

* `results_n=8_r=<r>_l=2_m=<m>_summary.csv`: one row per input instance with `r` reticulations, with columns:
    * `filename`: the input file.
    * `ILP level<=1?`: `True` if Formulation 1 found a support network of level at most one for this instance, `False` otherwise.
    * `ILP runtime`: total wall-clock runtime in seconds, measured with `time.perf_counter()` (preprocessing + model building + solving, as printed by the program).
* `summary_by_r_true_false.csv`: one row per `r`, aggregating the per-instance results above into the count and the average/min/max runtime, reported separately for the `True` (YES) instances, the `False` (NO) instances, and all (`All`) instances. 
## Experiment 2 (Section 5.2): performance of Formulation 2

`Form2_Experiment/` contains the results of comparing [`Formulation2_gurobi.py`](../code/Formulation2_gurobi.py) (this repository) against Algorithm 2 of Suzuki and Hayamizu (2025). This experiment reuses the benchmark dataset and the exact/heuristic algorithms of that earlier paper, so neither the input networks nor the `Exact` columns below were produced with anything in this repository — they come from the companion repository:

> Takatora Suzuki and Momoko Hayamizu. _Structure Support Networks._ GitHub. <https://github.com/hayamizu-lab/structure-support-networks>
> - data used here: [`data/LM-Experiment`](https://github.com/hayamizu-lab/structure-support-networks/tree/main/data/LM-Experiment)
> - exact algorithm (Algorithm 1): [`code/LM-Exact.py`](https://github.com/hayamizu-lab/structure-support-networks/blob/main/code/LM-Exact.py)
> - heuristic algorithm (Algorithm 2): [`code/LM-Heuristic.py`](https://github.com/hayamizu-lab/structure-support-networks/blob/main/code/LM-Heuristic.py)

* `Form2_vs_Alg2_r=<r>.csv`: one row per non-tree-based instance with `r` reticulations (`r` ranges from 4 to 36; `r = 1, 2, 3` are excluded because every instance there is tree-based), with columns:
    * `Input file`: the input file name.
    * `Exact minimum level`: the true base level of the instance, computed by Algorithm 1 of the companion repository.
    * `Heuristic minimum level`, `Heuristic runtime`: the level of the support network returned by Algorithm 2, and its runtime in seconds.
    * `ILP Form2 level`, `ILP Form2 runtime`: the level of the support network returned by Formulation 2, and its runtime in seconds.
    * `ILP Form2 objective`: the value of Formulation 2's objective (minimized total edge-multiplicity overlap) at the optimum.

## Case study (Section 6): application to ARGs

`ARG_Application/` contains the results of running all four methods on the two ancestral recombination graphs (ARGs) in [`data/ARG_Application`](../data/ARG_Application/): Algorithm 1 and Algorithm 2 of the `structure-support-networks` repository (see the citation above), and Formulation 1 and Formulation 2 of this repository.

`ARG_summary.csv` contains  one row per input ARG (`KwARG_edges.txt`, `ARGweaver_edges.txt`), with columns:
* `Input file`: the input file in `data/ARG_Application/`.
* `Exact minimum level`, `Exact runtime`: base level and runtime of Algorithm 1.
* `Heuristic minimum level`, `Heuristic runtime`: level and runtime of Algorithm 2.
* `ILP Form1 level`: `1` if Formulation 1 found a level-at-most-one support network, `INFEASIBLE` otherwise.
* `ILP Form1 runtime`: runtime of Formulation 1.
* `ILP Form2 level`, `ILP Form2 runtime`, `ILP heuristic objective`: level, runtime, and objective value of Formulation 2.

`edge_list/`: the support network returned by each method for each input ARG, as an edge list in the same `u v` format as the files under `data/` (see [`data/README.md`](../data/README.md)). 
Each file is named `<input>__<method>.txt`, where `<method>` is one of `Exact` (Algorithm 1), `Heuristic` (Algorithm 2), `ILP_Form1` (Formulation 1), or `ILP_Form2` (Formulation 2), e.g. `KwARG_edges__Exact.txt`. 
Note that `ARGweaver_edges__ILP_Form1.txt` is absent because Formulation 1 is infeasible on `ARGweaver_edges.txt`.

`figures/`: a PDF visualization of every file in `edge_list/`, named `<input>__<method>.pdf`. 
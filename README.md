# LevelMinimizationILP


This repository contains an implementation of the integer linear programming formulation for solving the Level Minimization problem (Problem 2 in our paper) using Gurobi. This repository also contains the results of the experiments carried out in this paper.


This repository serves as the supporting material for the following paper:
> Takatora Suzuki. **Finding Tree-Like Substructures in Phylogenetic Networks: ILP Approaches and Their Application.** _submitted._

## Repository Structure

The repository is organized as follows:

* `code`: Contains all the code used for the experiments in our paper.
    * `Formulation1_gurobi.py`: Implementation of Formulation 1, which exactly decides whether an input network has a support network of level at most one. 
    * `Formulation2_gurobi.py`: Implementation of Formulation 2, which heuristically minimizes the level of a support network of an input network.
    * `generate_instances_EXP1.py`: Code used to randomly generate the input data for the experiment in Section 5.1.
    * `draw_network.py`: Code used to visualize a network in PDF format.
* `data`: Contains the input data used for the experiments. 
    * `Form1_Experiment`: Data sets used in the experiment in Section 5.1.
    * `ARG_Application`: The two ancestral recombination graphs used in the case study in Section 6.
* `results`: Contains full details of the results of the experiments in Section 5, and of the case study in Section 6. 

We note that the data sets and the algorithms used in Experiment 2, as well as Algorithms 1 and 2 used alongside Formulations 1 and 2 in the case study of Section 6, are not in this repository, but in the following repository:
> Takatora Suzuki and Momoko Hayamizu. _Structure Support Networks_. GitHub. https://github.com/hayamizu-lab/structure-support-networks

See [`results/README.md`](results/README.md) for exactly which files of that repository were used.

## Usage

### Environment set-up

Clone this repository to your local machine and move into its root directory:
```bash
git clone https://github.com/takatora-suzuki/LevelMinimizationILP.git
cd LevelMinimizationILP
```

### Prerequisites

To run this project, you will need:
+ [Gurobi Optimizer](https://www.gurobi.com/) with a valid Gurobi license (see below)
+ Python packages: `gurobipy`, `networkx`, `graphviz`
+ Standard-library modules used by the code (included with Python, no installation needed): `random`, `time`, `dataclasses`, `typing`

An activated Gurobi license is required to run the solver. See the [Gurobi website](https://www.gurobi.com/) for details on obtaining one. If you are a student or a faculty member, a free academic license is available. 

### Tutorial

When you run a program, you will be prompted for a file name. Enter the input path **without the `.txt` extension**; each script appends it automatically. We demonstrate the code using the sample input [`sample-input.txt`](sample-input.txt) (this network is isomorphic to the one shown in Fig. 2(a) of our paper).

#### Running Formulation 1
To run `Formulation1_gurobi`, use
```terminal
python code/Formulation1_gurobi.py
```
and enter `sample-input`. Then, you will get a result after the output by Gurobi, such as:
```
...
Model is infeasible
Best objective -, best bound -, gap -
[timing] solve=0.0034s total=0.0217s

INFEASIBLE: N has no level-<=1 support network.
```
or, for a feasible instance:
```
...
Optimal solution found (tolerance 1.00e-04)
Best objective 0.000000000000e+00, best bound 0.000000000000e+00, gap 0.0000%
[timing] solve=0.0049s total=0.0120s

FEASIBLE: N has a level-<=1 support network.
wrote a support network to sample_support.txt
wrote a support network to sample_support.pdf
```
If feasible, this program outputs the support network of the input network in the working directory such as `sample-input_support.txt`. This program also visualizes the output in PDF format. This PDF highlights the support network in the input network with black solid lines.

#### Running Formulation 2
To run `Formulation2_gurobi`, use
```terminal
python code/Formulation2_gurobi.py
```
and enter `sample-input`. Then, you will get a result after the output by Gurobi, such as:
```
...
Optimal solution found (tolerance 1.00e-04)
Best objective 2.000000000000e+00, best bound 2.000000000000e+00, gap 0.0000%
[timing] solve=0.0037s total=0.0164s

objective = 2.0
actual level(G) = 2
wrote a support network to sample_support.txt
wrote a support network to sample_support.pdf
```
The runtimes are measured by `time.perf.counter()`. The `objective` is the minimum number of overlapped edges across the selected reticulation cycles, not the network level itself; `actual level(G)` is the level of the returned support network, computed separately. This program outputs the edge-set of a support network (see [`sample-input_support.txt`](sample-input_support.txt)). This program also visualizes the output in PDF format (see [`sample-input_support.pdf`](sample-input_support.pdf)). This PDF highlights the support network in the input network with black solid lines.


#### Generating new instances for Experiment 1
To run `generate_instances_EXP1`, use
```terminal
python code/generate_instances_EXP1.py
```
and enter `<output filename> <n> <r> <l> <m>` on one line. Then, this program generates a random level-2-based network with `n` leaves, `r` reticulations and having a level-2 support network with `l` level-2 blocks, and `m` level-1 blocks, and writes it to `<output filename>.txt` (relative to the current working directory).

#### Drawing a network with its support networks
To run `draw_network.py`, use
```terminal
python code/draw_network.py
```
and enter `sample-input`. Then, this program visualizes the network in PDF format in the working directory, such as [`sample-input.pdf`](sample-input.pdf). 

## License

This project is licensed under the [MIT License](LICENSE).

## Contact

If you have any questions or suggestions regarding this project, please feel free to contact the author:
- Takatora Suzuki [takatora.szk@fuji.waseda.jp](mailto:takatora.szk@fuji.waseda.jp)

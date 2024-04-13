# Demand Response analyses workflow

Workflows for **demand response analyses** with the agent-based power market model **AMIRIS**.

The workflow executes AMIRIS and simulates the business-oriented dispatch of a chosen demand response focus cluster for a variety of power tariff designs. 

The tariffs vary in
* the capacity share, i.e. the distribution of payments among peak capacity and energy as well as
* the dynamic share, i.e. the share of the energy-related payment that is made dynamic, hence fluctuating with the model-endogenous day-ahead price.

Some metrics are calculated, such as change the change in peak load, achieved savings from power payments, shifting cycles etc. Net present values are calculated based on savings and actual costs. 

The approach is described in depth within the PhD thesis of Johannes Kochems (forthcoming).

## Overview

* Workflow is defined in the main file `workflow.py`. This is the python file to be executed.
* Workflow is controlled by using a yaml config file `config,yaml`.

## Usage

Dependencies can be installed from the `environment.yml` file at the top level.

For conda / mamba users, the respective command is

```
conda env create -f environment.yml
```

To run, you need a not yet open version of AMIRIS which can be provided on request by contacting the author and fulfilling some DLR non disclosure requirements. Also, you need a solver, e.g. Gurobi or CPLEX, to solve the optimization model.

from typing import Dict

import pandas as pd


def read_param_results_for_runs(config_workflow: Dict) -> Dict:
    """Read parameter results for different runs to compare among each other"""
    run_results = {}
    for run in config_workflow["runs_to_evaluate"]:
        run_results[run] = {}
        for param in config_workflow["params_to_evaluate"]:
            param_results = pd.read_csv(
                f"{config_workflow['output_folder']}/{run}/{param}.csv",
                index_col=0,
                sep=";",
            )
            run_results[run][param] = param_results

    return run_results

from typing import Dict

import pandas as pd

from dr_analyses.workflow_routines import trim_file_name


def read_scenario_result(config_workflow: Dict, scenario: str) -> pd.Series:
    """Read the scenario result and return it"""
    return pd.read_csv(
        config_workflow["output_folder"]
        + trim_file_name(scenario)
        + "/parameter_summary.csv",
        sep=";",
        index_col=0,
    )["Summary"]


def concat_results(scenario_results: Dict) -> pd.DataFrame:
    """Combine parameter results to an overall data set"""
    overall_results = pd.concat(
        [result for result in scenario_results.values()],
        keys=scenario_results.keys(),
        axis=1,
    )
    cost_groups = {
        "low": "low",
        "medium": "medium",
        "high": "high",
        "20": "20",
    }
    tariff_groups = {
        "static_tariff": "static_tariff",
        "DA_plus_static": "DA",
        "DA_plus_dynamicEEG": "DA_dyn_EEG",
        "RTP_wo": "RTP_w_Caps",
        "RTP_no_cap": "RTP_wo_Caps",
    }
    for key, val in cost_groups.items():
        overall_results.loc[
            "cost_group",
            [col for col in overall_results.columns if key in col],
        ] = val
    for key, val in tariff_groups.items():
        overall_results.loc[
            "tariff_group",
            [col for col in overall_results.columns if key in col],
        ] = val

    return overall_results


def evaluate_all_parameter_results(
    config_workflow: Dict, overall_results: pd.DataFrame
) -> Dict[str, pd.DataFrame]:
    """Evaluate all parameter results and store them in a dict of DataFrames"""
    all_parameter_results = dict()
    for param in overall_results.index:
        if param in ["cost_group", "tariff_group"]:
            continue
        else:
            all_parameter_results[param] = evaluate_parameter_results(
                config_workflow, overall_results, param
            )

    return all_parameter_results


def evaluate_parameter_results(
    config_workflow: Dict, overall_results: pd.DataFrame, param: str
) -> pd.DataFrame:
    """Pivot and evaluate parameter results"""
    param_results = overall_results.loc[
        [param, "cost_group", "tariff_group"]
    ].T
    param_results = param_results.pivot(
        index="cost_group", columns="tariff_group", values=param
    )

    if config_workflow["write_results"]:
        param_results.to_csv(
            config_workflow["output_folder"] + param + ".csv", sep=";"
        )

    return param_results

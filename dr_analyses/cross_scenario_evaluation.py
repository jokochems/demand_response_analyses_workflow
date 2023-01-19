from typing import Dict

import pandas as pd

from dr_analyses.container import trim_file_name
from dr_analyses.workflow_routines import make_directory_if_missing


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
    capacity_tariff_share_groups = {
        "0_LP": "0",
        "20_LP": "20",
        "40_LP": "40",
        "60_LP": "60",
        "80_LP": "80",
        "100_LP": "100",
    }
    dynamic_tariff_groups = {
        "0_dynamic": "0",
        "20_dynamic": "20",
        "40_dynamic": "40",
        "60_dynamic": "60",
        "80_dynamic": "80",
        "100_dynamic": "100",
    }
    for key, val in capacity_tariff_share_groups.items():
        overall_results.loc[
            "capacity_tariff_share",
            [col for col in overall_results.columns if key in col],
        ] = val
    for key, val in dynamic_tariff_groups.items():
        overall_results.loc[
            "dynamic_tariff_share",
            [col for col in overall_results.columns if key in col],
        ] = val

    return overall_results


def evaluate_all_parameter_results(
    config_workflow: Dict, overall_results: pd.DataFrame
) -> Dict[str, pd.DataFrame]:
    """Evaluate all parameter results and store them in a dict of DataFrames"""
    all_parameter_results = {}
    for param in overall_results.index:
        if param in ["capacity_tariff_share", "dynamic_tariff_share"]:
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
        [param, "capacity_tariff_share", "dynamic_tariff_share"]
    ].T
    param_results = param_results.pivot(
        index="capacity_tariff_share",
        columns="dynamic_tariff_share",
        values=param,
    )

    if config_workflow["write_results"]:
        data_output_folder = (
            f"{config_workflow['output_folder']}"
            f"{config_workflow['data_output']}"
        )
        make_directory_if_missing(data_output_folder)
        param_results.to_csv(f"{data_output_folder}{param}.csv", sep=";")

    return param_results


def calculate_net_present_values(overall_results: pd.DaraFrame, ):
    """Calculate and return net present values for demand response investments made
    :return:
    """
    pass
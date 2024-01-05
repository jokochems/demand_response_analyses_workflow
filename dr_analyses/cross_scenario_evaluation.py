from typing import Dict

import pandas as pd

from dr_analyses.container import trim_file_name
from dr_analyses.workflow_routines import make_directory_if_missing


def read_scenario_result(config_workflow: Dict, scenario: str) -> pd.Series:
    """Read the scenario result and return it"""
    print(f"Adding results for scenario {scenario} from file.")
    return pd.read_csv(
        f"{config_workflow['output_folder']}"
        f"{config_workflow['load_shifting_focus_cluster']}/"
        f"{trim_file_name(scenario).split('_')[3]}/"
        f"{trim_file_name(scenario)}"
        f"/parameter_summary.csv",
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
        el: el.split("_")[3] for el in overall_results.columns
    }
    dynamic_tariff_groups = {
        el: el.split("_")[1] for el in overall_results.columns
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
    config_workflow: Dict, overall_results: pd.DataFrame, dr_scen: str
) -> Dict[str, pd.DataFrame]:
    """Evaluate all parameter results and store them in a dict of DataFrames"""
    all_parameter_results = {}
    for param in overall_results.index:
        if param in ["capacity_tariff_share", "dynamic_tariff_share"]:
            continue
        else:
            all_parameter_results[param] = evaluate_parameter_results(
                config_workflow, overall_results, param, dr_scen
            )

    return all_parameter_results


def evaluate_parameter_results(
    config_workflow: Dict, overall_results: pd.DataFrame, param: str, dr_scen: str
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
    param_results = sort_data_ascending(param_results)

    if config_workflow["write_results"]:
        data_output_folder = (
            f"{config_workflow['output_folder']}"
            f"{config_workflow['data_output']}"
            f"{config_workflow['load_shifting_focus_cluster']}/"
            f"{dr_scen}/"
        )
        file_name = (
            f"{data_output_folder}{param}_"
            f"{config_workflow['tariff_config']['energy']['min_share']}-"
            f"{config_workflow['tariff_config']['energy']['max_share']}"
            f"_dynamic_"
            f"{config_workflow['tariff_config']['capacity']['min_share']}-"
            f"{config_workflow['tariff_config']['capacity']['max_share']}"
            f"_LP"
        )
        if config_workflow["optional_file_add_on"] != "":
            file_name += config_workflow["optional_file_add_on"]
        make_directory_if_missing(data_output_folder)
        param_results.to_csv(f"{file_name}.csv", sep=";")

    return param_results


def sort_data_ascending(param_results: pd.DataFrame) -> pd.DataFrame:
    """Sort given DataFrame's index and columns in ascending order"""
    # Ensure correct data type
    param_results.index = param_results.index.astype(int)
    param_results.columns = param_results.columns.astype(int)
    param_results = param_results.sort_index().sort_index(axis=1)

    return param_results

from typing import Dict

import pandas as pd
from fameio.source.cli import Config

from dr_analyses.container import Container
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
    return pd.concat(
        [result for result in scenario_results.values()],
        keys=scenario_results.keys(),
        axis=1,
    )


def evaluate_parameter_results(overall_results: pd.DataFrame, param: str) -> pd.DataFrame:
    """Pivot and evaluate parameter results"""
    cost_groups = {
        "low": "low",
        "medium": "medium",
        "high": "high",
        "20": "20"
    }
    tariff_groups = {
        "static_tariff": "static_tariff",
        "DA_plus_static": "DA",
        "DA_plus_dynamic_EEG": "DA_dyn_EEG",
        "RTP_with_caps": "RTP_w_Caps",
        "RTP_without_caps": "RTP_wo_Caps"
    }
    param_results = overall_results.loc[[param]]
    # TODO: Assign cost groups values to be able to do the grouping / pivoting
    overall_results.loc["cost_group"]

from fameio.source.cli import Config

from dr_analyses.results_analysis import calc_load_shifting_results
from dr_analyses.workflow_routines import (
    get_all_yaml_files_in_folder_except,
    make_scenario_config,
    run_amiris,
    convert_amiris_results,
)

config_workflow = {
    "input_folder": "C:/Users/koch_j0/AMIRIS/asgard/input/demand_response",
    "output_folder": "./results/",
    "make_scenario": False,
    "run_amiris": False,
    "convert_results": False,
    "baseline_load_file": "C:/Users/koch_j0/AMIRIS/asgard/result/demand_response_eninnov/00_Evaluation/ind_cluster_shift_only_baseline_load.xlsx",  # noqa: E501
}

config_make = {
    Config.LOG_LEVEL: "error",
    Config.LOG_FILE: None,
    # Config.NUM_PROCESSES: 1,
}

run_properties = {
    "exe": "amiris/amiris-core_1.2-jar-with-dependencies.jar",
    "logging": "-Dlog4j.configuration=file:amiris/log4j.properties",
    "main": "de.dlr.gitlab.fame.setup.FameRunner",
    "setup": "amiris/fameSetup.yaml",
}

config_convert = {
    Config.LOG_LEVEL: "warn",
    Config.LOG_FILE: None,
    Config.AGENT_LIST: None,
    Config.SINGLE_AGENT_EXPORT: False,
}

if __name__ == "__main__":
    to_ignore = ["schema.yaml"]
    scenario_files = get_all_yaml_files_in_folder_except(
        config_workflow["input_folder"], to_ignore
    )
    for scenario in scenario_files:
        if config_workflow["make_scenario"]:
            make_scenario_config(
                scenario, config_make, config_workflow["input_folder"]
            )
        if config_workflow["run_amiris"]:
            run_amiris(run_properties, config_make)
        if config_workflow["convert_results"]:
            convert_amiris_results(
                scenario, config_convert, config_workflow["output_folder"]
            )
        calc_load_shifting_results(
            scenario, config_convert, config_workflow
        )
        # TODO: Resume with aggregation & analysis of results!

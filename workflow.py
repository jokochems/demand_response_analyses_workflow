from fameio.source.cli import Config

from dr_analyses.container import Container
from dr_analyses.cross_scenario_evaluation import (
    read_scenario_result,
    concat_results,
)
from dr_analyses.results_workflow import (
    calc_basic_load_shifting_results,
    obtain_scenario_prices,
    add_power_payments,
    write_results,
)
from dr_analyses.summary import calc_summary_parameters
from dr_analyses.workflow_routines import (
    get_all_yaml_files_in_folder_except,
    make_scenario_config,
    run_amiris,
    convert_amiris_results,
    trim_file_name,
)

config_workflow = {
    "input_folder": "C:/Users/koch_j0/AMIRIS/asgard/input/demand_response",
    "output_folder": "./results/",
    "make_scenario": False,
    "run_amiris": False,
    "convert_results": False,
    "process_results": True,
    "write_results": False,
    "aggregate_results": True,
    "evaluate_cross_scenarios": True,
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
    scenario_results = dict()
    for scenario in scenario_files:
        cont = Container(scenario, config_workflow, config_convert)

        if config_workflow["make_scenario"]:
            make_scenario_config(cont)
        if config_workflow["run_amiris"]:
            run_amiris(run_properties, config_make)
        if config_workflow["convert_results"]:
            convert_amiris_results(cont)
        if config_workflow["process_results"]:
            calc_basic_load_shifting_results(cont)
            obtain_scenario_prices(cont)
            add_power_payments(cont)
            if config_workflow["write_results"]:
                write_results(cont)
        if config_workflow["aggregate_results"]:
            calc_summary_parameters(cont)
            scenario_results[trim_file_name(scenario)] = cont.summary_series
        break

    if config_workflow["evaluate_cross_scenarios"]:
        if len(scenario_results) == 0:
            for scenario in scenario_files:
                scenario_results[
                    trim_file_name(scenario)
                ] = read_scenario_result(config_workflow, scenario)
        concat_results(scenario_results)
        # TODO: Add cross-scenario analysis

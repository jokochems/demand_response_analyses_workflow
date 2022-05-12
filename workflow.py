from fameio.source.cli import Config

from dr_analyses.container import Container
from dr_analyses.cross_run_evaluation import read_param_results_for_runs
from dr_analyses.cross_scenario_evaluation import (
    concat_results,
    evaluate_all_parameter_results,
    read_scenario_result,
)
from dr_analyses.plotting import plot_bar_charts, plot_cross_run_comparison
from dr_analyses.results_summary import calc_summary_parameters
from dr_analyses.results_workflow import (
    add_power_payments,
    calc_basic_load_shifting_results,
    obtain_scenario_and_baseline_prices,
    write_results,
)
from dr_analyses.workflow_routines import (
    convert_amiris_results,
    get_all_yaml_files_in_folder_except,
    make_scenario_config,
    run_amiris,
)

config_workflow = {
    "input_folder": "C:/Users/koch_j0/AMIRIS/asgard/input/demand_response",
    "scenario_subfolder": "/w_capacity_charge",  # "wo_capacity_charge"
    "output_folder": "./results/",
    "make_scenario": False,
    "run_amiris": False,
    "convert_results": False,
    "process_results": False,
    "use_baseline_prices_for_comparison": False,
    "write_results": False,
    "aggregate_results": False,
    "evaluate_cross_scenarios": False,
    "make_plots": False,
    "evaluate_cross_runs": True,
    "runs_to_evaluate": {
        "Analysis_2022-05-05_price_no_repercussions": (
            "without capacity charge"
        ),
        "Analysis_2022-05-12_capacity_charges": "with capacity charge",
    },
    "params_to_evaluate": ["PeakLoadChange", "NetSavings"],
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
    # Add baseline scenario (no dr) separately because of different contracts
    baseline_scenario = get_all_yaml_files_in_folder_except(
        config_workflow["input_folder"] + "/baseline", to_ignore
    )

    scenario_files = baseline_scenario.copy()
    scenario_files.extend(
        get_all_yaml_files_in_folder_except(
            config_workflow["input_folder"]
            + config_workflow["scenario_subfolder"],
            to_ignore,
        )
    )

    scenario_results = {}

    for scenario in scenario_files:
        cont = Container(
            scenario,
            config_workflow,
            config_convert,
            config_make,
            baseline_scenario,
        )

        if config_workflow["make_scenario"]:
            make_scenario_config(cont)
        if config_workflow["run_amiris"]:
            run_amiris(run_properties, cont)
        if config_workflow["convert_results"]:
            convert_amiris_results(cont)
        if config_workflow["process_results"] and "_no_dr" not in scenario:
            calc_basic_load_shifting_results(cont)
            obtain_scenario_and_baseline_prices(cont)
            add_power_payments(
                cont, config_workflow["use_baseline_prices_for_comparison"]
            )
            if config_workflow["write_results"]:
                write_results(cont)
        if config_workflow["aggregate_results"] and "_no_dr" not in scenario:
            calc_summary_parameters(cont)
            scenario_results[cont.trimmed_scenario] = cont.summary_series

    if config_workflow["evaluate_cross_scenarios"]:
        if not scenario_results:
            for scenario in scenario_files:
                scenario_results[
                    Container.trim_file_name(scenario)
                ] = read_scenario_result(config_workflow, scenario)
        overall_results = concat_results(scenario_results)
        all_parameter_results = evaluate_all_parameter_results(
            config_workflow, overall_results
        )
        if config_workflow["make_plots"]:
            plot_bar_charts(config_workflow, all_parameter_results)

    if config_workflow["evaluate_cross_runs"]:
        param_results = read_param_results_for_runs(config_workflow)
        plot_cross_run_comparison(config_workflow, param_results)

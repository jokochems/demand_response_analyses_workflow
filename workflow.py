import shutil

from fameio.source.cli import Options, ResolveOptions

from dr_analyses.container import Container
from dr_analyses.cross_run_evaluation import read_param_results_for_runs
from dr_analyses.cross_scenario_evaluation import (
    concat_results,
    evaluate_all_parameter_results,
    read_scenario_result,
)
from dr_analyses.plotting import (
    plot_bar_charts,
    plot_cross_run_comparison,
    configure_plots, plot_heat_maps,
)
from dr_analyses.results_summary import calc_summary_parameters
from dr_analyses.results_workflow import (
    add_power_payments,
    calc_load_shifting_results,
    obtain_scenario_and_baseline_prices,
    write_results,
    extract_load_shifting_cashflows,
    add_capacity_payments,
    calculate_net_present_values,
    add_discounted_payments_to_results,
)
from dr_analyses.workflow_routines import (
    convert_amiris_results,
    make_scenario_config,
    run_amiris,
    make_directory_if_missing,
    read_load_shifting_template,
    read_load_shedding_template,
    prepare_tariff_configs,
    read_tariff_configs,
    read_investment_expenses,
)
from load_shifting_api.main import LoadShiftingApiThread

config_workflow = {
    "template_folder": "./template/",
    "input_folder": "./inputs/",
    "data_sub_folder": "data",
    "scenario_sub_folder": "scenarios",
    "tariff_config_file": "tariff_configuration",
    "output_folder": "./results/",
    "data_output": "data_out/",
    "plots_output": "plots_out/",
    "demand_response_scenarios": {
        "none": "scenario_wo_dr",
        "5": "scenario_w_dr_5",
        "50": "scenario_w_dr_50",
        "95": "scenario_w_dr_95",
    },
    "load_shifting_focus_cluster": "ind_cluster_shift_only",
    "load_shedding_clusters": [
        "ind_cluster_shed_only",
        "ind_cluster_shift_shed",
        "hoho_cluster_shift_shed",
    ],
    "interest_rate": 0.05,
    "prepare_tariff_config": True,
    "amiris_analyses": {
        "start_web_service": True,
        "make_scenario": True,
        "run_amiris": True,
        "convert_results": True,
        "process_results": True,
        "use_baseline_prices_for_comparison": True,
        "aggregate_results": True,
    },
    "write_results": True,
    "evaluate_cross_scenarios": True,
    "make_plots": True,
    "evaluate_cross_runs": True,
    "runs_to_evaluate": {
        "Analysis_2022-05-05_price_no_repercussions": (
            "without capacity charge"
        ),
        "Analysis_2022-05-12_capacity_charges": "with capacity charge",
    },
    "params_to_evaluate": ["PeakLoadChange", "NetSavings"],
    "baseline_load_file": "baseline_load_profile",
}

config_plotting = {
    "small_size": 12,
    "medium_size": 14,
    "bigger_size": 15,
    "figsize": (10, 7),
    "drop_list": [],
    "rename_dict": {"columns": {}, "rows": {}, "parameters": {}},
    "x_label": None,
    "save_plot": True,
    "show_plot": False,
}

config_make = {
    Options.LOG_LEVEL: "error",
    Options.LOG_FILE: None,
    # Config.NUM_PROCESSES: 1,
}

run_properties = {
    "exe": "amiris/amiris-core_1.2.6-jar-with-dependencies.jar -Xmx16000M",
    "logging": "-Dlog4j.configuration=file:amiris/log4j.properties",
    "main": "de.dlr.gitlab.fame.setup.FameRunner",
    "setup": "amiris/fameSetup.yaml",
}

config_convert = {
    Options.LOG_LEVEL: "warn",
    Options.LOG_FILE: None,
    Options.AGENT_LIST: None,
    Options.OUTPUT: None,  # set in workflow
    Options.SINGLE_AGENT_EXPORT: False,
    Options.MEMORY_SAVING: False,
    Options.RESOLVE_COMPLEX_FIELD: ResolveOptions.SPLIT,
}

if __name__ == "__main__":
    make_directory_if_missing(f"{config_workflow['input_folder']}/scenarios/")
    if config_workflow["prepare_tariff_config"]:
        for dr_scen in config_workflow["demand_response_scenarios"]:
            if dr_scen != "none":
                prepare_tariff_configs(config_workflow, dr_scen)

    # Store templates for reuse
    templates = {
        "tariffs": {},
        "load_shifting": read_load_shifting_template(config_workflow),
        "load_shedding": read_load_shedding_template(config_workflow),
    }

    scenario_files = {}
    investment_expenses = {}
    baseline_scenario = None
    for dr_scen, dr_scen_name in config_workflow[
        "demand_response_scenarios"
    ].items():
        if dr_scen != "none":
            templates["tariffs"][dr_scen] = read_tariff_configs(
                config_workflow, dr_scen
            )
            for tariff in templates["tariffs"][dr_scen]:
                tariff_name = tariff["Name"]

                scenario = (
                    f"{config_workflow['input_folder']}/"
                    f"{config_workflow['scenario_sub_folder']}/"
                    f"{dr_scen_name}_{tariff_name}.yaml"
                )
                shutil.copyfile(
                    f"{config_workflow['template_folder']}/scenario_template_wo_dr.yaml",
                    scenario,
                )
                scenario_files[f"{dr_scen}_{tariff_name}"] = scenario

            investment_expenses[dr_scen] = read_investment_expenses(
                config_workflow,
                dr_scen,
            )

        else:
            scenario = (
                f"{config_workflow['input_folder']}/"
                f"{config_workflow['scenario_sub_folder']}/{dr_scen_name}.yaml"
            )
            shutil.copyfile(
                f"{config_workflow['template_folder']}/scenario_template_wo_dr.yaml",
                scenario,
            )
            scenario_files[dr_scen] = scenario
            baseline_scenario = scenario

    scenario_results = {}

    if config_workflow["amiris_analyses"]["start_web_service"]:
        load_shifting_api_thread = LoadShiftingApiThread()
        load_shifting_api_thread.start()

    for dr_scen, scenario in scenario_files.items():
        cont = Container(
            scenario,
            config_workflow,
            config_convert,
            config_make,
            baseline_scenario,
        )

        if scenario != baseline_scenario:
            cont.add_load_shifting_config(dr_scen, templates)
            cont.update_config_for_scenario(
                dr_scen, templates["load_shedding"]
            )
            cont.save_scenario_yaml()
        else:
            # No need to change config for baseline scenario
            continue

        # Uncomment the following code for dev purposes; Remove once finalized
        # For time reasons, only evaluate two scenarios in dev stadium before moving to cross-scenario comparison
        if dr_scen not in [
            "5_20_dynamic_0_LP",
            "5_0_dynamic_0_LP",
            "5_0_dynamic_20_LP",
        ]:
            continue

        if config_workflow["amiris_analyses"]["make_scenario"]:
            make_scenario_config(cont)
        if config_workflow["amiris_analyses"]["run_amiris"]:
            run_amiris(run_properties, cont)
        if config_workflow["amiris_analyses"]["convert_results"]:
            convert_amiris_results(cont)
        if (
            config_workflow["amiris_analyses"]["process_results"]
            and "_wo_dr" not in scenario
        ):
            obtain_scenario_and_baseline_prices(cont)
            calc_load_shifting_results(cont, dr_scen)
            add_power_payments(
                cont,
                config_workflow["amiris_analyses"][
                    "use_baseline_prices_for_comparison"
                ],
            )
            add_capacity_payments(
                cont,
            )
            add_discounted_payments_to_results(
                [
                    "BaselineTotalPayments",
                    "ShiftingTotalPayments",
                    "VariableShiftingCosts",
                ],
                cont,
            )
            cont.add_cashflows(extract_load_shifting_cashflows(cont))
            cont.add_npv(
                calculate_net_present_values(
                    cont, dr_scen, investment_expenses
                )
            )
            if config_workflow["write_results"]:
                write_results(cont)
        if (
            config_workflow["amiris_analyses"]["aggregate_results"]
            and "_wo_dr" not in scenario
        ):
            calc_summary_parameters(cont)
            scenario_results[cont.trimmed_scenario] = cont.summary_series

    if config_workflow["evaluate_cross_scenarios"]:
        if not scenario_results:
            scenario_files = {
                k: v
                for k, v in scenario_files.items()
                if k
                in [
                    "none",
                    "5_0_dynamic_0_LP",
                    "5_0_dynamic_20_LP",
                    "5_20_dynamic_0_LP",
                ]
            }
            for dr_scen, scenario in scenario_files.items():
                if dr_scen != "none":
                    scenario_results[dr_scen] = read_scenario_result(
                        config_workflow, scenario
                    )
        overall_results = concat_results(scenario_results)

        all_parameter_results = evaluate_all_parameter_results(
            config_workflow, overall_results
        )
        if config_workflow["make_plots"]:
            configure_plots(config_plotting)
            plot_bar_charts(
                config_workflow, all_parameter_results, config_plotting
            )
            plot_heat_maps(
                config_workflow, all_parameter_results, config_plotting
            )

    if config_workflow["evaluate_cross_runs"]:
        param_results = read_param_results_for_runs(config_workflow)
        if len(param_results) > 0:
            plot_cross_run_comparison(config_workflow, param_results)

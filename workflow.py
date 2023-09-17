from dr_analyses.container import Container
from dr_analyses.cross_scenario_evaluation import (
    concat_results,
    evaluate_all_parameter_results,
    read_scenario_result,
)
from dr_analyses.plotting import (
    plot_bar_charts,
    configure_plots,
    plot_heat_maps,
)
from dr_analyses.results_summary import calc_summary_parameters
from dr_analyses.results_workflow import (
    add_power_payments,
    calc_load_shifting_results,
    obtain_scenario_and_baseline_prices,
    write_results,
    extract_load_shifting_cashflows,
    add_capacity_payments,
    calculate_net_present_value,
    add_discounted_payments_to_results,
    calculate_load_shifting_annuity,
    calculate_net_present_value_per_capacity,
)
from dr_analyses.workflow_config import (
    add_args,
    extract_simple_config,
    extract_config_plotting,
    extract_fame_config,
    update_run_properties,
)
from dr_analyses.workflow_routines import (
    convert_amiris_results,
    make_scenario_config,
    run_amiris,
    make_directory_if_missing,
    read_load_shifting_template,
    read_load_shedding_template,
    prepare_tariff_configs,
    initialize_scenario_results_dict,
    prepare_scenario_dicts,
    store_price_forecast_from_baseline,
    read_investment_results_template,
    prepare_tariffs_from_workflow,
    load_yaml_file,
)
from load_shifting_api.main import LoadShiftingApiThread

if __name__ == "__main__":
    args = add_args()
    config_file = load_yaml_file(args.file)
    config_workflow = extract_simple_config(config_file, "config_workflow")
    config_plotting = extract_config_plotting(config_file)
    config_make = extract_fame_config(config_file, "config_make")
    default_run_properties = extract_simple_config(
        config_file, "run_properties"
    )
    config_convert = extract_fame_config(config_file, "config_convert")

    run_properties = {}
    for dr_scen in config_workflow["demand_response_scenarios"]:
        run_properties[dr_scen] = update_run_properties(
            default_run_properties,
            dr_scen,
            config_workflow["load_shifting_focus_cluster"],
        )

    make_directory_if_missing(
        f"{config_workflow['input_folder']}/"
        f"{config_workflow['scenario_sub_folder']}/"
        f"{config_workflow['load_shifting_focus_cluster']}/"
    )
    if config_workflow["prepare_tariff_config"]:
        for dr_scen in config_workflow["demand_response_scenarios"]:
            prepare_tariff_configs(config_workflow, dr_scen)

    templates = {
        "tariffs": {},
        "load_shifting": read_load_shifting_template(config_workflow),
        "load_shedding": read_load_shedding_template(config_workflow),
        "investment_results": read_investment_results_template(
            config_workflow
        ),
    }

    (
        scenario_files,
        investment_expenses,
        fixed_costs,
        baseline_scenarios,
    ) = prepare_scenario_dicts(templates, config_workflow)

    scenario_results = initialize_scenario_results_dict(config_workflow)

    if not config_workflow["amiris_analyses"]["skip_simulation"]:
        if config_workflow["amiris_analyses"]["start_web_service"]:
            load_shifting_api_thread = LoadShiftingApiThread()
            load_shifting_api_thread.start()

            service_url = load_shifting_api_thread.get_url()
            templates["load_shifting"]["Attributes"]["Strategy"]["Api"][
                "ServiceUrl"
            ] = service_url

        for dr_scen, scenario in scenario_files.items():
            dr_scen_short = dr_scen.split("_", 1)[0]
            cont = Container(
                scenario,
                config_workflow,
                config_convert,
                config_make,
                baseline_scenarios[dr_scen_short],
            )

            cont.adapt_simulation_time_frame(
                cont.config_workflow["simulation"]
            )
            cont.adapt_shortage_capacity(
                config_workflow["simulation"][
                    "artificial_shortage_capacity_in_MW"
                ]
            )

            if scenario != baseline_scenarios[dr_scen_short]:
                cont.add_load_shifting_agent(
                    templates["load_shifting"], dr_scen
                )
                if config_workflow["tariff_config"]["mode"] == "from_workflow":
                    prepare_tariffs_from_workflow(cont, templates)
                cont.add_load_shifting_config(dr_scen, templates)
                cont.update_price_forecast(dr_scen)
                cont.change_contract_location(
                    f"{cont.config_workflow['input_folder']}/contracts_w_dr"
                )
            else:
                cont.create_dummy_price_forecast(dr_scen)
                cont.update_price_forecast(dr_scen)

            cont.update_load_shedding_config(
                dr_scen, templates["load_shedding"]
            )
            cont.add_investment_capacities_for_scenario(
                dr_scen, templates["investment_results"]
            )
            cont.update_opex_for_scenario(dr_scen)
            cont.update_all_paths_with_focus_cluster()
            cont.save_scenario_yaml()

            if config_workflow["amiris_analyses"]["make_scenario"]:
                make_scenario_config(cont)
            if config_workflow["amiris_analyses"]["run_amiris"]:
                if not load_shifting_api_thread.is_alive():
                    raise Exception("LoadShiftingAPI is not available.")
                run_amiris(run_properties[dr_scen_short], cont)
            if config_workflow["amiris_analyses"]["convert_results"]:
                convert_amiris_results(cont)
                if scenario == baseline_scenarios[dr_scen_short]:
                    store_price_forecast_from_baseline(cont)
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
                        "VariableShiftingCostsFromOptimiser",
                    ],
                    cont,
                )
                cont.add_cashflows(
                    extract_load_shifting_cashflows(cont, dr_scen, fixed_costs)
                )
                cont.add_npv(
                    calculate_net_present_value(
                        cont, dr_scen, investment_expenses, fixed_costs
                    )
                )
                cont.add_npv_per_capacity(
                    calculate_net_present_value_per_capacity(cont)
                )
                cont.add_annuity(calculate_load_shifting_annuity(cont))
                if config_workflow["write_results"]:
                    write_results(cont)
            if (
                config_workflow["amiris_analyses"]["aggregate_results"]
                and "_wo_dr" not in scenario
            ):
                calc_summary_parameters(cont)
                scenario_results[dr_scen_short][dr_scen] = cont.summary_series

    if config_workflow["evaluate_cross_scenarios"]:
        for dr_scen, scenario in scenario_files.items():
            if "_wo_dr" not in scenario:
                dr_scen_short = dr_scen.split("_", 1)[0]
                # Read only missing entries from file
                if dr_scen not in scenario_results[dr_scen_short].keys():
                    scenario_results[dr_scen_short][
                        dr_scen
                    ] = read_scenario_result(config_workflow, scenario)

        for dr_scen, dr_scen_results in scenario_results.items():
            if "_wo_dr" in dr_scen:
                continue

            overall_results = concat_results(dr_scen_results)

            all_parameter_results = evaluate_all_parameter_results(
                config_workflow, overall_results, dr_scen
            )
            if config_workflow["make_plots"]:
                configure_plots(config_plotting)
                plot_bar_charts(
                    config_workflow,
                    all_parameter_results,
                    config_plotting,
                    dr_scen,
                )
                plot_heat_maps(
                    config_workflow,
                    all_parameter_results,
                    config_plotting,
                    dr_scen,
                )

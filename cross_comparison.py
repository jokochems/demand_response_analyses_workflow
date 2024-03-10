import pandas as pd

from dr_analyses.cross_scenario_evaluation import calc_average_param_results
from dr_analyses.plotting import (
    plot_cross_run_bar_charts,
    plot_cross_run_heatmaps,
    configure_plots,
    plot_sensitivity_comparison,
)
from dr_analyses.workflow_config import (
    add_args,
    extract_simple_config,
    extract_config_plotting,
)
from dr_analyses.workflow_routines import load_yaml_file, prepare_tariffs_list

if __name__ == "__main__":
    args = add_args()
    config_file = load_yaml_file(args.file)
    config_comparison = extract_simple_config(config_file, "config_comparison")
    config_plotting = extract_config_plotting(config_file)

    shares_energy = dict()
    shares_capacity = dict()

    sensitivity_analyses = False
    if "sensitivity" in config_comparison:
        if config_comparison["sensitivity"]["enabled"]:
            sensitivity_analyses = True

    if not sensitivity_analyses:
        for cluster in config_comparison["load_shifting_focus_clusters"]:
            shares_energy[cluster] = dict()
            shares_capacity[cluster] = dict()
            for scenario in config_comparison["demand_response_scenarios"]:
                shares_energy[cluster][scenario] = prepare_tariffs_list(
                    config_comparison["all_tariff_configs"][cluster][scenario],
                    kind="energy",
                )
                shares_capacity[cluster][scenario] = prepare_tariffs_list(
                    config_comparison["all_tariff_configs"][cluster][scenario],
                    kind="capacity",
                )
    else:
        shares_energy = list(range(0, 101, 20))
        shares_capacity = list(range(0, 101, 20))

    results = dict()

    if not sensitivity_analyses:
        for param in config_comparison["params_to_evaluate"]:
            results[param] = dict()
            for cluster in config_comparison["load_shifting_focus_clusters"]:
                results[param][cluster] = dict()
                for dr_scen in config_comparison["demand_response_scenarios"]:
                    file_name = (
                        f"{config_comparison['output_folder']}data_out/"
                        f"{cluster}/{dr_scen}/{param}_"
                        f"{shares_energy[cluster][dr_scen][0]}-"
                        f"{shares_energy[cluster][dr_scen][-1]}_dynamic_"
                        f"{shares_capacity[cluster][dr_scen][0]}-"
                        f"{shares_capacity[cluster][dr_scen][-1]}_LP.csv"
                    )
                    param_results = pd.read_csv(
                        file_name, sep=";", index_col=0
                    )
                    results[param][cluster][dr_scen] = param_results

        configure_plots(config_plotting)
        plot_cross_run_bar_charts(
            config_comparison,
            results,
            config_plotting,
        )

        plot_cross_run_heatmaps(
            config_comparison,
            results,
            config_plotting,
        )

    else:
        for param in config_comparison["params_to_evaluate"]:
            results[param] = dict()
            for sens_param in config_comparison["sensitivity"]["params"]:
                results[param][sens_param] = dict()
                for sens_case in config_comparison["sensitivity"]["cases"]:
                    file_name = (
                        f"{config_comparison['output_folder']}data_out/"
                        f"hoho_cluster_shift_only/50/{param}_"
                        f"{shares_energy[0]}-{shares_energy[-1]}_dynamic_"
                        f"{shares_capacity[0]}-{shares_capacity[-1]}_LP_"
                        f"sensitivity_{sens_param}_{sens_case}.csv"
                    )
                    param_results = pd.read_csv(
                        file_name, sep=";", index_col=0
                    )
                    results[param][sens_param][sens_case] = param_results
                file_name_regular = (
                    f"{config_comparison['output_folder']}data_out/"
                    f"hoho_cluster_shift_only/50/{param}_"
                    f"{shares_energy[0]}-{shares_energy[-1]}_dynamic_"
                    f"{shares_capacity[0]}-{shares_capacity[-1]}_LP.csv"
                )
                param_results = pd.read_csv(
                    file_name_regular, sep=";", index_col=0
                )
                results[param][sens_param]["+/-0"] = param_results

        results_agg = calc_average_param_results(results)
        configure_plots(config_plotting)
        plot_sensitivity_comparison(
            results_agg,
            config_plotting,
            config_comparison,
        )

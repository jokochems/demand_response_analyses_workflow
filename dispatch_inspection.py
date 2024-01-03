import os

from dr_analyses.dispatch_inspection_routines import (
    derive_combined_results,
    retrieve_combined_result,
    slice_combined_result,
)
from dr_analyses.plotting import (
    plot_single_dispatch_pattern,
    configure_plots,
    plot_weekly_dispatch_situations,
)
from dr_analyses.workflow_config import (
    add_args,
    extract_simple_config,
    extract_config_plotting,
)
from dr_analyses.workflow_routines import load_yaml_file

if __name__ == "__main__":
    args = add_args()
    config_file = load_yaml_file(args.file)
    config_workflow = extract_simple_config(config_file, "config_workflow")
    config_dispatch = extract_simple_config(config_file, "config_dispatch")
    config_plotting = extract_config_plotting(config_file)

    if config_workflow["create_combined_results"]:
        # Add combined results for all simulations run so far
        for cluster in next(os.walk(config_dispatch["output_folder"]))[1]:
            if cluster not in config_dispatch["all_clusters"]:
                continue
            else:
                for scenario in next(
                    os.walk(f"{config_dispatch['output_folder']}/{cluster}")
                )[1]:
                    for tariff in os.listdir(
                        f"{config_dispatch['output_folder']}/{cluster}/"
                        f"{scenario}"
                    ):
                        if "wo_dr" not in tariff:
                            try:
                                derive_combined_results(
                                    config_dispatch, scenario, cluster, tariff
                                )
                            except FileNotFoundError:
                                print(
                                    f"Failed for cluster: {cluster}; "
                                    f"scenario: {scenario}; tariff: {tariff}."
                                )
                        else:
                            continue

    if config_workflow["plot_dispatch_situations"]:
        for cluster, tariffs in config_plotting["cases"].items():
            for tariff in tariffs:
                combined_result = retrieve_combined_result(
                    config_dispatch, cluster, tariff
                )
                combined_result_sliced = slice_combined_result(
                    combined_result, config_plotting
                )
                configure_plots(config_plotting)
                plot_single_dispatch_pattern(
                    combined_result_sliced,
                    cluster,
                    tariff,
                    config_plotting,
                    config_dispatch,
                    xtick_frequency=config_plotting["xtick_frequency"],
                )
                if config_plotting["weekly_evaluation"]["enable"]:
                    for week in range(52):
                        combined_result_sliced = slice_combined_result(
                            combined_result,
                            config_plotting,
                            weekly=True,
                            week_counter=week,
                        )
                        plot_weekly_dispatch_situations(
                            combined_result_sliced,
                            cluster,
                            tariff,
                            config_plotting,
                            config_dispatch,
                            week,
                        )

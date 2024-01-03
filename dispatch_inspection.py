import os

from dr_analyses.dispatch_inspection_routines import (
    derive_combined_results,
    retrieve_combined_result,
)
from dr_analyses.workflow_config import (
    add_args,
    extract_simple_config,
)
from dr_analyses.workflow_routines import load_yaml_file

if __name__ == "__main__":
    args = add_args()
    config_file = load_yaml_file(args.file)
    config_workflow = extract_simple_config(config_file, "config_workflow")
    config_dispatch = extract_simple_config(config_file, "config_dispatch")
    config_plotting = extract_simple_config(config_file, "config_plotting")

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
                print("stop")

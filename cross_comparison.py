import warnings

import pandas as pd

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

    shares_energy = prepare_tariffs_list(config_comparison, kind="energy")
    shares_capacity = prepare_tariffs_list(config_comparison, kind="capacity")

    results = dict()
    for cluster in config_comparison["load_shifting_focus_clusters"]:
        results[cluster] = dict()
        for dr_scen in config_comparison["demand_response_scenarios"]:
            file_name = (
                f"{config_comparison['output_folder']}data_out/"
                f"{cluster}/{dr_scen}/NetPresentValuePerCapacity.csv"
            )
            specific_npvs = pd.read_csv(file_name, sep=";", index_col=0)
            if (specific_npvs.index.to_list() != shares_capacity) or (
                specific_npvs.columns.to_list() != shares_energy
            ):
                warnings.warn(
                    "Expected capacity shares and/or dynamic tariff shares "
                    "do not match the results read in! Rerun simulations "
                    "using correct shares!"
                )
            results[cluster][dr_scen] = specific_npvs

    print("Stop here.")

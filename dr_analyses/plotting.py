from typing import Dict, List

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from dr_analyses.workflow_routines import make_directory_if_missing


def configure_plots(config_plotting: Dict) -> None:
    """Update matplotlib plotting paramters"""
    plt.rc("font", size=config_plotting["small_size"])
    plt.rc("axes", titlesize=config_plotting["bigger_size"])
    plt.rc("axes", labelsize=config_plotting["medium_size"])
    plt.rc("xtick", labelsize=config_plotting["small_size"])
    plt.rc("ytick", labelsize=config_plotting["small_size"])
    plt.rc("legend", fontsize=config_plotting["small_size"])
    plt.rc("figure", titlesize=config_plotting["bigger_size"])


def plot_bar_charts(
    config_workflow: Dict,
    all_parameter_results: Dict[str, pd.DataFrame],
    config_plotting: Dict = None,
) -> None:
    """Plot and save bar charts for the different parameters"""
    if not config_plotting:
        config_plotting = {
            "figsize": (9, 6),
            "drop_list": [],
            "rename_dict": {"columns": {}, "rows": {}, "parameters": {}},
            "x_label": None,
        }

    plots_output_folder = (
        f"{config_workflow['output_folder']}{config_workflow['plots_output']}"
    )
    make_directory_if_missing(plots_output_folder)

    for param, param_results in all_parameter_results.items():
        # Do what control freak demands (renaming etc.)
        if len(config_plotting["drop_list"]) > 0:
            param_results = param_results.drop(
                columns=config_plotting["drop_list"]
            )
        if config_plotting["rename_dict"]:
            param_results = param_results.rename(
                index=config_plotting["rename_dict"]["rows"],
                columns=config_plotting["rename_dict"]["columns"],
            )
        if config_plotting["x_label"]:
            param_results.index.name = config_plotting["x_label"]
        if param in config_plotting["rename_dict"]["parameters"]:
            param = config_plotting["rename_dict"]["parameters"][param]
        fig, ax = plt.subplots(figsize=config_plotting["figsize"])
        _ = param_results.plot(
            kind="bar",
            align="center",
            width=0.2,
            ax=ax,
            colormap="Blues",
            edgecolor="darkblue",
        )
        # _ = ax.set_yticks(determine_yaxis_spacing(param_results))
        _ = ax.set_axisbelow(True)
        _ = ax.grid(axis="y", color="lightgrey")
        # _ = plt.legend(
        #     bbox_to_anchor=(1.01, 1),
        #     loc="upper left",
        #     borderaxespad=0.0,
        #     ncol=1,
        # )
        _ = plt.legend(
            bbox_to_anchor=(0.01, 0.98),
            loc="upper left",
            fancybox=False,
            shadow=False,
            ncol=3,
        )
        _ = ax.set_ylabel(param)
        _ = plt.tight_layout()

        _ = fig.savefig(f"{plots_output_folder}{param}.png", dpi=300)
        plt.close(fig)
        # plt.show()


def plot_cross_run_comparison(
    config_workflow: Dict,
    param_results: Dict[str, Dict[str, pd.DataFrame]],
    sharex=True,
) -> None:
    """Compare the results of different runs among each other"""
    runs = config_workflow["runs_to_evaluate"]
    params = config_workflow["params_to_evaluate"]

    fig, axs = plt.subplots(
        len(runs),
        len(params),
        figsize=(10 * len(runs), 6 * len(params)),
        sharey="row",
    )

    col = 0
    for run, run_name in runs.items():
        for row, param in enumerate(params):
            _ = param_results[run][param].plot(
                kind="bar",
                align="center",
                width=0.2,
                ax=axs[row, col],
                colormap="Blues",
                edgecolor="darkblue",
                legend=False,
            )
            _ = axs[row, col].set_axisbelow(True)
            _ = axs[row, col].grid(axis="y", color="lightgrey")
            _ = axs[row, col].set_ylabel(param)
            _ = axs[row, col].set_title(
                f"Parameter {param} for run {run_name}"
            )
            handles, labels = axs[row, col].get_legend_handles_labels()

        col += 1

    _ = plt.legend(
        handles,
        labels,
        loc="upper right",
        borderaxespad=0.0,
        ncol=1,
    )

    _ = plt.tight_layout()

    _ = fig.savefig(
        config_workflow["output_folder"] + "param_comparison" + ".png", dpi=300
    )
    plt.close(fig)
    # plt.show()


def determine_yaxis_spacing(param_results):
    """Determine the yaxis space"""
    max_val = param_results.max().max()
    min_val = param_results.min().min()

    # Determine rounding
    to_subtract_max = 1
    to_subtract_min = to_subtract_max + 1
    if max_val < 0:
        to_subtract_max += 1
    if min_val < 0:
        to_subtract_min += 1

    digits_upper = len(str(max_val * 1.1).split(".")[0]) - to_subtract_max
    digits_lower = len(str(min_val * 1.1).split(".")[0]) - to_subtract_min
    plot_max = np.round(max_val * 1.1, -digits_upper)
    plot_min = np.round(min_val * 1.1, -digits_lower)

    return range(
        min(int(plot_min), 0),
        int(plot_max) + 1,
        max(int((plot_min + plot_max) / 10), 1),
    )

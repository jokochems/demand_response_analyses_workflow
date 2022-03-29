from typing import Dict

import pandas as pd
from matplotlib import pyplot as plt
import numpy as np


# TODO: Develop and inspect plotting routine!
def plot_bar_charts(
    config_workflow: Dict, all_parameter_results: Dict[str, pd.DataFrame]
):
    """Plot and save bar charts for the different parameters"""
    for param, param_results in all_parameter_results.items():
        fig, ax = plt.subplots(figsize=(14, 7))
        _ = param_results.plot(kind="bar", align="center", width=0.2, ax=ax, colormap="Blues", edgecolor="darkblue")
        _ = ax.set_yticks(determine_yaxis_spacing(param_results))
        _ = ax.set_axisbelow(True)
        _ = ax.grid(axis='y', color="lightgrey")
        _ = plt.legend(bbox_to_anchor=(1.01, 1), loc='upper left', borderaxespad=0., ncol=1)
        _ = ax.set_ylabel(param)
        _ = plt.tight_layout()

        _ = fig.savefig(config_workflow["output_folder"] + param + ".png", dpi=300)
        plt.close()


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

    return range(min(int(plot_min), 0), int(plot_max) + 1, max(int((plot_min + plot_max) / 10), 1))
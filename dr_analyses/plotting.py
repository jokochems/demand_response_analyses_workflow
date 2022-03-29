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

        plt.show()


def determine_yaxis_spacing(param_results):
    """Determine the yaxis space"""
    max_val = param_results.max().max()
    # Handle negative values
    if max_val < 0:
        max_val *= (-1)

    # Determine rounding
    digits = len(str(max_val * 1.1).split(".")[0]) - 1
    plot_max = np.round(max_val * 1.1, -2)

    return range(0, int(plot_max) + 1, int(plot_max / 10))
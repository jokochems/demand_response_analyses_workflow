from typing import Dict

import pandas as pd
from matplotlib import pyplot as plt


# TODO: Develop and inspect plotting routine!
def plot_bar_charts(
    config_workflow: Dict, all_parameter_results: Dict[str, pd.DataFrame]
):
    """Plot and save bar charts for the different parameters"""
    for param, param_results in all_parameter_results.items():
        fig, ax = plt.subplots(figsize=(12, 5))
        _ = param_results.plot(kind="bar", ax=ax)
        plt.show()

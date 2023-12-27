import math
from typing import Dict

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.ticker import FuncFormatter

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
    dr_scen: str = "",
) -> None:
    """Plot and save bar charts for the different parameters"""
    if not config_plotting:
        config_plotting = initialize_empty_plot_config()

    plots_output_folder = (
        f"{config_workflow['output_folder']}{config_workflow['plots_output']}"
        f"{config_workflow['load_shifting_focus_cluster']}/{dr_scen}/"
    )
    make_directory_if_missing(plots_output_folder)

    for original_param, param_results in all_parameter_results.items():
        param, param_results = prepare_param_data_for_plotting(
            config_plotting, original_param, param_results
        )
        fig, ax = plt.subplots(figsize=config_plotting["figsize"]["bar"])
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

        _ = plt.legend(
            bbox_to_anchor=(0.01, 0.98),
            loc="upper left",
            fancybox=False,
            shadow=False,
            ncol=3,
        )
        if config_plotting["y_limits"]:
            if original_param in config_plotting["y_limits"]:
                if "log_y" in config_plotting["y_limits"][original_param]:
                    if config_plotting["y_limits"][original_param]["log_y"]:
                        _ = plt.yscale("symlog")
                _ = plt.ylim(
                    float(
                        config_plotting["y_limits"][original_param]["limits"][
                            0
                        ]
                    ),
                    float(
                        config_plotting["y_limits"][original_param]["limits"][
                            1
                        ]
                    ),
                )
        if config_plotting["format_axis"]:
            if param_results.max().max() >= 10:
                _ = ax.get_yaxis().set_major_formatter(
                    FuncFormatter(lambda x, p: format(int(x), ","))
                )
        _ = ax.set_ylabel(param)
        _ = plt.tight_layout()

        if config_plotting["save_plot"]:
            _ = fig.savefig(
                f"{plots_output_folder}{param}_bar.png",
                dpi=300,
                bbox_inches="tight",
            )
        plt.close(fig)
        if config_plotting["show_plot"]:
            plt.show()


def prepare_param_data_for_plotting(
    config_plotting: Dict,
    param: str,
    param_results: pd.DataFrame,
    columns_renaming: bool = True,
):
    """Prepare param data for plotting (renaming etc.)"""
    if len(config_plotting["drop_list"]) > 0:
        param_results = param_results.drop(
            columns=config_plotting["drop_list"]
        )
    if config_plotting["division"]:
        if param in config_plotting["division"]:
            param_results = param_results / float(
                config_plotting["division"][param]
            )
    if config_plotting["rename_dict"]:
        param_results = param_results.rename(
            index=config_plotting["rename_dict"]["rows"],
            columns=config_plotting["rename_dict"]["columns"],
        )
        if columns_renaming:
            if config_plotting["rename_dict"]["derive_column_names"]:
                if config_plotting["rename_dict"]["columns"]:
                    raise UserWarning(
                        "If columns are to be renamed, "
                        "configuration parameter 'derive_column_names' "
                        "has no effect."
                    )
                else:
                    param_results = param_results.rename(
                        columns={
                            col: f"{col}% dyn."
                            for col in param_results.columns
                        },
                    )

        if "index_name" in config_plotting["rename_dict"].keys():
            param_results.index.name = config_plotting["rename_dict"][
                "index_name"
            ][config_plotting["language"]]
        if "columns_name" in config_plotting["rename_dict"].keys():
            param_results.columns.name = config_plotting["rename_dict"][
                "columns_name"
            ][config_plotting["language"]]
    if config_plotting["x_label"]:
        param_results.index.name = config_plotting["x_label"]
    if (
        param
        in config_plotting["rename_dict"]["parameters"][
            config_plotting["language"]
        ]
    ):
        param = config_plotting["rename_dict"]["parameters"][
            config_plotting["language"]
        ][param]

    return param, param_results


def plot_cross_run_comparison(
    config_comparison: Dict,
    all_results: Dict[
        str, Dict[str, Dict[str, Dict[str, pd.DataFrame]]]
    ],
    config_plotting: Dict,
    sharex=True,
) -> None:
    """Compare results of different scenarios / clusters among each other"""
    dr_scenarios = config_comparison["demand_response_scenarios"]
    clusters = config_comparison["load_shifting_focus_clusters"]
    params = config_comparison["params_to_evaluate"]

    fig, axs = plt.subplots(
        len(clusters),
        len(dr_scenarios),
        figsize=(
            config_plotting["figsize"]["bar"][0] * len(dr_scenarios),
            config_plotting["figsize"]["bar"][1] * len(clusters),
        ),
        sharey="row",
    )

    for original_param, param_results in all_parameter_results.items():
        param, param_results = prepare_param_data_for_plotting(
            config_plotting, original_param, param_results
        )

    col = 0
    for run, run_name in clusters.items():
        for row, param in enumerate(params):
            _ = all_results[run][param].plot(
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
        config_comparison["output_folder"] + "param_comparison" + ".png",
        dpi=300,
    )
    plt.close(fig)
    # plt.show()


def initialize_empty_plot_config() -> Dict:
    """Initialize and return an empty config"""
    return {
        "figsize": (8, 8),
        "drop_list": [],
        "rename_dict": {"columns": {}, "rows": {}, "parameters": {}},
        "x_label": None,
        "save_plot": True,
        "show_plot": False,
    }


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


def plot_heat_maps(
    config_workflow: Dict,
    all_parameter_results: Dict[str, pd.DataFrame],
    config_plotting: Dict = None,
    dr_scen: str = "",
) -> None:
    """Plot and save an annotated heat map for given parameters"""
    if not config_plotting:
        config_plotting = initialize_empty_plot_config()

    plots_output_folder = (
        f"{config_workflow['output_folder']}{config_workflow['plots_output']}"
        f"{config_workflow['load_shifting_focus_cluster']}/{dr_scen}/"
    )
    make_directory_if_missing(plots_output_folder)

    for original_param, param_results in all_parameter_results.items():
        param, param_results = prepare_param_data_for_plotting(
            config_plotting,
            original_param,
            param_results,
            columns_renaming=False,
        )
        fig, ax = plt.subplots(figsize=config_plotting["figsize"]["heatmap"])

        data = param_results.astype(float).values
        row_labels = param_results.index.values
        col_labels = param_results.columns.values

        cbar_bounds = derive_cbar_bounds(data, config_plotting, original_param)
        im, cbar = heatmap(
            data,
            row_labels,
            col_labels,
            ax=ax,
            vmin=-cbar_bounds,
            vmax=cbar_bounds,
            cbar_kw={"shrink": 1.0},
            cmap=plt.cm.get_cmap("coolwarm").reversed(),
            cbarlabel=param,
            config_plotting=config_plotting,
        )
        if config_plotting["format_axis"]:
            if data.max().max() >= 10:
                _ = ax.get_yaxis().set_major_formatter(
                    FuncFormatter(lambda x, p: format(int(x), ","))
                )
        annotate = config_plotting["annotate"]
        if annotate:
            _ = annotate_heatmap(im, config_plotting)

        _ = fig.tight_layout()

        if config_plotting["save_plot"]:
            file_name = f"{plots_output_folder}{param}_heatmap"
            if not annotate:
                file_name += "_no_annotations"
            _ = fig.savefig(f"{file_name}.png", dpi=300, bbox_inches="tight")
        plt.close(fig)
        if config_plotting["show_plot"]:
            plt.show()


def derive_cbar_bounds(
    data: np.array, config_plotting: Dict, original_param: str
) -> np.array:
    """Derive the color bar bounds from data or configuration"""
    lower_value = np.nanquantile(data, 0.1)
    upper_value = np.nanquantile(data, 0.9)

    if config_plotting["y_limits"]:
        if original_param in config_plotting["y_limits"]:
            if "cbar_limit" in config_plotting["y_limits"][original_param]:
                cbar_limit = config_plotting["y_limits"][original_param][
                    "cbar_limit"
                ]
            else:
                cbar_limit = 0.8
            lower_value = (
                float(config_plotting["y_limits"][original_param]["limits"][0])
                * cbar_limit
            )
            upper_value = (
                float(config_plotting["y_limits"][original_param]["limits"][1])
                * cbar_limit
            )

    cbar_bounds = (
        np.nanmax(
            [
                np.abs(lower_value),
                np.abs(upper_value),
            ]
        )
        * 1.05
    )
    return cbar_bounds


def heatmap(
    data,
    row_labels,
    col_labels,
    ax=None,
    cbar_kw={},
    cbarlabel="",
    config_plotting={},
    **kwargs,
):
    """
    Create a heatmap from a numpy array and two lists of labels.

    This is the actual plotting routine, taken from the following matplotlib
    example with some minor modifications:
    https://matplotlib.org/stable/gallery/images_contours_and_fields/image_annotated_heatmap.html

    Parameters
    ----------
    data: np.ndarray
        A 2D numpy array of shape (M, N).
    row_labels: list
        A list or array of length M with the labels for the rows.
    col_labels: list
        A list or array of length N with the labels for the columns.
    ax: matplotlib.axes.Axes`
        A `matplotlib.axes.Axes` instance to which the heatmap is plotted.  If
        not provided, use current axes or create a new one.  Optional.
    cbar_kw: dict
        A dictionary with arguments to `matplotlib.Figure.colorbar`.  Optional.
    cbarlabel: str
        The label for the colorbar.  Optional.
    config_plotting: Dict
        Configuration settings for plotting
    **kwargs
        All other arguments are forwarded to `imshow`.
    """  # noqa: E501
    if not ax:
        ax = plt.gca()

    # Plot the heatmap
    im = ax.imshow(data, **kwargs)

    # Create colorbar
    cbar = ax.figure.colorbar(im, ax=ax, **cbar_kw)
    cbar.ax.set_ylabel(cbarlabel, rotation=-90, va="bottom")

    # Show all ticks and label them with the respective list entries.
    ax.set_xticks(np.arange(data.shape[1]), labels=col_labels)
    ax.set_yticks(np.arange(data.shape[0]), labels=row_labels)

    if "index_name" in config_plotting["rename_dict"].keys():
        x_label = config_plotting["rename_dict"]["columns_name"][
            config_plotting["language"]
        ]
    else:
        x_label = "dynamic_share"
    if "columns_name" in config_plotting["rename_dict"].keys():
        y_label = config_plotting["rename_dict"]["index_name"][
            config_plotting["language"]
        ]
    else:
        y_label = "capacity_share"

    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)

    # Let the horizontal axes labeling appear on top.
    ax.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False)
    ax.xaxis.set_label_position("top")

    # Add a grid to the plot
    ax.set_xticks(np.arange(data.shape[1] + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(data.shape[0] + 1) - 0.5, minor=True)
    ax.grid(which="minor", color="k", linestyle="-", linewidth=1)
    ax.tick_params(which="minor", bottom=False, left=False)

    return im, cbar


def annotate_heatmap(
    im,
    config_plotting: Dict,
    data=None,
    textcolors=("black", "white"),
    lower_threshold=0.33,
    upper_threshold=0.67,
    **textkw,
):
    """A function to annotate a heatmap.

    Taken from a matplotlib example:
    https://matplotlib.org/stable/gallery/images_contours_and_fields/image_annotated_heatmap.html,
    accessed 21.01.2023

    Parameters
    ----------
    im: plt.AxesImage
        The AxesImage to be labeled.
    config_plotting: Dict
        Configuration settings for plotting
    data: np.ndarray
        Data used to annotate.  If None, the image's data is used.  Optional.
    textcolors: tuple
        A pair of colors.  The first is used for values below a threshold,
        the second for those above.  Optional.
    lower_threshold: float
        Lower threshold for text color formatting
    upper_threshold: float
        Upper threshold for text color formatting
    **textkw
        All other arguments are forwarded to each call to `text` used to create
        the text labels.
    """  # noqa: E501

    if not isinstance(data, (list, np.ndarray)):
        data = im.get_array()

    # Set default alignment to center, but allow it to be overwritten by textkw.
    kw = dict(
        horizontalalignment="center",
        verticalalignment="center",
        fontsize=config_plotting["very_small_size"],
    )
    kw.update(textkw)

    # Loop over the data and create a `Text` for each "pixel".
    # Change the text's color depending on the data.
    texts = []
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            color_condition = int(
                im.norm(data[i, j]) > upper_threshold
            ) or int(im.norm(data[i, j]) < lower_threshold)
            kw.update(color=textcolors[color_condition])
            try:
                text = im.axes.text(j, i, abbreviate(data[i, j]), **kw)
                texts.append(text)
            except Exception:
                raise

    return texts


def abbreviate(x: float or None) -> str:
    """use scientific notation for abbreviating numbers

    Solution is taken from this stackoverflow issue:
    https://stackoverflow.com/questions/3158132/verbally-format-a-number-in-python

    with some minor modifications in terms of formatting
    """  # noqa: E501
    if isinstance(x, np.ma.core.MaskedConstant):
        return "--"
    x = int(x)
    abbreviations = [
        "",
        r"\cdot 10^{3}",
        r"\cdot 10^{6}",
        r"\cdot 10^{9}",
        r"\cdot 10^{12}",
    ]
    thing = "1"
    a = 0
    # Correct for minus sign in case of negative values
    length = len(str(x)) if x > 0 else len(str(x)) - 1
    while len(thing) <= length - 3:
        thing += "000"
        a += 1
    b = int(thing)
    thing = round(x / b, 2)

    return f"${thing}{abbreviations[a]}$"

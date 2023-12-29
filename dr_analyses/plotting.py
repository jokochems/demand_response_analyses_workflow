import math
from typing import Dict

import matplotlib.axes
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt, gridspec
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
        create_bar_chart(
            original_param,
            param,
            param_results,
            config_plotting,
            ax,
        )
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


def create_bar_chart(
    original_param: str,
    param: str,
    param_results: pd.DataFrame,
    config_plotting: Dict,
    ax: matplotlib.axes.Axes,
    title: None or str = None,
):
    """Create a single bar chart"""
    _ = param_results.plot(
        kind="bar",
        align="center",
        width=0.2,
        ax=ax,
        colormap="Blues",
        edgecolor="darkblue",
    )
    _ = ax.set_axisbelow(True)
    _ = ax.grid(axis="y", color="lightgrey")

    _ = ax.legend(
        bbox_to_anchor=(0.01, 0.98),
        loc="upper left",
        fancybox=False,
        shadow=False,
        ncol=3,
    )
    if title:
        ax.set_title(title)
    if config_plotting["y_limits"]:
        if original_param in config_plotting["y_limits"]:
            if "log_y" in config_plotting["y_limits"][original_param]:
                if config_plotting["y_limits"][original_param]["log_y"]:
                    _ = plt.yscale("symlog")
            _ = ax.set_ylim(
                float(
                    config_plotting["y_limits"][original_param]["limits"][0]
                ),
                float(
                    config_plotting["y_limits"][original_param]["limits"][1]
                ),
            )
    if config_plotting["format_axis"]:
        if param_results.max().max() >= 10:
            _ = ax.get_yaxis().set_major_formatter(
                FuncFormatter(lambda x, p: format(int(x), ","))
            )
    _ = ax.set_ylabel(param)


def plot_cross_run_bar_charts(
    config_comparison: Dict,
    all_results: Dict[str, Dict[str, Dict[str, pd.DataFrame]]],
    config_plotting: Dict,
) -> None:
    """Compare results of different scenarios / clusters among each other

    Create bar charts and choose subplot config dependent on input"""
    dr_scenarios = config_comparison["demand_response_scenarios"]
    dr_clusters = config_comparison["load_shifting_focus_clusters"]

    param_results_dict = dict()
    for original_param, cluster_results in all_results.items():
        param_results_dict[original_param] = dict()
        for cluster, scenario_results in cluster_results.items():
            param_results_dict[original_param][cluster] = dict()
            for scenario, par_results in scenario_results.items():
                param, param_results = prepare_param_data_for_plotting(
                    config_plotting, original_param, par_results
                )
                param_results_dict[original_param][cluster][scenario] = (
                    param,
                    param_results,
                )

    for original_param, cluster_results in param_results_dict.items():
        if len(dr_clusters) != 1:
            fig, axs = plt.subplots(
                len(dr_clusters),
                len(dr_scenarios),
                figsize=(
                    config_plotting["figsize"]["bar"][0] * config_plotting["scaling_factor"],
                    config_plotting["figsize"]["bar"][1] * len(dr_clusters),
                ),
                sharey="row",
            )
        else:
            fig, axs = plt.subplots(
                len(dr_scenarios),
                1,
                figsize=(
                    config_plotting["figsize"]["bar"][0],
                    config_plotting["figsize"]["bar"][1] * len(dr_scenarios),
                ),
            )
        for cluster_number, (cluster, scenario_results) in enumerate(
            cluster_results.items()
        ):
            for scenario_number, (scenario, param_results) in enumerate(
                scenario_results.items()
            ):
                if config_plotting["show_title"]:
                    title = (
                        f"{config_plotting['rename_dict']['clusters'][config_plotting['language']][cluster]}"
                        f" - DR {scenario}"
                    )  # noqa: E501
                else:
                    title = None
                if len(dr_clusters) == 1:
                    axes_argument = axs[scenario_number]
                else:
                    axes_argument = axs[cluster_number, scenario_number]
                create_bar_chart(
                    original_param,
                    param_results[0],
                    param_results[1],
                    config_plotting,
                    axes_argument,
                    title=title,
                )

        _ = plt.tight_layout()
        _ = fig.savefig(
            f"{config_comparison['output_folder']}"
            f"{config_comparison['plots_output']}"
            f"comparison_bar_{param_results[0]}_"
            f"{len(dr_scenarios)}_scenarios_{len(dr_clusters)}_clusters.png",
            dpi=300,
            bbox_inches="tight",
        )
        plt.close(fig)
        if config_plotting["show_plot"]:
            plt.show()


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
    title=None,
    hide_cbar=False,
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
    title : str or None
        Title to display for subplot if not None
    hide_cbar : boolean
        Don't display cbar if True
    **kwargs
        All other arguments are forwarded to `imshow`.
    """  # noqa: E501
    if not ax:
        ax = plt.gca()

    # Plot the heatmap
    im = ax.imshow(data, **kwargs)

    # Create colorbar
    if not hide_cbar:
        cbar = ax.figure.colorbar(im, ax=ax, **cbar_kw)
        cbar.ax.set_ylabel(cbarlabel, rotation=-90, va="bottom")
    else:
        cbar = None

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

    if title:
        ax.set_title(title)

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


def plot_cross_run_heatmaps(
    config_comparison: Dict,
    all_results: Dict[str, Dict[str, Dict[str, pd.DataFrame]]],
    config_plotting: Dict,
) -> None:
    """Compare results of different scenarios / clusters among each other

    Create heatmaps and choose subplot config dependent on input"""
    dr_scenarios = config_comparison["demand_response_scenarios"]
    dr_clusters = config_comparison["load_shifting_focus_clusters"]

    param_results_dict = dict()
    for original_param, cluster_results in all_results.items():
        param_results_dict[original_param] = dict()
        for cluster, scenario_results in cluster_results.items():
            param_results_dict[original_param][cluster] = dict()
            for scenario, par_results in scenario_results.items():
                param, param_results = prepare_param_data_for_plotting(
                    config_plotting, original_param, par_results
                )
                param_results_dict[original_param][cluster][scenario] = (
                    param,
                    param_results,
                )

    for original_param, cluster_results in param_results_dict.items():
        if len(dr_clusters) != 1:
            width_ratios = [1] * len(dr_scenarios) + [0.1]
            height_ratios = [1] * len(dr_clusters)
            gs = gridspec.GridSpec(
                len(dr_clusters),
                len(dr_scenarios) + 1,
                width_ratios=width_ratios,
                height_ratios=height_ratios,
            )
            fig = plt.figure(
                figsize=(
                    config_plotting["figsize"]["heatmap"][0] * config_plotting["scaling_factor"],
                    config_plotting["figsize"]["heatmap"][1]
                    * len(dr_clusters),
                ),
            )
        else:
            fig, axs = plt.subplots(
                len(dr_scenarios),
                1,
                figsize=(
                    config_plotting["figsize"]["heatmap"][0],
                    config_plotting["figsize"]["heatmap"][1]
                    * len(dr_scenarios),
                ),
            )
        for cluster_number, (cluster, scenario_results) in enumerate(
            cluster_results.items()
        ):
            for scenario_number, (scenario, param_results) in enumerate(
                scenario_results.items()
            ):
                title = (
                    f"{config_plotting['rename_dict']['clusters'][config_plotting['language']][cluster]}"
                    f" - DR {scenario}"
                )  # noqa: E501
                if len(dr_clusters) == 1:
                    axes_argument = axs[scenario_number]
                else:
                    axes_argument = plt.subplot(
                        gs[cluster_number, scenario_number]
                    )

                data = param_results[1].astype(float).values
                row_labels = param_results[1].index.values
                col_labels = param_results[1].columns.values

                cbar_bounds = derive_cbar_bounds(
                    data, config_plotting, original_param
                )
                if len(dr_clusters) != 1:
                    hide_cbar = True
                else:
                    hide_cbar = False
                im, cbar = heatmap(
                    data,
                    row_labels,
                    col_labels,
                    ax=axes_argument,
                    vmin=-cbar_bounds,
                    vmax=cbar_bounds,
                    cbar_kw={"shrink": 1.0},
                    cmap=plt.cm.get_cmap("coolwarm").reversed(),
                    cbarlabel=param_results[0],
                    config_plotting=config_plotting,
                    title=title,
                    hide_cbar=hide_cbar,
                )
                if config_plotting["format_axis"]:
                    if data.max().max() >= 10:
                        _ = axes_argument.get_yaxis().set_major_formatter(
                            FuncFormatter(lambda x, p: format(int(x), ","))
                        )
                annotate = config_plotting["annotate"]
                if annotate:
                    _ = annotate_heatmap(im, config_plotting)

                if (
                    len(dr_clusters) > 1
                    and scenario_number == len(dr_scenarios) - 1
                ):
                    cbar_ax = plt.subplot(
                        gs[cluster_number, len(dr_scenarios)]
                    )
                    cbar = plt.colorbar(im, cax=cbar_ax)
                    cbar.ax.set_ylabel(
                        param_results[0], rotation=-90, va="bottom"
                    )

        _ = plt.tight_layout(rect=[0, 0, 0.9, 0.8])

        if config_plotting["save_plot"]:
            file_name = (
                f"{config_comparison['output_folder']}"
                f"{config_comparison['plots_output']}"
                f"comparison_heatmap_{param_results[0]}_{len(dr_scenarios)}_"
                f"scenarios_{len(dr_clusters)}_clusters"
            )
            if not annotate:
                file_name += "_no_annotations"
            _ = fig.savefig(f"{file_name}.png", dpi=300, bbox_inches="tight")
        plt.close(fig)
        if config_plotting["show_plot"]:
            plt.show()

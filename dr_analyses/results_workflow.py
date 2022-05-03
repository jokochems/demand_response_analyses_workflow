import numpy as np
import pandas as pd
from fameio.source.cli import Config

from dr_analyses.container import Container
from dr_analyses.results_subroutines import (
    add_abs_values,
    add_baseline_load_profile,
    calculate_dynamic_price_time_series,
    add_static_prices,
)
from dr_analyses.workflow_routines import trim_file_name


def calc_basic_load_shifting_results(cont: Container) -> None:
    """Create basic results for scenario and add them to Container object

    :param Container cont: container object holding configuration
    """
    cont.config_convert[Config.OUTPUT] = cont.config_workflow[
        "output_folder"
    ] + trim_file_name(cont.scenario)
    results = pd.read_csv(
        f"{cont.config_convert[Config.OUTPUT]}/LoadShiftingTrader.csv", sep=";"
    )

    results = (
        results[[col for col in results.columns if "Offered" not in col]]
        .dropna()
        .reset_index(drop=True)
    )
    add_abs_values(results, ["NetAwardedPower", "StoredMWh"])
    results["ShiftCycleEnd"] = np.where(results["CurrentShiftTime"].diff() < 0, 1, 0)
    add_baseline_load_profile(results, cont.config_workflow["baseline_load_file"])
    results["LoadAfterShifting"] = (
        results["BaselineLoadProfile"] + results["NetAwardedPower"]
    )
    cont.set_results(results)


def obtain_scenario_prices(cont: Container) -> None:
    """Obtain price time-series based on results of scenario

    :param Container cont: container object holding configuration
    """
    cont.set_load_shifting_data()
    dynamic_components = cont.load_shifting_data["Attributes"]["Policy"][
        "DynamicTariffComponents"
    ]
    calculate_dynamic_price_time_series(cont, dynamic_components)
    add_static_prices(cont)


def add_power_payments(cont: Container) -> None:
    """Add power payments to results DataFrame

    :param Container cont: container object holding configuration and results
    """
    cont.results["BaselineTotalPayments"] = 0
    cont.results["ShiftingTotalPayments"] = 0
    for col in cont.power_prices.columns:
        cont.results[f"Baseline{col}Payment"] = (
            cont.results["BaselineLoadProfile"] * cont.power_prices[col]
        )

        cont.results["BaselineTotalPayments"] += cont.results[f"Baseline{col}Payment"]
        cont.results[f"Shifting{col}Payment"] = (
            cont.results["LoadAfterShifting"] * cont.power_prices[col]
        )

        cont.results["ShiftingTotalPayments"] += cont.results[f"Shifting{col}Payment"]


def write_results(cont: Container) -> None:
    """Write load shifting results and consumer price time series to disk"""
    cont.write_results()
    cont.write_power_prices()

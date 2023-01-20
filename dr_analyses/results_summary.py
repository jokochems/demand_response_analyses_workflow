import math

from dr_analyses.container import Container
from dr_analyses.results_workflow import AMIRIS_TIMESTEPS_PER_YEAR


def calc_summary_parameters(cont: Container) -> None:
    """Calculate summary parameters from results time series

    Hereby, payments are overall payments with annual discounting.
    """

    if cont.results is None:
        msg = (
            "There are no results available, reading from disk is not (yet) "
            "implemented.\nFor now, set 'process_results' parameter in "
            "config_workflow dict to True and rerun."
        )
        raise ValueError(msg)

    cont.initialize_summary()
    add_full_shift_cycles(cont)
    add_peak_load_summary(cont)
    add_capacity_charges_summary(cont)
    add_energy_payments_summary(cont)
    add_total_costs_and_savings_summary(cont)
    cont.set_summary_series()
    cont.write_summary()


def add_full_shift_cycles(cont: Container) -> None:
    """Determine and add the number of full shift cycles to summary"""
    full_shift_cycle_energy = (
        cont.load_shifting_data["Attributes"]["LoadShiftingPortfolio"][
            "PowerInMW"
        ]
        * cont.load_shifting_data["Attributes"]["LoadShiftingPortfolio"][
            "MaximumShiftTimeInHours"
        ]
    )

    cont.summary["NoOfFullShiftCycles"] = (
        cont.results["AbsoluteStoredMWh"].sum() / full_shift_cycle_energy
    )


def add_peak_load_summary(cont: Container) -> None:
    """Add overall peak load information to summary"""
    cont.summary["PeakLoadBeforeShifting"] = cont.results[
        "BaselineLoadProfile"
    ].max()
    cont.summary["PeakLoadAfterShifting"] = cont.results[
        "LoadAfterShifting"
    ].max()
    cont.summary["PeakLoadChange"] = (
        cont.summary["PeakLoadAfterShifting"]
        - cont.summary["PeakLoadBeforeShifting"]
    )


def add_capacity_charges_summary(cont: Container) -> None:
    """Add capacity charges information to summary"""
    (
        total_discounted_payments_before,
        total_discounted_payments_after,
    ) = calculate_discounted_capacity_payments(cont)

    cont.summary[
        "CapacityPaymentBeforeShifting"
    ] = total_discounted_payments_before
    cont.summary[
        "CapacityPaymentAfterShifting"
    ] = total_discounted_payments_after
    cont.summary["CapacityPaymentChange"] = (
        cont.summary["CapacityPaymentAfterShifting"]
        - cont.summary["CapacityPaymentBeforeShifting"]
    )


def calculate_discounted_capacity_payments(cont: Container) -> (float, float):
    """Calculate and return discounted capacity payments"""
    nominal_annual_payments_before = list(
        cont.results["BaselineCapacityPayment"]
        .loc[cont.results["BaselineCapacityPayment"] != 0]
        .values
    )
    nominal_annual_payments_after = list(
        cont.results["ShiftingCapacityPayment"]
        .loc[cont.results["ShiftingCapacityPayment"] != 0]
        .values
    )
    # Fill list of annual values with zeros if there is no capacity payment
    if not nominal_annual_payments_before:
        nominal_annual_payments_before = [0] * math.ceil(
            len(cont.results) / AMIRIS_TIMESTEPS_PER_YEAR
        )
        nominal_annual_payments_after = [0] * math.ceil(
            len(cont.results) / AMIRIS_TIMESTEPS_PER_YEAR
        )

    total_discounted_payments_before = sum(
        [
            payment * (1 + cont.config_workflow["interest_rate"]) ** (-year)
            for year, payment in enumerate(nominal_annual_payments_before)
        ]
    )
    total_discounted_payments_after = sum(
        [
            payment * (1 + cont.config_workflow["interest_rate"]) ** (-year)
            for year, payment in enumerate(nominal_annual_payments_after)
        ]
    )

    return total_discounted_payments_before, total_discounted_payments_after


def add_energy_payments_summary(cont: Container) -> None:
    """Add energy-related payments information to summary"""
    cont.summary["EnergyPaymentBeforeShifting"] = cont.results[
        "DiscountedBaselineTotalPayments"
    ].sum()
    cont.summary["EnergyPaymentAfterShifting"] = cont.results[
        "DiscountedShiftingTotalPayments"
    ].sum()
    cont.summary["EnergyPaymentChange"] = (
        cont.summary["EnergyPaymentAfterShifting"]
        - cont.summary["EnergyPaymentBeforeShifting"]
    )


def add_total_costs_and_savings_summary(cont: Container) -> None:
    """Add total costs and savings information to summary"""
    cont.summary["TotalPaymentBeforeShifting"] = (
        cont.summary["CapacityPaymentBeforeShifting"]
        + cont.summary["EnergyPaymentBeforeShifting"]
    )
    cont.summary["TotalPaymentAfterShifting"] = (
        cont.summary["CapacityPaymentAfterShifting"]
        + cont.summary["EnergyPaymentAfterShifting"]
    )
    cont.summary["TotalPaymentChange"] = (
        cont.summary["TotalPaymentAfterShifting"]
        - cont.summary["TotalPaymentBeforeShifting"]
    )
    cont.summary["TotalShiftingCosts"] = cont.results[
        "DiscountedVariableShiftingCosts"
    ].sum()
    cont.summary["NetSavings"] = (
        -cont.summary["TotalPaymentChange"]
        - cont.summary["TotalShiftingCosts"]
    )

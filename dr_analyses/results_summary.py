from dr_analyses.container import Container


def calc_summary_parameters(cont: Container) -> None:
    """Calculate summary parameters from results time series"""

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
        cont.load_shifting_data["Attributes"]["LoadShiftingPortfolio"]["PowerInMW"]
        * cont.load_shifting_data["Attributes"]["LoadShiftingPortfolio"][
            "MaximumShiftTimeInHours"
        ]
    )

    cont.summary["NoOfFullShiftCycles"] = (
        cont.results["AbsoluteStoredMWh"].sum() / full_shift_cycle_energy
    )


def add_peak_load_summary(cont: Container) -> None:
    """Add peak load information to summary"""
    cont.summary["PeakLoadBeforeShifting"] = cont.results["BaselineLoadProfile"].max()
    cont.summary["PeakLoadAfterShifting"] = cont.results["LoadAfterShifting"].max()
    cont.summary["PeakLoadChange"] = (
        cont.summary["PeakLoadAfterShifting"] - cont.summary["PeakLoadBeforeShifting"]
    )


def add_capacity_charges_summary(cont: Container) -> None:
    """Add capacity charges information to summary"""
    capacity_charge = cont.load_shifting_data["Attributes"]["Policy"][
        "CapacityBasedNetworkChargesInEURPerMW"
    ]
    cont.summary["CapacityPaymentBeforeShifting"] = (
        capacity_charge * cont.summary["PeakLoadAfterShifting"]
    )
    cont.summary["CapacityPaymentAfterShifting"] = (
        capacity_charge * cont.summary["PeakLoadAfterShifting"]
    )
    cont.summary["CapacityPaymentChange"] = (
        cont.summary["CapacityPaymentAfterShifting"]
        - cont.summary["CapacityPaymentBeforeShifting"]
    )


def add_energy_payments_summary(cont: Container) -> None:
    """Add energy-related payments information to summary"""
    cont.summary["EnergyPaymentBeforeShifting"] = cont.results[
        "BaselineTotalPayments"
    ].sum()
    cont.summary["EnergyPaymentAfterShifting"] = cont.results[
        "ShiftingTotalPayments"
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
    cont.summary["TotalShiftingCosts"] = cont.results["VariableShiftingCosts"].sum()
    cont.summary["NetSavings"] = (
        -cont.summary["TotalPaymentChange"] - cont.summary["TotalShiftingCosts"]
    )

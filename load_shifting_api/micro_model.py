from typing import List

import pyomo.environ as pyo
from pydantic import BaseModel

from .model.loadshiftmodel import (
    LoadShiftOptimizationModel,
)
from .model.processing import extract_results


class Inputs(BaseModel):
    """Inputs to the load shifting micro-model"""

    # Model parameters from yaml
    peak_load_price: float
    variable_costs_down: List[float]
    variable_costs_up: List[float]
    max_shifting_time: int
    interference_time: int
    peak_demand_before: float
    max_capacity_down: float
    max_capacity_up: float
    efficiency: float
    activate_annual_limits: bool
    solver: str
    max_activations: int
    initial_energy_level: float
    price_sensitivity: float

    # Time series from file
    normalized_baseline_load: List[float]
    energy_price: List[float]
    availability_up: List[float]
    availability_down: List[float]


class ModelResponse(BaseModel):
    """Output from the load shifting micro-model"""

    demand_after: List[float]
    upshift: List[float]
    downshift: List[float]
    overall_variable_costs: float


def micro_model_api(inputs: Inputs) -> ModelResponse:
    """
    Trigger a micro-model run using the given inputs

    Args:
        inputs: Inputs
            Collection of all necessary micro-model inputs

    Returns:
        ModelResponse
    """
    demand_after, upshift, downshift, overall_variable_costs = run_model(
        inputs
    )

    return ModelResponse(
        demand_after=demand_after,
        upshift=upshift,
        downshift=downshift,
        overall_variable_costs=overall_variable_costs,
    )


def run_model(inputs: Inputs):
    """Run load shift optimization model and return model results"""
    lsm = LoadShiftOptimizationModel(
        normalized_baseline_load=inputs.normalized_baseline_load,
        energy_price=inputs.energy_price,
        availability_up=inputs.availability_up,
        availability_down=inputs.availability_down,
        peak_load_price=inputs.peak_load_price,
        variable_costs_down=inputs.variable_costs_down,
        variable_costs_up=inputs.variable_costs_up,
        max_shifting_time=inputs.max_shifting_time,
        interference_time=inputs.interference_time,
        peak_demand_before=inputs.peak_demand_before,
        max_capacity_down=inputs.max_capacity_down,
        max_capacity_up=inputs.max_capacity_up,
        efficiency=inputs.efficiency,
        activate_annual_limits=inputs.activate_annual_limits,
        solver=inputs.solver,
        max_activations=inputs.max_activations,
        initial_energy_level=0,  # inputs.initial_energy_level,
        price_sensitivity=inputs.price_sensitivity,
    )
    extract_results(lsm, rounding_precision=4)

    return (
        lsm.demand_after,
        lsm.upshift,
        lsm.downshift,
        pyo.value(lsm.model.overall_variable_costs),
    )

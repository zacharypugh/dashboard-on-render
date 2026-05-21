from .kinematics import compute_vehicle_kinematics
from .relationships import compute_relationship_metrics
from .safety import compute_safety_metrics


def compute_all_metrics(trial, ma_window=21, safety_params=None):
    trial.metrics.update(compute_vehicle_kinematics(trial, ma_window=ma_window))
    trial.metrics.update(compute_relationship_metrics(trial))
    trial.metrics.update(compute_safety_metrics(trial, params=safety_params))
    return trial

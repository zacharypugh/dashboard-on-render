import numpy as np
from config import OBLIQUE_REFERENCE_SPEED_MPS
from utils import smooth_ma


def compute_dt(t):
    dt = np.diff(t, prepend=t[0])
    dt[dt == 0] = np.nan
    return dt


def compute_vehicle_kinematics(trial, ma_window=21):
    t = trial.timestamps
    t0 = float(t[0]) if len(t) else 0.0
    out = {"vehicle": {}}
    for vehicle, traces in trial.vehicle_traces.items():
        distance = traces["distance"].values.astype(float)
        raw_speed = traces["speed"].values.astype(float)
        lateral = traces["lateral"].values.astype(float)
        lateral_raw = traces.get("lateral_raw", traces["lateral"]).values.astype(float)
        oblique_position = (distance - distance[0]) - OBLIQUE_REFERENCE_SPEED_MPS * (t - t0)

        if len(t) > 1:
            long_acc = np.nan_to_num(np.gradient(raw_speed, t))
            lat_speed = np.nan_to_num(np.gradient(lateral_raw, t))
            lat_acc = np.nan_to_num(np.gradient(lat_speed, t))
        else:
            long_acc = np.zeros_like(raw_speed, dtype=float)
            lat_speed = np.zeros_like(lateral_raw, dtype=float)
            lat_acc = np.zeros_like(lateral_raw, dtype=float)

        out["vehicle"][vehicle] = {
            "distance": distance,
            "oblique_position": oblique_position,
            "speed": smooth_ma(raw_speed, win=ma_window),
            "lateral": lateral,
            "long_acc": smooth_ma(long_acc, win=ma_window),
            "lat_speed": smooth_ma(lat_speed, win=ma_window),
            "lat_acc": smooth_ma(lat_acc, win=ma_window),
        }
    return out

import numpy as np
from config import SAFETY_PARAMS, LANE_DROP_END_BY_SITE, LEFT_TURN_LANE_END_OFFSET_BY_SITE, ALIAS_TO_VEHICLE


def compute_ttc(spacing, closing_speed, vehicle_length=None, params=None):
    params = {**SAFETY_PARAMS, **(params or {})}
    veh_len = float(params["vehicle_length"] if vehicle_length is None else vehicle_length)
    effective_spacing = np.asarray(spacing, dtype=float) - veh_len
    ttc = np.full_like(effective_spacing, np.nan, dtype=float)
    mask = np.isfinite(effective_spacing) & np.isfinite(closing_speed) & (effective_spacing > 0) & (closing_speed > 0)
    ttc[mask] = effective_spacing[mask] / closing_speed[mask]
    return ttc


def compute_drac(spacing, closing_speed, vehicle_length=None, params=None):
    params = {**SAFETY_PARAMS, **(params or {})}
    veh_len = float(params["vehicle_length"] if vehicle_length is None else vehicle_length)
    effective_spacing = np.asarray(spacing, dtype=float) - veh_len
    drac = np.full_like(effective_spacing, np.nan, dtype=float)
    mask = np.isfinite(effective_spacing) & np.isfinite(closing_speed) & (effective_spacing > 0) & (closing_speed > 0)
    drac[mask] = (closing_speed[mask] ** 2) / (2.0 * effective_spacing[mask])
    return drac


def compute_safe_distance(follower_speed, follower_acc, leader_speed, params=None):
    params = {**SAFETY_PARAMS, **(params or {})}
    tau = float(params["reaction_time"])
    b = float(params["braking_deceleration"])

    vf = np.asarray(follower_speed, dtype=float)
    af = np.asarray(follower_acc, dtype=float)
    vl = np.asarray(leader_speed, dtype=float)
    if b <= 0:
        return np.full(vf.shape, np.nan, dtype=float)
    post_reaction_speed = vf + af * tau
    return vf * tau + 0.5 * af * tau ** 2 + (post_reaction_speed ** 2) / (2.0 * b) - (vl ** 2) / (2.0 * b)


def compute_essm(spacing, follower_speed, follower_acc, leader_speed, params=None):
    params = {**SAFETY_PARAMS, **(params or {})}
    veh_len = float(params["vehicle_length"])
    veh_buffer = float(params.get("vehicle_buffer", 0.0))
    safe_distance = compute_safe_distance(follower_speed, follower_acc, leader_speed, params=params)
    essm = np.asarray(spacing, dtype=float) - safe_distance - veh_len - veh_buffer
    essm[~np.isfinite(essm)] = np.nan
    return safe_distance, essm


def summarize_metrics(ttc, drac, essm):
    def _safe_min(x):
        x = np.asarray(x, dtype=float)
        x = x[np.isfinite(x)]
        return float(np.min(x)) if x.size else np.nan
    def _safe_max(x):
        x = np.asarray(x, dtype=float)
        x = x[np.isfinite(x)]
        return float(np.max(x)) if x.size else np.nan
    return {
        "min_ttc": _safe_min(ttc),
        "max_drac": _safe_max(drac),
        "min_essm": _safe_min(essm),
        "max_essm": _safe_max(essm),
    }


def _build_dynamic_x_pair(trial, dynamic_key, output_key, params=None):
    vt = trial.metrics["vehicle"]
    dynamic = trial.metrics["dynamic"][dynamic_key]
    x_dist = vt["LC"]["distance"]
    x_speed = vt["LC"]["speed"]
    x_acc = vt["LC"]["long_acc"]

    alias_series = dynamic["alias"]
    gap_series = dynamic["gap"]
    leader_speed = np.full_like(x_speed, np.nan, dtype=float)
    follower_speed = np.full_like(x_speed, np.nan, dtype=float)
    follower_acc = np.full_like(x_speed, np.nan, dtype=float)
    closing_speed = np.full_like(x_speed, np.nan, dtype=float)

    if dynamic_key == "target_leader":
        # X follows its target leader.
        for alias in ["A", "B", "C"]:
            veh = ALIAS_TO_VEHICLE.get(alias)
            mask = alias_series == alias
            if veh in vt:
                leader_speed[mask] = vt[veh]["speed"][mask]
        spacing = gap_series
        follower_speed = x_speed
        follower_acc = x_acc
        closing_speed = x_speed - leader_speed
        essm_spacing = np.abs(spacing)
    else:
        # Target follower follows X.
        for alias in ["A", "B", "C"]:
            veh = ALIAS_TO_VEHICLE.get(alias)
            mask = alias_series == alias
            if veh in vt:
                follower_speed[mask] = vt[veh]["speed"][mask]
                follower_acc[mask] = vt[veh]["long_acc"][mask]
        spacing = gap_series
        leader_speed = x_speed
        closing_speed = follower_speed - x_speed
        essm_spacing = spacing

    ttc = compute_ttc(spacing, closing_speed)
    drac = compute_drac(spacing, closing_speed)
    safe_distance, essm = compute_essm(essm_spacing, follower_speed, follower_acc, leader_speed, params=params)
    return output_key, {
        "spacing": spacing,
        "essm_spacing": essm_spacing,
        "closing_speed": closing_speed,
        "safe_distance": safe_distance,
        "ttc": ttc,
        "drac": drac,
        "essm": essm,
        **summarize_metrics(ttc, drac, essm),
    }


def _build_static_endpoint_pair(trial, output_key, endpoint_distance, params=None):
    vt = trial.metrics["vehicle"]
    x_dist = vt["LC"]["distance"]
    x_speed = vt["LC"]["speed"]
    x_acc = vt["LC"]["long_acc"]
    spacing = endpoint_distance - x_dist
    leader_speed = np.zeros_like(x_speed)
    closing_speed = x_speed
    ttc = compute_ttc(spacing, closing_speed)
    drac = compute_drac(spacing, closing_speed)
    safe_distance, essm = compute_essm(spacing, x_speed, x_acc, leader_speed, params=params)
    return output_key, {
        "spacing": spacing,
        "closing_speed": closing_speed,
        "safe_distance": safe_distance,
        "ttc": ttc,
        "drac": drac,
        "essm": essm,
        **summarize_metrics(ttc, drac, essm),
    }


def compute_safety_metrics(trial, params=None):
    params = {**SAFETY_PARAMS, **(params or {})}
    vt = trial.metrics["vehicle"]
    pairwise = trial.metrics["pairwise"]
    out = {"safety": {}}

    for out_key, front_alias, rear_alias in [("BA", "A", "B"), ("CB", "B", "C")]:
        front = ALIAS_TO_VEHICLE.get(front_alias)
        rear = ALIAS_TO_VEHICLE.get(rear_alias)
        if front in vt and rear in vt:
            spacing = vt[front]["distance"] - vt[rear]["distance"]
            closing_speed = vt[rear]["speed"] - vt[front]["speed"]
            safe_distance, essm = compute_essm(spacing, vt[rear]["speed"], vt[rear]["long_acc"], vt[front]["speed"], params=params)
            ttc = compute_ttc(spacing, closing_speed)
            drac = compute_drac(spacing, closing_speed)
            out["safety"][out_key] = {
                "spacing": spacing,
                "closing_speed": closing_speed,
                "safe_distance": safe_distance,
                "ttc": ttc,
                "drac": drac,
                "essm": essm,
                **summarize_metrics(ttc, drac, essm),
            }

    if "LC" in vt:
        k, payload = _build_dynamic_x_pair(trial, "target_leader", "X_TARGET_LEADER", params=params)
        out["safety"][k] = payload
        k, payload = _build_dynamic_x_pair(trial, "target_follower", "TARGET_FOLLOWER_X", params=params)
        out["safety"][k] = payload

        if trial.site_id in LANE_DROP_END_BY_SITE:
            lane_drop_endpoint = LANE_DROP_END_BY_SITE[trial.site_id]
            k, payload = _build_static_endpoint_pair(trial, "X_LEFT_TURN_LANE_END", lane_drop_endpoint, params=params)
            out["safety"][k] = payload
            left_turn_endpoint = lane_drop_endpoint + LEFT_TURN_LANE_END_OFFSET_BY_SITE[trial.site_id]
            k, payload = _build_static_endpoint_pair(trial, "X_LANE_DROP_END", left_turn_endpoint, params=params)
            out["safety"][k] = payload

    return out

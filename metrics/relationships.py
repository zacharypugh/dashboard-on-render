import numpy as np
from config import ALIAS_TO_VEHICLE
from utils import safe_divide


HEADWAY_CENTER_OFFSET_M = 7.0


LONGITUDINAL_PAIR_SPECS = {
    "AB": ("A", "B"),
    "BC": ("B", "C"),
    "XA": ("X", "A"),
    "XB": ("X", "B"),
    "XC": ("X", "C"),
    "BA": ("B", "A"),
    "CB": ("C", "B"),
}


def _resolve_vehicle(alias):
    return ALIAS_TO_VEHICLE.get(alias)


def spacing_between(vt, first_alias, second_alias):
    v1 = _resolve_vehicle(first_alias)
    v2 = _resolve_vehicle(second_alias)
    if v1 not in vt or v2 not in vt:
        return None
    return vt[v1]["distance"] - vt[v2]["distance"]


def closing_speed_for_front_rear(vt, front_alias, rear_alias):
    front = _resolve_vehicle(front_alias)
    rear = _resolve_vehicle(rear_alias)
    if front not in vt or rear not in vt:
        return None
    return vt[rear]["speed"] - vt[front]["speed"]


def headway_for_front_rear(vt, front_alias, rear_alias):
    spacing = spacing_between(vt, front_alias, rear_alias)
    rear = _resolve_vehicle(rear_alias)
    if spacing is None or rear not in vt:
        return None
    return safe_divide(np.asarray(spacing, dtype=float), vt[rear]["speed"])


def tau_for_front_rear(vt, front_alias, rear_alias):
    spacing = spacing_between(vt, front_alias, rear_alias)
    rear = _resolve_vehicle(rear_alias)
    if spacing is None or rear not in vt:
        return None
    return safe_divide(np.asarray(spacing, dtype=float) - HEADWAY_CENTER_OFFSET_M, vt[rear]["speed"])


def determine_dynamic_x_targets(trial):
    vt = trial.metrics["vehicle"]
    x = vt.get("LC")
    if x is None:
        return {"target_leader": None, "target_follower": None}

    x_dist = x["distance"]
    candidates = []
    for alias in ["A", "B", "C"]:
        vehicle = _resolve_vehicle(alias)
        if vehicle in vt:
            candidates.append((alias, vt[vehicle]["distance"]))

    leader_gap = None
    leader_alias = None
    follower_gap = None
    follower_alias = None

    for alias, dist in candidates:
        gap = dist - x_dist
        if leader_gap is None:
            leader_gap = np.where(gap > 0, gap, np.nan)
            leader_alias = np.full_like(gap, alias, dtype=object)
            follower_gap = np.where(gap < 0, -gap, np.nan)
            follower_alias = np.full_like(gap, alias, dtype=object)
        else:
            better_leader = np.isfinite(gap) & (gap > 0) & (~np.isfinite(leader_gap) | (gap < leader_gap))
            leader_gap = np.where(better_leader, gap, leader_gap)
            leader_alias = np.where(better_leader, alias, leader_alias)

            follower_candidate = np.where(gap < 0, -gap, np.nan)
            better_follower = np.isfinite(follower_candidate) & (~np.isfinite(follower_gap) | (follower_candidate < follower_gap))
            follower_gap = np.where(better_follower, follower_candidate, follower_gap)
            follower_alias = np.where(better_follower, alias, follower_alias)

    return {
        "target_leader": {"alias": leader_alias, "gap": leader_gap},
        "target_follower": {"alias": follower_alias, "gap": follower_gap},
    }


def compute_relationship_metrics(trial):
    vt = trial.metrics["vehicle"]
    out = {"pairwise": {}, "dynamic": {}}

    for pair_key, (first_alias, second_alias) in LONGITUDINAL_PAIR_SPECS.items():
        out["pairwise"][pair_key] = {
            "first": first_alias,
            "second": second_alias,
            "spacing": spacing_between(vt, first_alias, second_alias),
            "headway": headway_for_front_rear(vt, first_alias, second_alias),
            "tau": tau_for_front_rear(vt, first_alias, second_alias),
        }

    # Safety-oriented front/rear pairs.
    for pair_key, (front_alias, rear_alias) in {"BA": ("A", "B"), "CB": ("B", "C")}.items():
        out["pairwise"][pair_key].update({
            "front": front_alias,
            "rear": rear_alias,
            "closing_speed": closing_speed_for_front_rear(vt, front_alias, rear_alias),
            "time_gap": tau_for_front_rear(vt, front_alias, rear_alias),
        })

    dynamic = determine_dynamic_x_targets(trial)
    out["dynamic"] = dynamic
    if dynamic.get("target_leader") is not None:
        follower_speed = vt.get("LC", {}).get("speed")
        out["pairwise"]["TL_X"] = {
            "first": "TL",
            "second": "X",
            "spacing": dynamic["target_leader"]["gap"],
            "headway": safe_divide(np.asarray(dynamic["target_leader"]["gap"], dtype=float), follower_speed) if follower_speed is not None else None,
            "tau": safe_divide(np.asarray(dynamic["target_leader"]["gap"], dtype=float) - HEADWAY_CENTER_OFFSET_M, follower_speed) if follower_speed is not None else None,
        }
    if dynamic.get("target_follower") is not None:
        follower_alias = np.asarray(dynamic["target_follower"]["alias"], dtype=object)
        follower_speed = np.full_like(dynamic["target_follower"]["gap"], np.nan, dtype=float)
        for alias in ["A", "B", "C"]:
            vehicle = _resolve_vehicle(alias)
            if vehicle in vt:
                mask = follower_alias == alias
                follower_speed[mask] = vt[vehicle]["speed"][mask]
        out["pairwise"]["X_TF"] = {
            "first": "X",
            "second": "TF",
            "spacing": dynamic["target_follower"]["gap"],
            "headway": safe_divide(np.asarray(dynamic["target_follower"]["gap"], dtype=float), follower_speed),
            "tau": safe_divide(np.asarray(dynamic["target_follower"]["gap"], dtype=float) - HEADWAY_CENTER_OFFSET_M, follower_speed),
        }
    return out

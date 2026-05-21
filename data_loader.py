import os
from datetime import datetime
import numpy as np
import pandas as pd
import pytz

from models import TrialData
from config import REPORT_EVENT_COLUMN_CANDIDATES


eastern = pytz.timezone("US/Eastern")


def _merge_report_into_lookup(lookup, report_df, prefix=None):
    for _, mrow in report_df.iterrows():
        serial = int(float(mrow["Serial Number"]))
        ds = int(float(mrow["DS"]))
        dv = int(float(mrow["DV"]))
        key = (serial, ds, dv)
        merged = lookup.get(key, {}).copy()
        row_dict = mrow.to_dict()
        if prefix:
            row_dict = {
                (column if column in {"Serial Number", "DS", "DV"} else f"{prefix}{column}"): value
                for column, value in row_dict.items()
            }
        merged.update(row_dict)
        lookup[key] = merged
    return lookup


def build_lookup_from_report(event_file_path, verification_event_file_path=None, los_event_file_path=None, lc_detection_file_path=None, lc_direct_detection_file_path=None, follower_decel_detection_file_path=None, follower_profile_detection_file_path=None):
    event_df = pd.read_excel(event_file_path)
    lookup = {}
    lookup = _merge_report_into_lookup(lookup, event_df)
    if verification_event_file_path and os.path.exists(verification_event_file_path):
        verification_df = pd.read_excel(verification_event_file_path)
        lookup = _merge_report_into_lookup(lookup, verification_df)
    if los_event_file_path and os.path.exists(los_event_file_path):
        los_df = pd.read_excel(los_event_file_path)
        lookup = _merge_report_into_lookup(lookup, los_df)
    if lc_detection_file_path and os.path.exists(lc_detection_file_path):
        lc_detection_df = pd.read_excel(lc_detection_file_path)
        lookup = _merge_report_into_lookup(lookup, lc_detection_df, prefix="slope__")
    if lc_direct_detection_file_path and os.path.exists(lc_direct_detection_file_path):
        lc_direct_detection_df = pd.read_excel(lc_direct_detection_file_path)
        lookup = _merge_report_into_lookup(lookup, lc_direct_detection_df, prefix="direct__")
    if follower_decel_detection_file_path and os.path.exists(follower_decel_detection_file_path):
        follower_decel_detection_df = pd.read_excel(follower_decel_detection_file_path)
        lookup = _merge_report_into_lookup(lookup, follower_decel_detection_df, prefix="follower_slope__")
    if follower_profile_detection_file_path and os.path.exists(follower_profile_detection_file_path):
        follower_profile_detection_df = pd.read_excel(follower_profile_detection_file_path)
        lookup = _merge_report_into_lookup(lookup, follower_profile_detection_df, prefix="follower_profile__")
    return lookup


def parse_key_from_filename(fp):
    base = os.path.basename(fp)
    if base.startswith('~$'):
        raise ValueError(f"Skipping Excel temp file: {base}")
    serial = int(base.split("_")[0].lstrip("S"))
    ds = int(base.split("_")[1].lstrip("DS"))
    dv = int(base.split("_")[2].split(".")[0].lstrip("DV"))
    return serial, ds, dv


def _get_first_numeric(row_dict, column_names, default=None):
    for name in column_names:
        if name in row_dict and pd.notna(row_dict[name]):
            try:
                return float(row_dict[name])
            except Exception:
                pass
    return default


def _get_first_int(row_dict, column_names, default=None):
    for name in column_names:
        if name in row_dict and pd.notna(row_dict[name]):
            try:
                return int(float(row_dict[name]))
            except Exception:
                pass
    return default


def _normalize_gap_value(value):
    if value is None or pd.isna(value):
        return None
    text = str(value).strip().lower().replace('_', ' ').replace('-', ' ')
    if text in {'0', 'zero', 'gap 0', 'gap zero'}:
        return 'zero'
    if text in {'1', 'first', 'gap 1', 'gap first'}:
        return 'first'
    if text in {'2', 'second', 'gap 2', 'gap second'}:
        return 'second'
    return text


def _resolve_los_time(row_dict):
    gap_value = None
    for name in ['Gap', 'Initial Gap']:
        if name in row_dict and pd.notna(row_dict[name]):
            gap_value = row_dict[name]
            break
    gap_key = _normalize_gap_value(gap_value)
    column_candidates = {
        'zero': ['A_LOS_Time', 'LOS Time A', 'LOS A', 'LOS Time_A'],
        'first': ['B_LOS_Time', 'LOS Time B', 'LOS B', 'LOS Time_B'],
        'second': ['C_LOS_Time', 'LOS Time C', 'LOS C', 'LOS Time_C'],
    }
    if gap_key in column_candidates:
        return _get_first_numeric(row_dict, column_candidates[gap_key])
    return _get_first_numeric(row_dict, REPORT_EVENT_COLUMN_CANDIDATES.get('los_sec', []))


def _resolve_slope_lc_detection_times(row_dict):
    threshold_columns = [
        "slope__LC Start @0.10 time",
        "slope__LC Start @0.15 time",
        "slope__LC Start @0.25 time",
    ]
    threshold_values = [
        value for value in (_get_first_numeric(row_dict, [column]) for column in threshold_columns)
        if value is not None and np.isfinite(value)
    ]
    if threshold_values:
        min_time = float(min(threshold_values))
        max_time = float(max(threshold_values))
        return min_time, max_time

    min_time = _get_first_numeric(
        row_dict,
        [f"slope__{name}" for name in REPORT_EVENT_COLUMN_CANDIDATES.get("lc_start_sec", [])],
    )
    max_time = _get_first_numeric(
        row_dict,
        [f"slope__{name}" for name in REPORT_EVENT_COLUMN_CANDIDATES.get("lc_start_band_max_sec", [])],
    )
    if min_time is not None and max_time is not None and max_time < min_time:
        min_time, max_time = max_time, min_time
    return min_time, max_time


def _resolve_slope_lc_end_detection_times(row_dict):
    threshold_columns = [
        "slope__LC End @0.10 time",
        "slope__LC End @0.15 time",
        "slope__LC End @0.25 time",
    ]
    threshold_values = [
        value for value in (_get_first_numeric(row_dict, [column]) for column in threshold_columns)
        if value is not None and np.isfinite(value)
    ]
    if threshold_values:
        return float(min(threshold_values)), float(max(threshold_values))

    min_time = _get_first_numeric(
        row_dict,
        [f"slope__{name}" for name in REPORT_EVENT_COLUMN_CANDIDATES.get("lc_end_sec", [])],
    )
    max_time = _get_first_numeric(
        row_dict,
        [f"slope__{name}" for name in REPORT_EVENT_COLUMN_CANDIDATES.get("lc_end_band_max_sec", [])],
    )
    if min_time is not None and max_time is not None and max_time < min_time:
        min_time, max_time = max_time, min_time
    return min_time, max_time

def _resolve_direct_lc_detection_times(row_dict):
    threshold_columns = [
        "direct__LC Start Time @ 0.1",
        "direct__LC Start Time @ 0.15",
        "direct__LC Start Time @ 0.25",
        "direct__LC Start Time @ 0.10",
        "direct__LC Start Time @0.1",
        "direct__LC Start Time @0.15",
        "direct__LC Start Time @0.25",
    ]
    threshold_values = [
        value for value in (_get_first_numeric(row_dict, [column]) for column in threshold_columns)
        if value is not None and np.isfinite(value)
    ]
    if threshold_values:
        return float(min(threshold_values)), float(max(threshold_values))

    direct_value = _get_first_numeric(row_dict, ["direct__LC Start Time"])
    return direct_value, direct_value


def _resolve_direct_lc_end_detection_times(row_dict):
    threshold_columns = [
        "direct__LC End Time @ 0.1",
        "direct__LC End Time @ 0.15",
        "direct__LC End Time @ 0.25",
        "direct__LC End Time @ 0.10",
        "direct__LC End Time @0.1",
        "direct__LC End Time @0.15",
        "direct__LC End Time @0.25",
    ]
    threshold_values = [
        value for value in (_get_first_numeric(row_dict, [column]) for column in threshold_columns)
        if value is not None and np.isfinite(value)
    ]
    if threshold_values:
        return float(min(threshold_values)), float(max(threshold_values))

    direct_value = _get_first_numeric(row_dict, ["direct__LC End Time"])
    return direct_value, direct_value


def _resolve_follower_decel_detection_range(row_dict, follower_alias):
    threshold_columns = [
        f"follower_slope__{follower_alias} Braking SlopeReg1s @0.10 time",
        f"follower_slope__{follower_alias} Braking SlopeReg1s @0.15 time",
        f"follower_slope__{follower_alias} Braking SlopeReg1s @0.25 time",
    ]
    threshold_values = [
        value for value in (_get_first_numeric(row_dict, [column]) for column in threshold_columns)
        if value is not None and np.isfinite(value)
    ]
    if not threshold_values:
        return None, None
    return float(min(threshold_values)), float(max(threshold_values))


def _build_case_name(row_dict):
    serial_str = str(int(float(row_dict["Serial Number"])))
    config_str = str(row_dict.get("Configuration", "ConfigUnknown")).strip().replace("/", "_")
    ds_str = f"DS{int(float(row_dict['DS']))}"
    dv_str = f"DV{int(float(row_dict['DV']))}"
    return f"{serial_str}_{config_str}_{ds_str}_{dv_str}"


def list_available_cases(merged_folder, event_file_path, verification_event_file_path=None, los_event_file_path=None, lc_detection_file_path=None, lc_direct_detection_file_path=None, follower_decel_detection_file_path=None, follower_profile_detection_file_path=None):
    lookup = build_lookup_from_report(
        event_file_path,
        verification_event_file_path=verification_event_file_path,
        los_event_file_path=los_event_file_path,
        lc_detection_file_path=lc_detection_file_path,
        lc_direct_detection_file_path=lc_direct_detection_file_path,
        follower_decel_detection_file_path=follower_decel_detection_file_path,
        follower_profile_detection_file_path=follower_profile_detection_file_path,
    )
    filepaths = sorted([
        os.path.join(merged_folder, f)
        for f in os.listdir(merged_folder)
        if f.lower().endswith(".xlsx") and not f.startswith("~$")
    ])
    cases = []
    for fp in filepaths:
        try:
            key = parse_key_from_filename(fp)
            if key not in lookup:
                continue
            row = lookup[key]
            case_name = _build_case_name(row)
            cases.append({
                "case_name": case_name,
                "file_path": fp,
                "file_name": os.path.basename(fp),
                "key": key,
            })
        except Exception as e:
            print(f"Failed to index {fp}: {e}")
    return cases, lookup


def process_one_trial(row_dict, file_path):
    df = pd.read_excel(file_path).sort_values(by="Raw_Timestamp")
    timestamps = np.sort(df["Raw_Timestamp"].unique()).astype(float)

    date_str = str(row_dict.get("Date", "")).split()[0]
    start_str = str(row_dict.get("Start Time", "00:00:00"))
    try:
        _ = eastern.localize(datetime.strptime(f"{date_str} {start_str}", "%Y-%m-%d %H:%M:%S"))
    except Exception:
        pass

    vehicle_traces = {}
    for vehicle in df["VehicleType"].unique():
        sub = df[df["VehicleType"] == vehicle].copy()
        def series_from(col, smooth=False):
            s = pd.Series(sub[col].values, index=sub["Raw_Timestamp"]).reindex(timestamps).interpolate().ffill().bfill()
            return s.rolling(window=20, center=True, min_periods=1).mean() if smooth else s

        vehicle_traces[vehicle] = {
            "distance": series_from("LongDist_LeftLane_m (Common Reference)"),
            "speed": series_from("Speed_mps"),
            "lateral_raw": series_from("LatDist_LeftLane_m", smooth=False),
            "lateral": series_from("LatDist_LeftLane_m", smooth=True),
        }

    event_times = {
        key: _get_first_numeric(row_dict, cols)
        for key, cols in REPORT_EVENT_COLUMN_CANDIDATES.items()
        if key not in {"site_id", "los_sec", "lc_start_band_min_sec", "lc_start_band_max_sec"}
    }
    event_times["los_sec"] = _resolve_los_time(row_dict)
    event_times["lc_start_band_min_sec"] = event_times.get("lc_start_sec")
    event_times["lc_start_band_max_sec"] = event_times.get("lc_start_sec")
    event_times["lc_end_band_min_sec"] = event_times.get("lc_end_sec")
    event_times["lc_end_band_max_sec"] = event_times.get("lc_end_sec")
    slope_lc_start_min, slope_lc_start_max = _resolve_slope_lc_detection_times(row_dict)
    slope_lc_end_min, slope_lc_end_max = _resolve_slope_lc_end_detection_times(row_dict)
    direct_lc_start_min, direct_lc_start_max = _resolve_direct_lc_detection_times(row_dict)
    direct_lc_end_min, direct_lc_end_max = _resolve_direct_lc_end_detection_times(row_dict)
    event_times["slope_lc_start_sec"] = slope_lc_start_min
    event_times["slope_lc_time_sec"] = slope_lc_start_max
    event_times["slope_lc_end_sec"] = slope_lc_end_min
    event_times["slope_lc_end_time_sec"] = slope_lc_end_max
    event_times["direct_lc_start_sec"] = direct_lc_start_min
    event_times["direct_lc_time_sec"] = direct_lc_start_max
    event_times["direct_lc_end_sec"] = direct_lc_end_min
    event_times["direct_lc_end_time_sec"] = direct_lc_end_max
    f1_band_min, f1_band_max = _resolve_follower_decel_detection_range(row_dict, "F1")
    f2_band_min, f2_band_max = _resolve_follower_decel_detection_range(row_dict, "F2")
    event_times["follower_decel_vehicle"] = None
    event_times["f1_dec_band_min_sec"] = event_times.get("f1_dec_sec")
    event_times["f1_dec_band_max_sec"] = event_times.get("f1_dec_sec")
    event_times["f2_dec_band_min_sec"] = event_times.get("f2_dec_sec")
    event_times["f2_dec_band_max_sec"] = event_times.get("f2_dec_sec")
    event_times["follower_slope_f1_dec_min_sec"] = f1_band_min
    event_times["follower_slope_f1_dec_max_sec"] = f1_band_max
    event_times["follower_slope_f2_dec_min_sec"] = f2_band_min
    event_times["follower_slope_f2_dec_max_sec"] = f2_band_max
    site_id = _get_first_int(row_dict, REPORT_EVENT_COLUMN_CANDIDATES["site_id"], default=None)
    case_name = _build_case_name(row_dict)

    return TrialData(
        timestamps=timestamps,
        vehicle_traces=vehicle_traces,
        event_times=event_times,
        case_name=case_name,
        label=os.path.basename(file_path),
        site_id=site_id,
        raw_report_row=row_dict,
    )


def load_trial_by_case(case_name, case_index, lookup):
    meta = case_index[case_name]
    row_dict = lookup[tuple(meta["key"])]
    return process_one_trial(row_dict, meta["file_path"])

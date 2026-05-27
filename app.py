import os
import re
from copy import deepcopy
import dash
import numpy as np
from dash import Dash, dcc, html, Input, Output, State, ALL, callback_context, dash_table
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from flask import abort, request, Response, send_file

from config import (
    APP_TITLE,
    BASIC_AUTH_ENABLED,
    BASIC_AUTH_USERNAME,
    BASIC_AUTH_PASSWORD,
    LOCAL_PORT,
    RUN_MODE,
    SHARE_PORT,
    EXPERIMENT_TYPE,
    MERGED_FOLDER,
    EVENT_FILE_PATH,
    EXPORT_FOLDER,
    WINDOW_PRE_EVENT_SEC,
    WINDOW_POST_EVENT_SEC,
    DEFAULT_MA_WINDOW,
    PLOT_GROUPS,
    LC_DETECTION_METHODS,
    FOLLOWER_DECEL_METHODS,
    EVENT_LINE_STYLES,
    LANE_DROP_END_BY_SITE,
    LEFT_TURN_LANE_END_OFFSET_BY_SITE,
    get_experiment_paths,
)
from data_loader import list_available_cases, load_trial_by_case
from metrics import compute_all_metrics
from plots.builders import build_combined_figure, build_single_plot_figure, build_summary_rows, add_event_lines, add_detection_bands
from plots.registry import PLOT_SPECS
from ui.layout import build_layout, plot_card
from exports.html_export import export_trial_pngs
from utils import clamp_range

# --- Globus Integration ---
from globus_storage import ensure_local, list_remote_dir, cache_path

app = Dash(__name__, suppress_callback_exceptions=True)
app.title = APP_TITLE
server = app.server


def _auth_ok(auth):
    return (
        auth
        and auth.username == BASIC_AUTH_USERNAME
        and auth.password == BASIC_AUTH_PASSWORD
    )


@server.before_request
def require_basic_auth():
    if not BASIC_AUTH_ENABLED:
        return None
    auth = request.authorization
    if _auth_ok(auth):
        return None
    return Response(
        "Authentication required",
        401,
        {"WWW-Authenticate": 'Basic realm="Lane Change Dashboard"'},
    )


def natural_sort_key(text):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", str(text))]


def _case_metadata_from_row(row):
    configuration = str(row.get("Configuration", "") or "").strip()
    site = str(row.get("Site", row.get("Site ID", "")) or "").strip()
    gap = str(row.get("Gap", row.get("Initial Gap", "")) or "").strip()
    try:
        ds = str(int(float(row.get("DS")))) if row.get("DS") is not None else ""
    except Exception:
        ds = str(row.get("DS", "") or "").strip()
    try:
        dv = str(int(float(row.get("DV")))) if row.get("DV") is not None else ""
    except Exception:
        dv = str(row.get("DV", "") or "").strip()
    return {
        "configuration": configuration,
        "site": site,
        "gap": gap,
        "ds": ds,
        "dv": dv,
    }


def _filter_case_options(case_options, case_index, site_value=None, configuration_value=None, gap_value=None, ds_value=None, dv_value=None):
    filtered = []
    for option in case_options:
        meta = case_index.get(option["value"], {})
        if site_value and meta.get("site") != site_value:
            continue
        if configuration_value and meta.get("configuration") != configuration_value:
            continue
        if gap_value and meta.get("gap") != gap_value:
            continue
        if ds_value and meta.get("ds") != ds_value:
            continue
        if dv_value and meta.get("dv") != dv_value:
            continue
        filtered.append(option)
    return filtered if filtered else case_options


def _display_filter_label(field, value):
    if field == "dv":
        mapping = {
            "0": "0 (equal)",
            "1": "1 (lower)",
            "2": "2 (higher)",
        }
        return mapping.get(str(value), value)
    if field == "ds":
        mapping = {
            "2": "2 (Tail)",
        }
        return mapping.get(str(value), value)
    return value


def _build_filter_options(case_index, field):
    values = sorted(
        {meta.get(field) for meta in case_index.values() if meta.get(field)},
        key=natural_sort_key,
    )
    return [{"label": _display_filter_label(field, value), "value": value} for value in values]


def build_case_registry(experiment_type):
    paths = get_experiment_paths(experiment_type)
    
    # 1) Cache supporting Excel files locally
    local_paths = {}
    for key, val in paths.items():
        if val and key.endswith("_path"):
            try:
                local_paths[key] = ensure_local(val)
            except Exception as e:
                print(f"Failed to fetch {key} via Globus: {e}")
                local_paths[key] = None
        else:
            local_paths[key] = val

    # 2) Cache merged_folder items locally
    local_merged = cache_path(paths["merged_folder"])
    os.makedirs(local_merged, exist_ok=True)
    try:
        remote_items = list_remote_dir(paths["merged_folder"])
        for item in remote_items:
            if item.get("type") == "file":
                ensure_local(f"{paths['merged_folder']}/{item['name']}")
    except Exception as e:
        print(f"Failed to sync remote merged_folder via Globus: {e}")

    try:
        cases, lookup = list_available_cases(
            local_merged,
            local_paths.get("event_file_path"),
            verification_event_file_path=local_paths.get("verification_event_file_path"),
            follower_decel_detection_file_path=local_paths.get("follower_decel_detection_file_path"),
            follower_profile_detection_file_path=local_paths.get("follower_profile_detection_file_path"),
            los_event_file_path=local_paths.get("los_event_file_path"),
            lc_detection_file_path=local_paths.get("lc_detection_file_path"),
            lc_direct_detection_file_path=local_paths.get("lc_direct_detection_file_path"),
        )
    except Exception as e:
        print(f"Failed to build case registry -> {e}")
        return {"case_index": {}, "report_lookup": {}, "case_options": [], "paths": paths}
        
    cases = sorted(cases, key=lambda item: (natural_sort_key(item["case_name"]), natural_sort_key(item["file_name"])))
    for item in cases:
        item.update(_case_metadata_from_row(lookup[tuple(item["key"])]))
    case_index = {item["case_name"]: item for item in cases}
    case_options = [{"label": f"{item['case_name']} | {item['file_name']}", "value": item["case_name"]} for item in cases]
    return {
        "case_index": case_index,
        "report_lookup": lookup,
        "case_options": case_options,
        "paths": paths,
    }


REGISTRY_CACHE = {}
TRIAL_CACHE = {}


def get_registry(experiment_type):
    if experiment_type not in REGISTRY_CACHE:
        REGISTRY_CACHE[experiment_type] = build_case_registry(experiment_type)
    return REGISTRY_CACHE[experiment_type]


def _normalize_lc_detection_methods(lc_detection_methods):
    if not lc_detection_methods:
        return []
    if isinstance(lc_detection_methods, str):
        return [lc_detection_methods]
    methods = [method for method in lc_detection_methods if method]
    return methods or []


def _apply_lc_detection_method(trial, lc_detection_methods):
    methods = _normalize_lc_detection_methods(lc_detection_methods)
    trial.event_times["lc_detection_methods"] = methods
    trial.event_times["lc_start_sec"] = trial.event_times.get("raw_lc_start_sec", trial.event_times.get("lc_start_sec"))
    trial.event_times["lc_end_sec"] = trial.event_times.get("raw_lc_end_sec", trial.event_times.get("lc_end_sec"))
    if "direct_threshold_method" in methods:
        trial.event_times["lc_start_band_min_sec"] = trial.event_times.get("direct_lc_start_sec")
        trial.event_times["lc_start_band_max_sec"] = trial.event_times.get("direct_lc_time_sec")
        trial.event_times["lc_end_band_min_sec"] = trial.event_times.get("direct_lc_end_sec")
        trial.event_times["lc_end_band_max_sec"] = trial.event_times.get("direct_lc_end_time_sec")
        trial.event_times["lc_detection_label"] = LC_DETECTION_METHODS["direct_threshold_method"]
    else:
        trial.event_times["lc_start_band_min_sec"] = trial.event_times.get("slope_lc_start_sec")
        trial.event_times["lc_start_band_max_sec"] = trial.event_times.get("slope_lc_time_sec")
        trial.event_times["lc_end_band_min_sec"] = trial.event_times.get("slope_lc_end_sec")
        trial.event_times["lc_end_band_max_sec"] = trial.event_times.get("slope_lc_end_time_sec")
        trial.event_times["lc_detection_label"] = LC_DETECTION_METHODS["slope_regression_method"]
    return trial


def _apply_follower_decel_method(trial, follower_decel_method):
    methods = []
    if follower_decel_method:
        methods = [follower_decel_method] if isinstance(follower_decel_method, str) else [method for method in follower_decel_method if method]
    trial.event_times["follower_decel_methods"] = methods
    trial.event_times["f1_dec_sec"] = trial.event_times.get("raw_f1_dec_sec", trial.event_times.get("f1_dec_sec"))
    trial.event_times["f2_dec_sec"] = trial.event_times.get("raw_f2_dec_sec", trial.event_times.get("f2_dec_sec"))
    f1_min = trial.event_times.get("follower_slope_f1_dec_min_sec")
    f1_max = trial.event_times.get("follower_slope_f1_dec_max_sec")
    f2_min = trial.event_times.get("follower_slope_f2_dec_min_sec")
    f2_max = trial.event_times.get("follower_slope_f2_dec_max_sec")
    trial.event_times["f1_dec_band_min_sec"] = f1_min
    trial.event_times["f1_dec_band_max_sec"] = f1_max
    trial.event_times["f2_dec_band_min_sec"] = f2_min
    trial.event_times["f2_dec_band_max_sec"] = f2_max
    trial.event_times["follower_decel_label"] = FOLLOWER_DECEL_METHODS["slope_regression_method"]
    return trial


def get_trial(experiment_type, case_key, lc_detection_method=None, follower_decel_method=None, follower_threshold_pairs=None):
    if not case_key:
        return None
    cache_key = (experiment_type, case_key)
    registry = get_registry(experiment_type)
    if cache_key not in TRIAL_CACHE:
        trial = load_trial_by_case(case_key, registry["case_index"], registry["report_lookup"])
        compute_all_metrics(trial, ma_window=DEFAULT_MA_WINDOW)
        trial.event_times["raw_lc_start_sec"] = trial.event_times.get("lc_start_sec")
        trial.event_times["raw_lc_end_sec"] = trial.event_times.get("lc_end_sec")
        trial.event_times["raw_f1_dec_sec"] = trial.event_times.get("f1_dec_sec")
        trial.event_times["raw_f2_dec_sec"] = trial.event_times.get("f2_dec_sec")
        TRIAL_CACHE[cache_key] = trial
    trial_copy = _apply_lc_detection_method(deepcopy(TRIAL_CACHE[cache_key]), lc_detection_method)
    trial_copy.event_times["follower_threshold_pairs"] = [pair for pair in (([follower_threshold_pairs] if isinstance(follower_threshold_pairs, str) else (follower_threshold_pairs or []))) if pair]
    return _apply_follower_decel_method(trial_copy, follower_decel_method)


def get_video_uri(experiment_type, case_key):
    if not case_key:
        return ""
    registry = get_registry(experiment_type)
    meta = registry["case_index"].get(case_key)
    if not meta:
        return ""
    # Assume the video exists remotely and skip local exists check 
    # The caching logic handles the actual fetch when serving it.
    return f"/video/{experiment_type}/{meta['case_name']}"


@server.route("/video/<experiment_type>/<case_name>")
def serve_video(experiment_type, case_name):
    registry = get_registry(experiment_type)
    meta = registry["case_index"].get(case_name)
    if not meta:
        abort(404)
    remote_video_path = f"{registry['paths']['video_folder']}/{meta['case_name']}.mp4"
    try:
        local_video_path = ensure_local(remote_video_path)
        if not os.path.exists(local_video_path):
            abort(404)
        return send_file(local_video_path, mimetype="video/mp4", conditional=True)
    except Exception as e:
        print(f"Failed to serve video via Globus: {e}")
        abort(404)


def compute_default_range(trial):
    return compute_window_range(trial, "auto_to_lc_end_plus_2")


def compute_window_range(trial, preset):
    tmin, tmax = float(trial.timestamps.min()), float(trial.timestamps.max())
    auto_sec = trial.event_times.get("auto_sec")
    lc_start_sec = trial.event_times.get("lc_start_sec")
    lc_end_sec = trial.event_times.get("lc_end_sec")

    if preset == "auto_to_lc_start":
        start = (auto_sec - 2.0) if auto_sec is not None else tmin
        end = lc_start_sec if lc_start_sec is not None else tmax
    elif preset == "auto_to_lc_end_plus_2":
        start = (auto_sec - 2.0) if auto_sec is not None else tmin
        end = (lc_end_sec + 2.0) if lc_end_sec is not None else tmax
    elif preset == "lc_start_to_lc_end":
        start = lc_start_sec if lc_start_sec is not None else ((auto_sec - 2.0) if auto_sec is not None else tmin)
        end = lc_end_sec if lc_end_sec is not None else tmax
    elif preset == "lc_end_to_plus_20":
        start = lc_end_sec if lc_end_sec is not None else tmin
        end = (lc_end_sec + 20.0) if lc_end_sec is not None else tmax
    elif preset == "full_trial":
        start = (auto_sec - 2.0) if auto_sec is not None else tmin
        end = (lc_end_sec + 20.0) if lc_end_sec is not None else tmax
    else:
        return compute_default_range(trial)

    return list(clamp_range(start, end, tmin, tmax))


def empty_fig(msg="No data"):
    fig = go.Figure()
    fig.update_layout(template="plotly_white", title=msg, height=300)
    return fig


@app.callback(
    Output("analysis-tab-wrap", "style"),
    Output("lane-end-tab-wrap", "style"),
    Input("main-tabs", "value"),
)
def toggle_main_tabs(active_tab):
    if active_tab == "lane-end-tab":
        return {"display": "none"}, {"display": "block"}
    return {"display": "block"}, {"display": "none"}


def visible_plots_from_groups(groups, explicit_plots):
    allowed = []
    for group in groups or []:
        allowed.extend(PLOT_GROUPS.get(group, []))
    return [plot for plot in explicit_plots or [] if plot in allowed]


def _finite_bounds(values):
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return None
    return float(np.min(arr)), float(np.max(arr))


def _collect_plot_values(trial, plot_key, longitudinal_pairs=None, safety_pairs=None):
    if trial is None:
        return None
    vehicle_metrics = trial.metrics.get("vehicle", {})
    if plot_key == "longitudinal_position":
        series = [payload.get("oblique_position") for payload in vehicle_metrics.values()]
    elif plot_key == "longitudinal_speed":
        series = [payload.get("speed") for payload in vehicle_metrics.values()]
    elif plot_key == "lateral_position":
        series = [payload.get("lateral") for payload in vehicle_metrics.values()]
    elif plot_key == "lateral_speed":
        series = [payload.get("lat_speed") for payload in vehicle_metrics.values()]
    elif plot_key == "lateral_acceleration":
        series = [payload.get("lat_acc") for payload in vehicle_metrics.values()]
    elif plot_key == "longitudinal_spacing":
        series = [trial.metrics.get("pairwise", {}).get(pair, {}).get("spacing") for pair in (longitudinal_pairs or [])]
    elif plot_key in {"longitudinal_headway", "longitudinal_tau"}:
        value_key = "headway" if plot_key == "longitudinal_headway" else "tau"
        series = [trial.metrics.get("pairwise", {}).get(pair, {}).get(value_key) for pair in (longitudinal_pairs or [])]
    elif plot_key in {"ttc", "drac", "essm"}:
        series = [trial.metrics.get("safety", {}).get(pair, {}).get(plot_key) for pair in (safety_pairs or [])]
    else:
        series = []

    bounds = [_finite_bounds(s) for s in series if s is not None]
    bounds = [b for b in bounds if b is not None]
    if not bounds:
        return None
    mins, maxs = zip(*bounds)
    return float(min(mins)), float(max(maxs))


def _slider_bounds_for_plot(trial, plot_key, longitudinal_pairs=None, safety_pairs=None):
    spec_limits = PLOT_SPECS[plot_key].y_limits
    slider_bounds_overrides = {
        "longitudinal_speed": (0.0, 30.0),
        "longitudinal_acceleration": (-10.0, 10.0),
        "longitudinal_headway": (0.0, 10.0),
        "longitudinal_tau": (0.0, 10.0),
        "longitudinal_spacing": (-30.0, 60.0),
        "essm": (-50.0, 50.0),
    }
    if plot_key in slider_bounds_overrides:
        slider_min, slider_max = slider_bounds_overrides[plot_key]
        default_value = [float(spec_limits[0]), float(spec_limits[1])] if spec_limits is not None else [slider_min, slider_max]
        return slider_min, slider_max, default_value

    data_bounds = _collect_plot_values(trial, plot_key, longitudinal_pairs=longitudinal_pairs, safety_pairs=safety_pairs)
    if spec_limits is not None:
        return float(spec_limits[0]), float(spec_limits[1]), [float(spec_limits[0]), float(spec_limits[1])]
    if data_bounds is None:
        return 0.0, 1.0, [0.0, 1.0]
    ymin, ymax = data_bounds
    if np.isclose(ymin, ymax):
        pad = max(1.0, abs(ymin) * 0.1)
    else:
        pad = max(0.5, (ymax - ymin) * 0.1)
    return ymin - pad, ymax + pad, [ymin, ymax]


def _round_1_decimal(value):
    return round(float(value), 1)


def _slider_marks(slider_min, slider_max):
    ticks = np.linspace(slider_min, slider_max, 5)
    return {_round_1_decimal(tick): f"{_round_1_decimal(tick):.1f}" for tick in ticks}


def _effective_custom_y_limits(mode, custom_y_limits):
    return custom_y_limits if mode == "saved" else None


def _extract_combined_ylimits_for_plot(selected_plot, visible_plots, relayout_data):
    if not relayout_data or selected_plot not in (visible_plots or []):
        return None
    row_index = visible_plots.index(selected_plot) + 1
    axis_name = "yaxis" if row_index == 1 else f"yaxis{row_index}"
    low_key = f"{axis_name}.range[0]"
    high_key = f"{axis_name}.range[1]"
    if low_key in relayout_data and high_key in relayout_data:
        return [float(relayout_data[low_key]), float(relayout_data[high_key])]
    return None


def _extract_individual_ylimits_for_plot(selected_plot, relayout_data_list, graph_ids):
    for relayout_data, graph_id in zip(relayout_data_list or [], graph_ids or []):
        if not graph_id or graph_id.get("index") != selected_plot or not relayout_data:
            continue
        if "yaxis.range[0]" in relayout_data and "yaxis.range[1]" in relayout_data:
            return [float(relayout_data["yaxis.range[0]"]), float(relayout_data["yaxis.range[1]"])]
    return None


def _extract_all_combined_ylimits(visible_plots, relayout_data):
    out = {}
    if not relayout_data:
        return out
    for row_index, plot_key in enumerate(visible_plots or [], start=1):
        axis_name = "yaxis" if row_index == 1 else f"yaxis{row_index}"
        low_key = f"{axis_name}.range[0]"
        high_key = f"{axis_name}.range[1]"
        if low_key in relayout_data and high_key in relayout_data:
            out[plot_key] = [
                _round_1_decimal(relayout_data[low_key]),
                _round_1_decimal(relayout_data[high_key]),
            ]
    return out


def _extract_all_individual_ylimits(relayout_data_list, graph_ids):
    out = {}
    for relayout_data, graph_id in zip(relayout_data_list or [], graph_ids or []):
        if not graph_id or not relayout_data:
            continue
        plot_key = graph_id.get("index")
        if "yaxis.range[0]" in relayout_data and "yaxis.range[1]" in relayout_data:
            out[plot_key] = [
                _round_1_decimal(relayout_data["yaxis.range[0]"]),
                _round_1_decimal(relayout_data["yaxis.range[1]"]),
            ]
    return out


app.layout = build_layout(get_registry(EXPERIMENT_TYPE)["case_options"])


@app.callback(
    Output("case-count-label", "children"),
    Output("site-filter", "options"),
    Output("configuration-filter", "options"),
    Output("gap-filter", "options"),
    Output("ds-filter", "options"),
    Output("dv-filter", "options"),
    Output("case-select", "options"),
    Output("case-select", "value"),
    Input("experiment-select", "value"),
    Input("site-filter", "value"),
    Input("configuration-filter", "value"),
    Input("gap-filter", "value"),
    Input("ds-filter", "value"),
    Input("dv-filter", "value"),
)
def update_cases_for_experiment(experiment_type, site_value, configuration_value, gap_value, ds_value, dv_value):
    registry = get_registry(experiment_type or EXPERIMENT_TYPE)
    case_options = _filter_case_options(
        registry["case_options"],
        registry["case_index"],
        site_value=site_value,
        configuration_value=configuration_value,
        gap_value=gap_value,
        ds_value=ds_value,
        dv_value=dv_value,
    )
    primary_case_value = case_options[0]["value"] if case_options else None
    return (
        f"Found {len(case_options)} valid files.",
        _build_filter_options(registry["case_index"], "site"),
        _build_filter_options(registry["case_index"], "configuration"),
        _build_filter_options(registry["case_index"], "gap"),
        _build_filter_options(registry["case_index"], "ds"),
        _build_filter_options(registry["case_index"], "dv"),
        case_options,
        primary_case_value,
    )


@app.callback(
    Output("compare-site-filter", "options"),
    Output("compare-configuration-filter", "options"),
    Output("compare-gap-filter", "options"),
    Output("compare-ds-filter", "options"),
    Output("compare-dv-filter", "options"),
    Output("compare-case-select", "options"),
    Output("compare-case-select", "value"),
    Input("compare-experiment-select", "value"),
    Input("compare-site-filter", "value"),
    Input("compare-configuration-filter", "value"),
    Input("compare-gap-filter", "value"),
    Input("compare-ds-filter", "value"),
    Input("compare-dv-filter", "value"),
)
def update_compare_cases_for_experiment(compare_experiment_type, site_value, configuration_value, gap_value, ds_value, dv_value):
    registry = get_registry(compare_experiment_type or EXPERIMENT_TYPE)
    case_options = _filter_case_options(
        registry["case_options"],
        registry["case_index"],
        site_value=site_value,
        configuration_value=configuration_value,
        gap_value=gap_value,
        ds_value=ds_value,
        dv_value=dv_value,
    )
    compare_case_value = case_options[0]["value"] if case_options else None
    return (
        _build_filter_options(registry["case_index"], "site"),
        _build_filter_options(registry["case_index"], "configuration"),
        _build_filter_options(registry["case_index"], "gap"),
        _build_filter_options(registry["case_index"], "ds"),
        _build_filter_options(registry["case_index"], "dv"),
        case_options,
        compare_case_value,
    )


@app.callback(
    Output("compare-select-wrap", "style"),
    Input("compare-mode", "value"),
)
def toggle_compare_controls(compare_mode):
    if "enabled" in (compare_mode or []):
        return {"display": "block", "marginBottom": "12px"}
    return {"display": "none", "marginBottom": "12px"}


@app.callback(
    Output("follower-threshold-pairs-wrap", "style"),
    Input("follower-decel-method", "value"),
)
def toggle_follower_threshold_pairs(follower_decel_method):
    methods = []
    if follower_decel_method:
        methods = [follower_decel_method] if isinstance(follower_decel_method, str) else [method for method in follower_decel_method if method]
    if "profile_threshold_method" in methods:
        return {"display": "block", "marginBottom": "12px", "background": "white", "padding": "16px", "borderRadius": "14px", "boxShadow": "0 6px 18px rgba(0,0,0,0.05)"}
    return {"display": "none", "marginBottom": "12px", "background": "white", "padding": "16px", "borderRadius": "14px", "boxShadow": "0 6px 18px rgba(0,0,0,0.05)"}


@app.callback(
    Output("plot-select", "value"),
    Input("group-select", "value"),
    State("plot-select", "value"),
)
def sync_plots_to_groups(groups, current_plots):
    allowed = []
    for group in groups or []:
        allowed.extend(PLOT_GROUPS.get(group, []))
    allowed = list(dict.fromkeys(allowed))
    if not current_plots:
        return allowed
    current_plots = current_plots or []
    retained = [p for p in current_plots if p in allowed]
    auto_added = [p for p in allowed if p not in retained]
    return retained + auto_added


@app.callback(
    Output("ylimit-plot-select", "options"),
    Output("ylimit-plot-select", "value"),
    Input("plot-select", "value"),
)
def update_ylimit_plot_options(plot_select):
    visible_plots = plot_select or []
    options = [{"label": PLOT_SPECS[k].title, "value": k} for k in visible_plots]
    value = visible_plots[0] if visible_plots else None
    return options, value


@app.callback(
    Output("ylimit-slider", "min"),
    Output("ylimit-slider", "max"),
    Output("ylimit-slider", "step"),
    Output("ylimit-slider", "marks"),
    Output("ylimit-slider", "value"),
    Output("ylimit-slider-label", "children"),
    Input("experiment-select", "value"),
    Input("case-select", "value"),
    Input("lc-detection-method", "value"),
    Input("follower-decel-method", "value"),
    Input("follower-threshold-pairs", "value"),
    Input("ylimit-plot-select", "value"),
    Input("ylimit-mode", "value"),
    Input("longitudinal-pairs", "value"),
    Input("safety-pairs", "value"),
    Input("custom-y-limits-store", "data"),
)
def update_ylimit_slider(experiment_type, case_key, lc_detection_method, follower_decel_method, follower_threshold_pairs, selected_plot, ylimit_mode, longitudinal_pairs, safety_pairs, custom_y_limits):
    if not selected_plot:
        return 0.0, 1.0, 0.1, {0.0: "0.0", 1.0: "1.0"}, [0.0, 1.0], "Select a visible plot to adjust its y-limits."
    trial = get_trial(experiment_type or EXPERIMENT_TYPE, case_key, lc_detection_method=lc_detection_method, follower_decel_method=follower_decel_method, follower_threshold_pairs=follower_threshold_pairs) if case_key else None
    slider_min, slider_max, default_value = _slider_bounds_for_plot(
        trial,
        selected_plot,
        longitudinal_pairs=longitudinal_pairs,
        safety_pairs=safety_pairs,
    )
    saved_value = (custom_y_limits or {}).get(selected_plot)
    current_value = saved_value if ylimit_mode == "saved" and saved_value else default_value
    slider_min = _round_1_decimal(slider_min)
    slider_max = _round_1_decimal(slider_max)
    current_value = [_round_1_decimal(current_value[0]), _round_1_decimal(current_value[1])] if current_value else [_round_1_decimal(default_value[0]), _round_1_decimal(default_value[1])]
    step = 0.1
    marks = _slider_marks(slider_min, slider_max)
    source_text = "saved" if ylimit_mode == "saved" and saved_value else "default"
    label = f"{PLOT_SPECS[selected_plot].title}: {current_value[0]:.1f} to {current_value[1]:.1f} ({source_text})"
    return slider_min, slider_max, step, marks, current_value, label


@app.callback(
    Output("custom-y-limits-store", "data"),
    Input("save-slider-ylimit", "n_clicks"),
    Input("save-zoom-ylimit", "n_clicks"),
    Input("reset-current-ylimit", "n_clicks"),
    Input("reset-all-ylimits", "n_clicks"),
    State("experiment-select", "value"),
    State("case-select", "value"),
    State("lc-detection-method", "value"),
    State("plot-select", "value"),
    State("group-select", "value"),
    State("ylimit-plot-select", "value"),
    State("ylimit-slider", "value"),
    State("combined-graph", "relayoutData", allow_optional=True),
    State({"type": "plot-graph", "index": ALL}, "relayoutData", allow_optional=True),
    State({"type": "plot-graph", "index": ALL}, "id", allow_optional=True),
    State("custom-y-limits-store", "data"),
    prevent_initial_call=True,
)
def update_custom_y_limits(save_slider_clicks, save_zoom_clicks, reset_current_clicks, reset_all_clicks, experiment_type, case_key, lc_detection_method, follower_threshold_pairs, plot_select, groups, selected_plot, slider_value, combined_relayout, individual_relayout_data, individual_graph_ids, current_store):
    store = dict(current_store or {})
    visible_plots = visible_plots_from_groups(groups, plot_select)

    trigger = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else None
    if trigger == "reset-all-ylimits":
        return {}

    if not selected_plot:
        return store

    if trigger == "reset-current-ylimit":
        store.pop(selected_plot, None)
        return store

    if trigger == "save-slider-ylimit" and slider_value and len(slider_value) == 2:
        store[selected_plot] = [_round_1_decimal(slider_value[0]), _round_1_decimal(slider_value[1])]
        return store

    if trigger == "save-zoom-ylimit":
        combined_limits = _extract_all_combined_ylimits(visible_plots, combined_relayout)
        individual_limits = _extract_all_individual_ylimits(individual_relayout_data, individual_graph_ids)
        for plot_key, limits in {**individual_limits, **combined_limits}.items():
            store[plot_key] = limits
    return store


@app.callback(
    Output("group-select", "value"),
    Output("plot-select", "value", allow_duplicate=True),
    Output("longitudinal-pairs", "value"),
    Output("safety-pairs", "value"),
    Output("event-lines", "value"),
    Input("select-all-filters", "n_clicks"),
    Input("deselect-all-filters", "n_clicks"),
    prevent_initial_call=True,
)
def update_all_filters(_select_clicks, _deselect_clicks):
    trigger = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else None
    if trigger == "select-all-filters":
        return (
            list(PLOT_GROUPS.keys()),
            list(PLOT_SPECS.keys()),
            ["AB", "BC", "TL_X", "X_TF"],
            ["X_TARGET_LEADER", "TARGET_FOLLOWER_X", "BA", "CB", "X_LANE_DROP_END", "X_LEFT_TURN_LANE_END"],
            ["auto_sec", "lc_start_sec", "lc_end_sec", "lc_cross_sec", "f1_dec_sec", "f2_dec_sec", "los_sec"],
        )
    return [], [], [], [], []


@app.callback(
    Output("selected-file-label", "children"),
    Output("open-video-link", "href"),
    Output("open-video-link", "style"),
    Output("open-compare-video-link", "href"),
    Output("open-compare-video-link", "style"),
    Input("compare-mode", "value"),
    Input("experiment-select", "value"),
    Input("case-select", "value"),
    Input("compare-experiment-select", "value"),
    Input("compare-case-select", "value"),
)
def update_selected_file_label(compare_mode, experiment_type, case_key, compare_experiment_type, compare_case_key):
    hidden_style = {"display": "none", "marginBottom": "12px", "fontWeight": "600"}
    hidden_compare_style = {"display": "none", "marginBottom": "12px", "marginLeft": "12px", "fontWeight": "600"}
    if not case_key:
        return "No case selected", "", hidden_style, "", hidden_compare_style
    experiment_type = experiment_type or EXPERIMENT_TYPE
    meta = get_registry(experiment_type)["case_index"].get(case_key)
    if not meta:
        return "Selected case not found", "", hidden_style, "", hidden_compare_style
    video_uri = get_video_uri(experiment_type, case_key)
    video_style = {"display": "inline-block", "marginBottom": "12px", "fontWeight": "600"} if video_uri else hidden_style

    compare_href = ""
    compare_style = hidden_compare_style
    if "enabled" in (compare_mode or []) and compare_case_key:
        compare_experiment_type = compare_experiment_type or EXPERIMENT_TYPE
        compare_href = get_video_uri(compare_experiment_type, compare_case_key)
        if compare_href:
            compare_style = {"display": "inline-block", "marginBottom": "12px", "marginLeft": "12px", "fontWeight": "600"}

    return f"Selected file: {meta['file_name']}", video_uri, video_style, compare_href, compare_style


def build_summary_component(trial, safety_pairs):
    rows = build_summary_rows(trial, safety_pairs)
    auto_sec = trial.event_times.get("auto_sec")
    lc_start_sec = trial.event_times.get("lc_start_sec")
    lc_end_sec = trial.event_times.get("lc_end_sec")

    def fmt_time(value):
        return f"{value:.2f} s" if value is not None else "N/A"

    window_note = (
        f"Summary window: LC Start ({fmt_time(lc_start_sec)}) to LC End + 15 s "
        f"({fmt_time(lc_end_sec + 15.0 if lc_end_sec is not None else None)})."
    )
    endpoint_note = (
        f"For X_LANE_DROP_END and X_LEFT_TURN_LANE_END, the summary window is "
        f"Auto Mode Time ({fmt_time(auto_sec)}) to LC Cross ({fmt_time(trial.event_times.get('lc_cross_sec'))})."
    )
    phase_note = (
        f"Note: Before LC Start (< {fmt_time(lc_start_sec)}), "
        f"During LC ({fmt_time(lc_start_sec)} to {fmt_time(lc_end_sec)}), "
        f"After LC (> {fmt_time(lc_end_sec)})."
    )

    return html.Div([
        html.Div(window_note, style={"marginBottom": "6px", "fontWeight": "600"}),
        html.Div(endpoint_note, style={"marginBottom": "6px", "fontWeight": "600"}),
        html.Div(phase_note, style={"marginBottom": "10px", "color": "#444"}),
        dash_table.DataTable(
            data=rows,
            columns=[{"name": c, "id": c} for c in [
                "Pair",
                "Min TTC",
                "Time @ Min TTC (s)",
                "Max DRAC",
                "Time @ Max DRAC (s)",
                "Min ESSM",
                "Time @ Min ESSM (s)",
            ]],
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "center", "padding": "8px"},
            style_header={"fontWeight": "bold"},
        ),
    ])


@app.callback(
    Output("x-range-store", "data"),
    Output("x-min", "value"),
    Output("x-max", "value"),
    Input("experiment-select", "value"),
    Input("case-select", "value"),
    Input("lc-detection-method", "value"),
    Input("window-preset", "value"),
    Input("x-min", "value"),
    Input("x-max", "value"),
    State("x-range-store", "data"),
)
def manage_x_range(experiment_type, case_key, lc_detection_method, window_preset, x_min, x_max, current_store):
    trial = get_trial(experiment_type or EXPERIMENT_TYPE, case_key, lc_detection_method=lc_detection_method)
    if trial is None:
        return None, None, None
    tmin, tmax = float(trial.timestamps.min()), float(trial.timestamps.max())
    default_range = compute_window_range(trial, window_preset)
    trigger = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else None
    if trigger in {"experiment-select", "case-select", "window-preset"}:
        return default_range, default_range[0], default_range[1]
    if x_min is not None and x_max is not None and x_min < x_max:
        xr = list(clamp_range(x_min, x_max, tmin, tmax))
        return xr, xr[0], xr[1]
    if current_store:
        return current_store, current_store[0], current_store[1]
    return default_range, default_range[0], default_range[1]


@app.callback(
    Output("summary-table-wrap", "children"),
    Input("compare-mode", "value"),
    Input("experiment-select", "value"),
    Input("case-select", "value"),
    Input("lc-detection-method", "value"),
    Input("safety-pairs", "value"),
)
def update_summary(compare_mode, experiment_type, case_key, lc_detection_method, safety_pairs):
    if "enabled" in (compare_mode or []):
        return html.Div()
    trial = get_trial(experiment_type or EXPERIMENT_TYPE, case_key, lc_detection_method=lc_detection_method)
    if trial is None:
        return html.Div("No case loaded")
    return build_summary_component(trial, safety_pairs)


def _add_shifted_event_lines(fig, trial, visible_event_keys, prefix=None, y_level=1.0, row=None, color_override=None):
    lc_cross = trial.event_times.get("lc_cross_sec")
    if lc_cross is None or not np.isfinite(lc_cross):
        return
    xref = "x" if row in (None, 1) else f"x{row}"
    yref = "paper" if row is None else ("y domain" if row == 1 else f"y{row} domain")
    for key in visible_event_keys or []:
        style = EVENT_LINE_STYLES.get(key)
        event_time = trial.event_times.get(key)
        if style is None or event_time is None or not np.isfinite(event_time):
            continue
        shifted_x = float(event_time) - float(lc_cross)
        line_color = color_override or style["color"]
        vline_kwargs = dict(x=shifted_x, line_color=line_color, line_dash=style["dash"], line_width=2)
        if row is not None:
            vline_kwargs.update(row=row, col=1)
        fig.add_vline(**vline_kwargs)
        label = style["label"] if not prefix else f"{prefix} {style['label']}"
        fig.add_annotation(
            x=shifted_x,
            y=y_level,
            xref=xref,
            yref=yref,
            text=f"{label}: {shifted_x:+.2f} s",
            showarrow=False,
            yshift=-10,
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor=line_color,
            borderwidth=1,
            font=dict(size=11, color=line_color),
        )

def _shifted_threshold_annotations(trial, lc_cross, threshold_specs):
    annotations = []
    for label, column in threshold_specs:
        value = trial.raw_report_row.get(column)
        try:
            value = float(value)
        except Exception:
            continue
        if np.isfinite(value):
            annotations.append((label, float(value) - float(lc_cross)))
    return annotations


def _add_shifted_threshold_band(fig, trial, start_key, end_key, row, label_text, threshold_specs, text_color, fillcolor, fill_opacity=0.10):
    lc_cross = trial.event_times.get("lc_cross_sec")
    x0 = trial.event_times.get(start_key)
    x1 = trial.event_times.get(end_key)
    if lc_cross is None or x0 is None or x1 is None:
        return
    if not (np.isfinite(lc_cross) and np.isfinite(x0) and np.isfinite(x1)):
        return
    shifted_x0 = float(x0) - float(lc_cross)
    shifted_x1 = float(x1) - float(lc_cross)
    if shifted_x1 < shifted_x0:
        shifted_x0, shifted_x1 = shifted_x1, shifted_x0
    if np.isclose(shifted_x0, shifted_x1):
        return

    fig.add_vrect(x0=shifted_x0, x1=shifted_x1, fillcolor=fillcolor, opacity=fill_opacity, line_width=0, row=row, col=1)
    xref = "x" if row == 1 else f"x{row}"
    yref = "y domain" if row == 1 else f"y{row} domain"
    label_x = shifted_x1 + max(0.04, 0.25 * (shifted_x1 - shifted_x0))
    fig.add_annotation(
        x=label_x,
        y=0.88,
        xref=xref,
        yref=yref,
        text=label_text,
        textangle=-90,
        showarrow=False,
        font=dict(size=10, color=text_color),
        bgcolor="rgba(255,255,255,0.0)",
    )

    y_slots = [0.76, 0.54, 0.32]
    for idx, (threshold_label, shifted_time) in enumerate(_shifted_threshold_annotations(trial, lc_cross, threshold_specs)):
        if shifted_time < shifted_x0 or shifted_time > shifted_x1:
            continue
        fig.add_annotation(
            x=shifted_time,
            y=y_slots[min(idx, len(y_slots) - 1)],
            xref=xref,
            yref=yref,
            text=threshold_label,
            textangle=-90,
            showarrow=False,
            font=dict(size=11, color=text_color),
            opacity=0.85,
            bgcolor="rgba(255,255,255,0.0)",
        )


def _add_shifted_lc_detection_bands(fig, trial, lc_detection_methods, lc_detection_events, row, color):
    methods = _normalize_lc_detection_methods(lc_detection_methods)
    events = lc_detection_events or ["lc_start_sec", "lc_end_sec"]
    text_color = color
    fill_color = color
    if "slope_regression_method" in methods:
        if "lc_start_sec" in events:
            _add_shifted_threshold_band(
                fig, trial, "slope_lc_start_sec", "slope_lc_time_sec", row,
                "SRLC",
                [("0.10 m/s", "slope__LC Start @0.10 time"), ("0.15 m/s", "slope__LC Start @0.15 time"), ("0.25 m/s", "slope__LC Start @0.25 time")],
                text_color, fill_color,
            )
        if "lc_end_sec" in events:
            _add_shifted_threshold_band(
                fig, trial, "slope_lc_end_sec", "slope_lc_end_time_sec", row,
                "SRLC",
                [("0.10 m/s", "slope__LC End @0.10 time"), ("0.15 m/s", "slope__LC End @0.15 time"), ("0.25 m/s", "slope__LC End @0.25 time")],
                text_color, fill_color,
            )
    if "direct_threshold_method" in methods:
        if "lc_start_sec" in events:
            _add_shifted_threshold_band(
                fig, trial, "direct_lc_start_sec", "direct_lc_time_sec", row,
                "DTLC",
                [("0.10 m/s", "direct__LC Start Time @ 0.1"), ("0.15 m/s", "direct__LC Start Time @ 0.15"), ("0.25 m/s", "direct__LC Start Time @ 0.25")],
                text_color, fill_color,
            )
        if "lc_end_sec" in events:
            _add_shifted_threshold_band(
                fig, trial, "direct_lc_end_sec", "direct_lc_end_time_sec", row,
                "DTLC",
                [("0.10 m/s", "direct__LC End Time @ 0.1"), ("0.15 m/s", "direct__LC End Time @ 0.15"), ("0.25 m/s", "direct__LC End Time @ 0.25")],
                text_color, fill_color,
            )


def _append_shifted_lateral_metric_trace(fig, trial, metric_key, label, color):
    x_vehicle = trial.metrics.get("vehicle", {}).get("LC")
    lc_cross = trial.event_times.get("lc_cross_sec")
    if not x_vehicle or lc_cross is None or not np.isfinite(lc_cross):
        return False

    timestamps = np.asarray(trial.timestamps, dtype=float)
    metric_values = np.asarray(x_vehicle[metric_key], dtype=float)
    if len(timestamps) == 0 or len(metric_values) == 0:
        return False

    shifted_time = timestamps - float(lc_cross)
    fig.add_trace(go.Scatter(
        x=shifted_time,
        y=metric_values,
        mode="lines",
        name=label,
        line=dict(width=2, color=color),
    ))
    return True


def _append_shifted_lateral_trace(fig, trial, label, color):
    x_vehicle = trial.metrics.get("vehicle", {}).get("LC")
    lc_cross = trial.event_times.get("lc_cross_sec")
    if not x_vehicle or lc_cross is None or not np.isfinite(lc_cross):
        return False

    timestamps = np.asarray(trial.timestamps, dtype=float)
    lateral = np.asarray(x_vehicle["lateral"], dtype=float)
    if len(timestamps) == 0 or len(lateral) == 0:
        return False

    lateral_at_cross = float(np.interp(lc_cross, timestamps, lateral))
    shifted_time = timestamps - float(lc_cross)
    shifted_lateral = lateral - lateral_at_cross
    fig.add_trace(go.Scatter(
        x=shifted_time,
        y=shifted_lateral,
        mode="lines",
        name=label,
        line=dict(width=2, color=color),
    ))
    return True


@app.callback(
    Output("shifted-lateral-analysis-graph", "figure"),
    Input("compare-mode", "value"),
    Input("experiment-select", "value"),
    Input("case-select", "value"),
    Input("compare-experiment-select", "value"),
    Input("compare-case-select", "value"),
    Input("lc-detection-method", "value"),
    Input("lc-detection-events", "value"),
    Input("event-lines", "value"),
)
def render_shifted_lateral_analysis(compare_mode, experiment_type, case_key, compare_experiment_type, compare_case_key, lc_detection_method, lc_detection_events, event_lines):
    if not case_key:
        return empty_fig("No case selected")

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.12,
        subplot_titles=("Shifted Lateral Position", "Shifted Lateral Speed"),
    )
    added_any = False

    def add_trial(trial, label, color, prefix, y_levels):
        nonlocal added_any
        x_vehicle = trial.metrics.get("vehicle", {}).get("LC")
        lc_cross = trial.event_times.get("lc_cross_sec")
        if not x_vehicle or lc_cross is None or not np.isfinite(lc_cross):
            return
        timestamps = np.asarray(trial.timestamps, dtype=float)
        lateral = np.asarray(x_vehicle["lateral"], dtype=float)
        lat_speed = np.asarray(x_vehicle["lat_speed"], dtype=float)
        if len(timestamps) == 0 or len(lateral) == 0 or len(lat_speed) == 0:
            return
        shifted_time = timestamps - float(lc_cross)
        lateral_at_cross = float(np.interp(lc_cross, timestamps, lateral))
        shifted_lateral = lateral - lateral_at_cross
        fig.add_trace(
            go.Scatter(x=shifted_time, y=shifted_lateral, mode="lines", name=label, line=dict(width=2, color=color)),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=shifted_time, y=lat_speed, mode="lines", name=label, line=dict(width=2, color=color), showlegend=False),
            row=2,
            col=1,
        )
        _add_shifted_event_lines(fig, trial, event_lines, prefix=prefix, y_level=y_levels[0], row=1, color_override=color)
        _add_shifted_event_lines(fig, trial, event_lines, prefix=prefix, y_level=y_levels[1], row=2, color_override=color)
        _add_shifted_lc_detection_bands(fig, trial, lc_detection_method, lc_detection_events, row=1, color=color)
        _add_shifted_lc_detection_bands(fig, trial, lc_detection_method, lc_detection_events, row=2, color=color)
        added_any = True

    primary_experiment = experiment_type or EXPERIMENT_TYPE
    primary_trial = get_trial(primary_experiment, case_key, lc_detection_method=lc_detection_method)
    if primary_trial is not None:
        add_trial(primary_trial, f"Primary: {primary_trial.case_name}", "#2e8b57", "P", (1.0, 1.0))

    if "enabled" in (compare_mode or []) and compare_case_key:
        compare_experiment = compare_experiment_type or EXPERIMENT_TYPE
        compare_trial = get_trial(compare_experiment, compare_case_key, lc_detection_method=lc_detection_method)
        if compare_trial is not None:
            add_trial(compare_trial, f"Compare: {compare_trial.case_name}", "#bc272d", "C", (0.93, 0.93))

    if not added_any:
        return empty_fig("LC Cross data unavailable for shifted lateral analysis")

    fig.update_layout(
        template="plotly_white",
        title=dict(text="Shifted Lateral Analysis at LC Cross", x=0.01, xanchor="left", y=0.99, yanchor="top", font=dict(size=18)),
        height=860,
        hovermode="x unified",
        font=dict(size=14),
        legend=dict(orientation="v", yanchor="top", y=0.99, xanchor="left", x=1.02, font=dict(size=11), bgcolor="rgba(255,255,255,0.8)", bordercolor="rgba(0,0,0,0.15)", borderwidth=1),
        margin=dict(l=70, r=180, t=90, b=50),
    )
    fig.update_xaxes(title_text="Shifted Time from LC Cross (s)", range=[-10, 10], showticklabels=True, title_font=dict(size=16), tickfont=dict(size=13), row=1, col=1)
    fig.update_xaxes(title_text="Shifted Time from LC Cross (s)", range=[-10, 10], showticklabels=True, title_font=dict(size=16), tickfont=dict(size=13), row=2, col=1)
    fig.update_yaxes(title_text="Shifted Lateral Position (m)", range=[-3, 3], title_font=dict(size=16), tickfont=dict(size=13), row=1, col=1)
    fig.update_yaxes(title_text="Shifted Lateral Speed (m/s)", range=[-2, 0.5], title_font=dict(size=16), tickfont=dict(size=13), row=2, col=1)
    fig.add_hline(y=0.0, line_color="rgba(0,0,0,0.25)", line_dash="dot", row=1, col=1)
    fig.add_vline(x=0.0, line_color="rgba(0,0,0,0.25)", line_dash="dot", row=1, col=1)
    fig.add_hline(y=0.0, line_color="rgba(0,0,0,0.25)", line_dash="dot", row=2, col=1)
    fig.add_vline(x=0.0, line_color="rgba(0,0,0,0.25)", line_dash="dot", row=2, col=1)
    return fig


@app.callback(
    Output("combined-wrap", "children"),
    Input("compare-mode", "value"),
    Input("experiment-select", "value"),
    Input("case-select", "value"),
    Input("lc-detection-method", "value"),
    Input("lc-detection-events", "value"),
    Input("follower-decel-method", "value"),
    Input("follower-threshold-pairs", "value"),
    Input("plot-select", "value"),
    Input("group-select", "value"),
    Input("longitudinal-pairs", "value"),
    Input("safety-pairs", "value"),
    Input("event-lines", "value"),
    Input("x-range-store", "data"),
    Input("ylimit-mode", "value"),
    Input("custom-y-limits-store", "data"),
    Input("view-mode", "value"),
)
def render_combined(compare_mode, experiment_type, case_key, lc_detection_method, lc_detection_events, follower_decel_method, follower_threshold_pairs, plot_select, groups, longitudinal_pairs, safety_pairs, event_lines, x_range, ylimit_mode, custom_y_limits, view_mode):
    visible_plots = visible_plots_from_groups(groups, plot_select)
    if "enabled" in (compare_mode or []) or view_mode not in {"combined", "both"} or not case_key or not visible_plots:
        return html.Div()
    trial = get_trial(experiment_type or EXPERIMENT_TYPE, case_key, lc_detection_method=lc_detection_method, follower_decel_method=follower_decel_method, follower_threshold_pairs=follower_threshold_pairs)
    if trial is None:
        return html.Div("No case loaded")
    fig = build_combined_figure(
        trial,
        visible_plots,
        enabled_longitudinal_pairs=longitudinal_pairs,
        enabled_safety_pairs=safety_pairs,
        x_range=x_range,
        visible_event_keys=event_lines,
        custom_y_limits=_effective_custom_y_limits(ylimit_mode, custom_y_limits),
        lc_detection_methods=lc_detection_method,
        lc_detection_events=lc_detection_events,
        follower_decel_methods=follower_decel_method,
        follower_threshold_pairs=follower_threshold_pairs,
    )
    return html.Div([
        html.H3("Combined View"),
        html.Div(f"{trial.case_name} — Combined View", style={"fontWeight": "600", "marginBottom": "8px", "color": "#1f3b6d"}),
        dcc.Graph(id="combined-graph", figure=fig, config={"displaylogo": False, "scrollZoom": True}),
    ], style={"border": "1px solid #ddd", "borderRadius": "10px", "padding": "10px", "background": "white", "marginBottom": "18px"})


@app.callback(
    Output("independent-plots-wrap", "children"),
    Input("compare-mode", "value"),
    Input("plot-select", "value"),
    Input("group-select", "value"),
    Input("view-mode", "value"),
)
def render_plot_cards(compare_mode, plot_select, groups, view_mode):
    if "enabled" in (compare_mode or []) or view_mode not in {"independent", "both"}:
        return html.Div()
    visible_plots = visible_plots_from_groups(groups, plot_select)
    if not visible_plots:
        return html.Div("No plots selected")
    return [plot_card(k) for k in visible_plots]


@app.callback(
    Output({"type": "plot-graph", "index": ALL}, "figure"),
    Input("compare-mode", "value"),
    Input("experiment-select", "value"),
    Input("case-select", "value"),
    Input("lc-detection-method", "value"),
    Input("lc-detection-events", "value"),
    Input("follower-decel-method", "value"),
    Input("follower-threshold-pairs", "value"),
    Input("plot-select", "value"),
    Input("group-select", "value"),
    Input("longitudinal-pairs", "value"),
    Input("safety-pairs", "value"),
    Input("event-lines", "value"),
    Input("x-range-store", "data"),
    Input("ylimit-mode", "value"),
    Input("custom-y-limits-store", "data"),
    Input("sync-x", "value"),
    Input({"type": "reset-zoom", "index": ALL}, "n_clicks"),
    State({"type": "plot-graph", "index": ALL}, "id"),
)
def update_individual_figures(compare_mode, experiment_type, case_key, lc_detection_method, lc_detection_events, follower_decel_method, follower_threshold_pairs, plot_select, groups, longitudinal_pairs, safety_pairs, event_lines, x_range, ylimit_mode, custom_y_limits, sync_x, _reset_clicks, ids):
    if not ids:
        return []
    if "enabled" in (compare_mode or []):
        return [empty_fig("Comparison mode enabled") for _ in ids]
    trial = get_trial(experiment_type or EXPERIMENT_TYPE, case_key, lc_detection_method=lc_detection_method, follower_decel_method=follower_decel_method, follower_threshold_pairs=follower_threshold_pairs)
    visible_plots = set(visible_plots_from_groups(groups, plot_select))
    if trial is None:
        return [empty_fig("No case selected") for _ in ids]
    global_range = x_range if "sync" in (sync_x or []) else None
    figs = []
    for item in ids:
        plot_key = item["index"]
        if plot_key not in visible_plots:
            figs.append(empty_fig("Hidden"))
            continue
        figs.append(build_single_plot_figure(
            trial,
            plot_key,
            enabled_longitudinal_pairs=longitudinal_pairs,
            enabled_safety_pairs=safety_pairs,
            x_range=global_range,
            visible_event_keys=event_lines,
            custom_y_limits=_effective_custom_y_limits(ylimit_mode, custom_y_limits),
            lc_detection_methods=lc_detection_method,
            lc_detection_events=lc_detection_events,
            follower_decel_methods=follower_decel_method,
            follower_threshold_pairs=follower_threshold_pairs,
        ))
    return figs


@app.callback(
    Output("popup-modal", "style"),
    Output("popup-plot-key", "data"),
    Input({"type": "open-popup", "index": ALL}, "n_clicks"),
    Input("close-popup", "n_clicks"),
    State({"type": "open-popup", "index": ALL}, "id"),
)
def toggle_popup(open_clicks, close_clicks, ids):
    trigger = callback_context.triggered[0]["prop_id"] if callback_context.triggered else ""
    if "close-popup" in trigger:
        return {"display": "none"}, None
    for clicks, item in zip(open_clicks or [], ids or []):
        if clicks and trigger.startswith(str(item).replace("'", '"')):
            return {
                "display": "flex", "position": "fixed", "inset": "0", "background": "rgba(0,0,0,0.45)",
                "zIndex": 9999, "justifyContent": "center", "alignItems": "center"
            }, item["index"]
    return {"display": "none"}, None


@app.callback(
    Output("popup-title", "children"),
    Output("popup-graph", "figure"),
    Input("experiment-select", "value"),
    Input("popup-plot-key", "data"),
    Input("case-select", "value"),
    Input("lc-detection-method", "value"),
    Input("lc-detection-events", "value"),
    Input("follower-decel-method", "value"),
    Input("follower-threshold-pairs", "value"),
    Input("longitudinal-pairs", "value"),
    Input("safety-pairs", "value"),
    Input("event-lines", "value"),
    Input("x-range-store", "data"),
    Input("ylimit-mode", "value"),
    Input("custom-y-limits-store", "data"),
)
def update_popup(experiment_type, plot_key, case_key, lc_detection_method, lc_detection_events, follower_decel_method, follower_threshold_pairs, longitudinal_pairs, safety_pairs, event_lines, x_range, ylimit_mode, custom_y_limits):
    if not plot_key or not case_key:
        return "Expanded Plot", empty_fig()
    trial = get_trial(experiment_type or EXPERIMENT_TYPE, case_key, lc_detection_method=lc_detection_method, follower_decel_method=follower_decel_method, follower_threshold_pairs=follower_threshold_pairs)
    if trial is None:
        return "Expanded Plot", empty_fig("No case selected")
    fig = build_single_plot_figure(
        trial,
        plot_key,
        enabled_longitudinal_pairs=longitudinal_pairs,
        enabled_safety_pairs=safety_pairs,
        x_range=x_range,
        visible_event_keys=event_lines,
        height=700,
        custom_y_limits=_effective_custom_y_limits(ylimit_mode, custom_y_limits),
        lc_detection_methods=lc_detection_method,
        lc_detection_events=lc_detection_events,
        follower_decel_methods=follower_decel_method,
        follower_threshold_pairs=follower_threshold_pairs,
    )
    return PLOT_SPECS[plot_key].title, fig


def build_compare_case_column(title, trial, visible_plots, longitudinal_pairs, safety_pairs, event_lines, x_range, view_mode, custom_y_limits=None, lc_detection_methods=None, lc_detection_events=None, follower_decel_methods=None, follower_threshold_pairs=None):
    sections = [html.H3(title, style={"marginBottom": "10px"})]
    sections.append(build_summary_component(trial, safety_pairs))

    if view_mode in {"combined", "both"} and visible_plots:
        combined_fig = build_combined_figure(
            trial,
            visible_plots,
            enabled_longitudinal_pairs=longitudinal_pairs,
            enabled_safety_pairs=safety_pairs,
            x_range=x_range,
            visible_event_keys=event_lines,
            custom_y_limits=custom_y_limits,
            lc_detection_methods=lc_detection_methods,
            lc_detection_events=lc_detection_events,
            follower_decel_methods=follower_decel_methods,
            follower_threshold_pairs=follower_threshold_pairs,
        )
        sections.append(html.Div([
            html.H4("Combined View"),
            dcc.Graph(figure=combined_fig, config={"displaylogo": False, "scrollZoom": True}),
        ], style={"border": "1px solid #ddd", "borderRadius": "10px", "padding": "10px", "background": "white", "marginBottom": "18px"}))

    if view_mode in {"independent", "both"}:
        for plot_key in visible_plots:
            fig = build_single_plot_figure(
                trial,
                plot_key,
                enabled_longitudinal_pairs=longitudinal_pairs,
                enabled_safety_pairs=safety_pairs,
                x_range=x_range,
                visible_event_keys=event_lines,
                custom_y_limits=custom_y_limits,
                lc_detection_methods=lc_detection_methods,
                lc_detection_events=lc_detection_events,
                follower_decel_methods=follower_decel_methods,
                follower_threshold_pairs=follower_threshold_pairs,
            )
            sections.append(html.Div([
                html.H4(PLOT_SPECS[plot_key].title, style={"margin": "0 0 10px 0"}),
                dcc.Graph(figure=fig, config={"displaylogo": False, "scrollZoom": True}),
            ], style={"border": "1px solid #ddd", "borderRadius": "10px", "padding": "10px", "marginBottom": "14px", "background": "white"}))

    return html.Div(sections, style={"flex": 1, "minWidth": "0"})


@app.callback(
    Output("compare-wrap", "children"),
    Input("compare-mode", "value"),
    Input("experiment-select", "value"),
    Input("compare-experiment-select", "value"),
    Input("case-select", "value"),
    Input("compare-case-select", "value"),
    Input("lc-detection-method", "value"),
    Input("lc-detection-events", "value"),
    Input("follower-decel-method", "value"),
    Input("follower-threshold-pairs", "value"),
    Input("plot-select", "value"),
    Input("group-select", "value"),
    Input("longitudinal-pairs", "value"),
    Input("safety-pairs", "value"),
    Input("event-lines", "value"),
    Input("x-range-store", "data"),
    Input("ylimit-mode", "value"),
    Input("custom-y-limits-store", "data"),
    Input("view-mode", "value"),
)
def render_compare_view(compare_mode, experiment_type, compare_experiment_type, case_key, compare_case_key, lc_detection_method, lc_detection_events, follower_decel_method, follower_threshold_pairs, plot_select, groups, longitudinal_pairs, safety_pairs, event_lines, x_range, ylimit_mode, custom_y_limits, view_mode):
    if "enabled" not in (compare_mode or []):
        return html.Div()
    visible_plots = visible_plots_from_groups(groups, plot_select)
    experiment_type = experiment_type or EXPERIMENT_TYPE
    compare_experiment_type = compare_experiment_type or EXPERIMENT_TYPE
    if not case_key or not compare_case_key:
        return html.Div("Select two cases to compare.", style={"marginTop": "10px"})

    left_trial = get_trial(experiment_type, case_key, lc_detection_method=lc_detection_method, follower_decel_method=follower_decel_method, follower_threshold_pairs=follower_threshold_pairs)
    right_trial = get_trial(compare_experiment_type, compare_case_key, lc_detection_method=lc_detection_method, follower_decel_method=follower_decel_method, follower_threshold_pairs=follower_threshold_pairs)
    if left_trial is None or right_trial is None:
        return html.Div("Unable to load one or both selected cases.", style={"marginTop": "10px"})

    left_title = f"Primary case ({experiment_type}): {left_trial.case_name}"
    right_title = f"Compare case ({compare_experiment_type}): {right_trial.case_name}"
    effective_y_limits = _effective_custom_y_limits(ylimit_mode, custom_y_limits)
    return html.Div([
        build_compare_case_column(left_title, left_trial, visible_plots, longitudinal_pairs, safety_pairs, event_lines, x_range, view_mode, custom_y_limits=effective_y_limits, lc_detection_methods=lc_detection_method, lc_detection_events=lc_detection_events, follower_decel_methods=follower_decel_method, follower_threshold_pairs=follower_threshold_pairs),
        build_compare_case_column(right_title, right_trial, visible_plots, longitudinal_pairs, safety_pairs, event_lines, x_range, view_mode, custom_y_limits=effective_y_limits, lc_detection_methods=lc_detection_method, lc_detection_events=lc_detection_events, follower_decel_methods=follower_decel_method, follower_threshold_pairs=follower_threshold_pairs),
    ], style={"display": "flex", "gap": "18px", "alignItems": "flex-start", "marginTop": "10px"})


@app.callback(
    Output("export-status", "children"),
    Input("export-btn", "n_clicks"),
    State("experiment-select", "value"),
    State("case-select", "value"),
    State("lc-detection-method", "value"),
    State("lc-detection-events", "value"),
    State("follower-decel-method", "value"),
    State("follower-threshold-pairs", "value"),
    State("plot-select", "value"),
    State("group-select", "value"),
    State("longitudinal-pairs", "value"),
    State("safety-pairs", "value"),
    State("event-lines", "value"),
    State("x-range-store", "data"),
    State("ylimit-mode", "value"),
    State("custom-y-limits-store", "data"),
    prevent_initial_call=True,
)
def export_visible_plots(n_clicks, experiment_type, case_key, lc_detection_method, lc_detection_events, follower_decel_method, follower_threshold_pairs, plot_select, groups, longitudinal_pairs, safety_pairs, event_lines, x_range, ylimit_mode, custom_y_limits):
    visible_plots = visible_plots_from_groups(groups, plot_select)
    if not case_key or not visible_plots:
        return "Nothing exported"
    experiment_type = experiment_type or EXPERIMENT_TYPE
    trial = get_trial(experiment_type, case_key, lc_detection_method=lc_detection_method, follower_decel_method=follower_decel_method, follower_threshold_pairs=follower_threshold_pairs)
    if trial is None:
        return "Nothing exported"
    
    # Write exports to the local cache folder
    export_folder = get_registry(experiment_type)["paths"]["export_folder"]
    local_export_folder = cache_path(export_folder)
    os.makedirs(local_export_folder, exist_ok=True)
    
    try:
        combined_path, individual_paths = export_trial_pngs(
            trial,
            local_export_folder,
            visible_plots,
            longitudinal_pairs,
            safety_pairs,
            x_range=x_range,
            visible_event_keys=event_lines,
            custom_y_limits=_effective_custom_y_limits(ylimit_mode, custom_y_limits),
            lc_detection_methods=lc_detection_method,
            lc_detection_events=lc_detection_events,
            follower_decel_methods=follower_decel_method,
            follower_threshold_pairs=follower_threshold_pairs,
        )
    except Exception as exc:
        return f"Export failed: {exc}"
    return f"Exported {1 + len(individual_paths)} PNG plots to locally cached export directory: {os.path.dirname(combined_path)}"


if __name__ == "__main__":
    from waitress import serve

    port = int(os.environ.get("PORT", 10000))
    serve(server, host="0.0.0.0", port=port)
import re
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import (
    FIGURE_TEMPLATE,
    DEFAULT_HEIGHT,
    COMBINED_HEIGHT_PER_PLOT,
    VEHICLE_COLORS,
    VEHICLE_MAP,
    PAIR_COLORS,
    PAIR_DISPLAY_LABELS,
    PAIR_LINE_DASHES,
    EVENT_LINE_STYLES,
    SAFETY_PARAMS,
    ALIAS_TO_VEHICLE,
    LANE_DROP_END_BY_SITE,
    LEFT_TURN_LANE_END_OFFSET_BY_SITE,
)
from plots.registry import PLOT_SPECS


def _base_layout(fig, title, height=DEFAULT_HEIGHT, x_range=None):
    fig.update_layout(
        template=FIGURE_TEMPLATE,
        title=dict(text=title, x=0.01, xanchor="left", y=0.97, yanchor="top", font=dict(size=18)),
        height=height,
        hovermode="x unified",
        dragmode="pan",
        font=dict(size=14),
        margin=dict(l=70, r=20, t=90, b=50),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=0.99,
            xanchor="right",
            x=0.99,
            font=dict(size=11),
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="rgba(0,0,0,0.15)",
            borderwidth=1,
        ),
    )
    fig.update_xaxes(title_text="Time (s)", range=x_range, showspikes=True, title_font=dict(size=16), tickfont=dict(size=13))
    fig.update_yaxes(title_font=dict(size=16), tickfont=dict(size=13))
    return fig


def _axis_ref(prefix, row):
    return prefix if row == 1 else f"{prefix}{row}"


def _event_annotation_text(style, x):
    return f"{style['label']}: {x:.2f} s"


def _add_event_line(fig, x, style, row=None, col=None, annotation_text=None):
    if x is None or not np.isfinite(x):
        return
    vline_kwargs = dict(x=x, line_color=style["color"], line_dash=style["dash"], line_width=2)
    if row is not None and col is not None:
        vline_kwargs.update(row=row, col=col)
    fig.add_vline(**vline_kwargs)

    xref = _axis_ref("x", row or 1)
    yref = f"{_axis_ref('y', row or 1)} domain"
    fig.add_annotation(
        x=x,
        y=1,
        xref=xref,
        yref=yref,
        text=annotation_text or _event_annotation_text(style, x),
        showarrow=False,
        yshift=-10,
        bgcolor="rgba(255,255,255,0.85)",
        bordercolor=style["color"],
        borderwidth=1,
        font=dict(size=10, color=style["color"]),
    )


def _lc_start_threshold_annotations(trial):
    threshold_specs = [
        ("0.10 m/s", "slope__LC Start @0.10 time"),
        ("0.15 m/s", "slope__LC Start @0.15 time"),
        ("0.25 m/s", "slope__LC Start @0.25 time"),
    ]
    annotations = []
    for label, column in threshold_specs:
        value = trial.raw_report_row.get(column)
        try:
            value = float(value)
        except Exception:
            continue
        if np.isfinite(value):
            annotations.append((label, value))
    return annotations


def _lc_end_threshold_annotations(trial):
    threshold_specs = [
        ("0.10 m/s", "slope__LC End @0.10 time"),
        ("0.15 m/s", "slope__LC End @0.15 time"),
        ("0.25 m/s", "slope__LC End @0.25 time"),
    ]
    annotations = []
    for label, column in threshold_specs:
        value = trial.raw_report_row.get(column)
        try:
            value = float(value)
        except Exception:
            continue
        if np.isfinite(value):
            annotations.append((label, value))
    return annotations


def _direct_lc_start_threshold_annotations(trial):
    threshold_specs = [
        ("0.10 m/s", "direct__LC Start Time @ 0.1"),
        ("0.15 m/s", "direct__LC Start Time @ 0.15"),
        ("0.25 m/s", "direct__LC Start Time @ 0.25"),
    ]
    annotations = []
    for label, column in threshold_specs:
        value = trial.raw_report_row.get(column)
        try:
            value = float(value)
        except Exception:
            continue
        if np.isfinite(value):
            annotations.append((label, value))
    return annotations


def _direct_lc_end_threshold_annotations(trial):
    threshold_specs = [
        ("0.10 m/s", "direct__LC End Time @ 0.1"),
        ("0.15 m/s", "direct__LC End Time @ 0.15"),
        ("0.25 m/s", "direct__LC End Time @ 0.25"),
    ]
    annotations = []
    for label, column in threshold_specs:
        value = trial.raw_report_row.get(column)
        try:
            value = float(value)
        except Exception:
            continue
        if np.isfinite(value):
            annotations.append((label, value))
    return annotations


def _follower_decel_threshold_annotations(trial, follower_alias):
    threshold_specs = [
        ("0.10 m/s2", f"follower_slope__{follower_alias} Braking SlopeReg1s @0.10 time"),
        ("0.15 m/s2", f"follower_slope__{follower_alias} Braking SlopeReg1s @0.15 time"),
        ("0.25 m/s2", f"follower_slope__{follower_alias} Braking SlopeReg1s @0.25 time"),
    ]
    annotations = []
    for label, column in threshold_specs:
        value = trial.raw_report_row.get(column)
        try:
            value = float(value)
        except Exception:
            continue
        if np.isfinite(value):
            annotations.append((label, value))
    return annotations


def _parse_follower_profile_pair_key(pair_key):
    match = re.match(r"dV(\d+)p(\d+)_Frac(\d+)_(\d+)", str(pair_key or ""))
    if not match:
        return None
    dv_whole, dv_frac, frac_num, frac_den = match.groups()
    frac_value = float(frac_num) / float(frac_den)
    return {
        "speed_diff_text": f"Speed diff: {dv_whole}.{dv_frac} m/s",
        "frac_num": float(frac_num),
        "frac_den": float(frac_den),
        "frac_value": frac_value,
    }



def _actual_peak_braking_magnitude(trial, threshold_time):
    dynamic = (trial.metrics or {}).get("dynamic", {}).get("target_follower")
    alias = None
    if dynamic is not None:
        alias_series = np.asarray(dynamic.get("alias"), dtype=object)
        timestamps = np.asarray(trial.timestamps, dtype=float)
        if timestamps.size and alias_series.size == timestamps.size and np.isfinite(threshold_time):
            idx = int(np.argmin(np.abs(timestamps - float(threshold_time))))
            alias = alias_series[idx]
    vehicle = ALIAS_TO_VEHICLE.get(alias) if alias else None
    if not vehicle:
        gap_value = str((trial.raw_report_row or {}).get("Gap", "")).strip().lower()
        if gap_value in {"zero", "0"}:
            vehicle = "Lead"
        elif gap_value in {"first", "1"}:
            vehicle = "F1"
        elif gap_value in {"second", "2"}:
            vehicle = "F2"
    if not vehicle:
        vehicle = "F1"
    acc = np.asarray((trial.metrics or {}).get("vehicle", {}).get(vehicle, {}).get("long_acc", []), dtype=float)
    acc = acc[np.isfinite(acc)]
    if acc.size == 0:
        return np.nan
    return max(0.0, float(-np.min(acc)))



def _follower_profile_threshold_annotations(trial, selected_pairs):
    annotations = []
    for pair_key in selected_pairs or []:
        column = f"follower_profile__Follower Braking ProfileThreshold time_{pair_key}"
        value = trial.raw_report_row.get(column)
        try:
            value = float(value)
        except Exception:
            continue
        if np.isfinite(value):
            parsed = _parse_follower_profile_pair_key(pair_key) or {}
            peak_mag = _actual_peak_braking_magnitude(trial, value)
            frac_value = parsed.get("frac_value")
            threshold_mag = peak_mag * frac_value if np.isfinite(peak_mag) and frac_value is not None else np.nan
            brake_text = (
                f'{threshold_mag:.2f} m/s2 (p: {peak_mag:.2f} m/s2)'
                if np.isfinite(threshold_mag) and np.isfinite(peak_mag)
                else 'Brake threshold'
            )
            annotations.append({
                "pair_key": pair_key,
                "time": value,
                "speed_diff_text": parsed.get("speed_diff_text", str(pair_key)),
                "brake_text": brake_text,
            })
    return annotations


def _add_threshold_band(fig, x0, x1, style, row=None, col=None, label_text=None, threshold_annotations=None, label_y=0.88, text_color="#cc6600", fill_opacity=0.12, threshold_y_positions=None, line_width=0, line_color=None):
    if x0 is None or x1 is None or not np.isfinite(x0) or not np.isfinite(x1):
        return False
    if x1 < x0:
        x0, x1 = x1, x0
    if np.isclose(x0, x1):
        return False

    vrect_kwargs = dict(
        x0=x0,
        x1=x1,
        fillcolor=style["color"],
        opacity=fill_opacity,
        line_width=line_width,
    )
    if line_color is not None:
        vrect_kwargs["line_color"] = line_color
    if row is not None and col is not None:
        vrect_kwargs.update(row=row, col=col)
    fig.add_vrect(**vrect_kwargs)

    xref = _axis_ref("x", row or 1)
    yref = f"{_axis_ref('y', row or 1)} domain"
    label_x = x1 + max(0.04, 0.25 * (x1 - x0))
    fig.add_annotation(
        x=label_x,
        y=label_y,
        xref=xref,
        yref=yref,
        text=label_text or f"{style['label']} region",
        textangle=-90,
        showarrow=False,
        font=dict(size=10, color=text_color),
        bgcolor="rgba(255,255,255,0.0)",
    )

    y_slots = threshold_y_positions or [0.72, 0.50, 0.28]
    for idx, (threshold_label, threshold_time) in enumerate(threshold_annotations or []):
        if threshold_time < x0 or threshold_time > x1:
            continue
        y_position = y_slots[min(idx, len(y_slots) - 1)]
        fig.add_annotation(
            x=threshold_time,
            y=y_position,
            xref=xref,
            yref=yref,
            text=threshold_label,
            textangle=-90,
            showarrow=False,
            font=dict(size=11, color=text_color),
            opacity=0.85,
            bgcolor="rgba(255,255,255,0.0)",
        )
    return True


def _with_band_color(style, band_color):
    styled = dict(style)
    styled["color"] = band_color
    return styled


def _add_lc_start_band(fig, trial, style, row=None, col=None):
    return _add_threshold_band(
        fig,
        trial.event_times.get("lc_start_band_min_sec"),
        trial.event_times.get("lc_start_band_max_sec"),
        style,
        row=row,
        col=col,
        label_text="SRLC",
        threshold_annotations=_lc_start_threshold_annotations(trial),
        label_y=0.88,
        text_color="#1f5fbf",
        fill_opacity=0.10,
        threshold_y_positions=[0.76, 0.54, 0.32],
    )


def _add_lc_end_band(fig, trial, style, row=None, col=None):
    return _add_threshold_band(
        fig,
        trial.event_times.get("lc_end_band_min_sec"),
        trial.event_times.get("lc_end_band_max_sec"),
        style,
        row=row,
        col=col,
        label_text="SRLC",
        threshold_annotations=_lc_end_threshold_annotations(trial),
        label_y=0.88,
        text_color="#1f5fbf",
        fill_opacity=0.10,
        threshold_y_positions=[0.76, 0.54, 0.32],
    )


def _add_direct_lc_start_band(fig, trial, style, row=None, col=None):
    return _add_threshold_band(
        fig,
        trial.event_times.get("direct_lc_start_sec"),
        trial.event_times.get("direct_lc_time_sec"),
        _with_band_color(style, "#8bc34a"),
        row=row,
        col=col,
        label_text="DTLC",
        threshold_annotations=_direct_lc_start_threshold_annotations(trial),
        label_y=0.88,
        text_color="#3f7d20",
        fill_opacity=0.10,
        threshold_y_positions=[0.76, 0.54, 0.32],
    )


def _add_direct_lc_end_band(fig, trial, style, row=None, col=None):
    return _add_threshold_band(
        fig,
        trial.event_times.get("direct_lc_end_sec"),
        trial.event_times.get("direct_lc_end_time_sec"),
        _with_band_color(style, "#8bc34a"),
        row=row,
        col=col,
        label_text="DTLC",
        threshold_annotations=_direct_lc_end_threshold_annotations(trial),
        label_y=0.88,
        text_color="#3f7d20",
        fill_opacity=0.10,
        threshold_y_positions=[0.76, 0.54, 0.32],
    )


def _add_follower_decel_band(fig, trial, event_key, style, row=None, col=None):
    if event_key == "f1_dec_sec":
        x0 = trial.event_times.get("f1_dec_band_min_sec")
        x1 = trial.event_times.get("f1_dec_band_max_sec")
        threshold_annotations = _follower_decel_threshold_annotations(trial, "F1")
    else:
        x0 = trial.event_times.get("f2_dec_band_min_sec")
        x1 = trial.event_times.get("f2_dec_band_max_sec")
        threshold_annotations = _follower_decel_threshold_annotations(trial, "F2")
    return _add_threshold_band(
        fig,
        x0,
        x1,
        _with_band_color(style, "#f2b8b5"),
        row=row,
        col=col,
        label_text="SRF",
        threshold_annotations=threshold_annotations,
        label_y=0.88,
        text_color="#b5564f",
        fill_opacity=0.16,
        threshold_y_positions=[0.76, 0.54, 0.32],
        line_width=1,
        line_color="#b5564f",
    )




def _add_follower_profile_band(fig, trial, style, selected_pairs, row=None, col=None):
    annotations = _follower_profile_threshold_annotations(trial, selected_pairs)
    if not annotations:
        return False
    times = [item["time"] for item in annotations]
    x0 = min(times)
    x1 = max(times)
    if np.isclose(x0, x1):
        x0 -= 0.05
        x1 += 0.05
    opacity = 0.08 if len(annotations) > 1 else 0.12
    profile_style = _with_band_color(style, "#bfe7c2")

    if x0 is None or x1 is None:
        return False
    if x1 < x0:
        x0, x1 = x1, x0

    vrect_kwargs = dict(x0=x0, x1=x1, fillcolor=profile_style["color"], opacity=opacity, line_width=0)
    if row is not None and col is not None:
        vrect_kwargs.update(row=row, col=col)
    fig.add_vrect(**vrect_kwargs)

    xref = _axis_ref("x", row or 1)
    yref = f"{_axis_ref('y', row or 1)} domain"
    fig.add_annotation(
        x=(x0 + x1) / 2.0,
        y=0.88,
        xref=xref,
        yref=yref,
        text="TSB",
        textangle=-90,
        showarrow=False,
        font=dict(size=12, color="#2e8b57"),
        bgcolor="rgba(255,255,255,0.0)",
    )

    for idx, item in enumerate(annotations):
        y_position = 0.72 - (idx * 0.22)
        fig.add_annotation(
            x=item["time"],
            y=max(y_position, 0.26),
            xref=xref,
            yref=yref,
            text=f'{item["speed_diff_text"]}<br>{item["brake_text"]}',
            textangle=-90,
            showarrow=False,
            align="center",
            font=dict(size=11, color="#2e8b57"),
            opacity=0.9,
            bgcolor="rgba(255,255,255,0.0)",
        )
    return True

def add_event_lines(fig, trial, visible_event_keys, row=None, col=None):
    visible_event_keys = visible_event_keys or []
    for event_key in visible_event_keys:
        x = trial.event_times.get(event_key)
        style = EVENT_LINE_STYLES.get(event_key)
        if style and x is not None and np.isfinite(x):
            _add_event_line(fig, x, style, row=row, col=col)
    return fig


def add_detection_bands(fig, trial, lc_detection_methods=None, follower_decel_methods=None, follower_threshold_pairs=None, lc_detection_events=None, row=None, col=None):
    lc_detection_methods = lc_detection_methods or []
    follower_decel_methods = follower_decel_methods or []
    follower_threshold_pairs = follower_threshold_pairs or []
    lc_detection_events = lc_detection_events or ["lc_start_sec", "lc_end_sec"]
    if "slope_regression_method" in lc_detection_methods:
        if "lc_start_sec" in lc_detection_events:
            _add_lc_start_band(fig, trial, EVENT_LINE_STYLES["lc_start_sec"], row=row, col=col)
        if "lc_end_sec" in lc_detection_events:
            _add_lc_end_band(fig, trial, EVENT_LINE_STYLES["lc_end_sec"], row=row, col=col)
    if "direct_threshold_method" in lc_detection_methods:
        if "lc_start_sec" in lc_detection_events:
            _add_direct_lc_start_band(fig, trial, EVENT_LINE_STYLES["lc_start_sec"], row=row, col=col)
        if "lc_end_sec" in lc_detection_events:
            _add_direct_lc_end_band(fig, trial, EVENT_LINE_STYLES["lc_end_sec"], row=row, col=col)
    if "slope_regression_method" in follower_decel_methods:
        _add_follower_decel_band(fig, trial, "f1_dec_sec", EVENT_LINE_STYLES["f1_dec_sec"], row=row, col=col)
        _add_follower_decel_band(fig, trial, "f2_dec_sec", EVENT_LINE_STYLES["f2_dec_sec"], row=row, col=col)
    if "profile_threshold_method" in follower_decel_methods and follower_threshold_pairs:
        _add_follower_profile_band(fig, trial, EVENT_LINE_STYLES["f1_dec_sec"], follower_threshold_pairs, row=row, col=col)
    return fig


def add_safety_bands(fig, metric_key):
    if metric_key == "ttc":
        fig.add_hrect(y0=0, y1=SAFETY_PARAMS["ttc_critical"], fillcolor="red", opacity=0.08, line_width=0)
        fig.add_hrect(y0=SAFETY_PARAMS["ttc_critical"], y1=SAFETY_PARAMS["ttc_warning"], fillcolor="orange", opacity=0.08, line_width=0)
    elif metric_key == "drac":
        fig.add_hrect(y0=SAFETY_PARAMS["drac_warning"], y1=SAFETY_PARAMS["drac_critical"], fillcolor="orange", opacity=0.08, line_width=0)
        fig.add_hrect(y0=SAFETY_PARAMS["drac_critical"], y1=SAFETY_PARAMS["drac_critical"] * 2, fillcolor="red", opacity=0.08, line_width=0)
    elif metric_key == "essm":
        fig.add_hrect(y0=SAFETY_PARAMS["essm_critical"], y1=SAFETY_PARAMS["essm_warning"], fillcolor="red", opacity=0.08, line_width=0)
        fig.add_hline(y=SAFETY_PARAMS["essm_warning"], line_color="orange", line_dash="dash", line_width=1)


def _resolve_y_limits(plot_key, custom_y_limits=None):
    if custom_y_limits and plot_key in custom_y_limits:
        limits = custom_y_limits.get(plot_key)
        if limits and len(limits) == 2:
            return limits
    return PLOT_SPECS[plot_key].y_limits


def _normalize_dynamic_alias(alias):
    if alias is None:
        return "None"
    if isinstance(alias, float) and not np.isfinite(alias):
        return "None"
    alias_text = str(alias).strip()
    return alias_text if alias_text else "None"


def _first_dynamic_alias(alias_series):
    for alias in alias_series:
        normalized = _normalize_dynamic_alias(alias)
        if normalized != "None":
            return normalized
    return "None"


def _dynamic_pair_legend_label(pair, alias):
    alias = _normalize_dynamic_alias(alias)
    if alias == "None":
        return "TLNone-X" if pair == "TL_X" else "X-TFNone"
    if pair == "TL_X":
        return f"{alias}X"
    return f"X{alias}"


def _dynamic_trace_color(plot_key, pair, alias, fallback_color):
    alias = _normalize_dynamic_alias(alias)
    if plot_key in {"longitudinal_spacing", "longitudinal_headway", "longitudinal_tau"}:
        if pair == "TL_X":
            return "#7a3db8"
        if pair == "X_TF":
            return "#ea801c"
    if plot_key in {"ttc", "drac", "essm"}:
        if pair == "TL_X":
            return "#7a3db8"
        if pair == "X_TF":
            return "#ea801c"
    return fallback_color


def _static_trace_color(plot_key, pair):
    if plot_key in {"longitudinal_spacing", "longitudinal_headway", "longitudinal_tau"}:
        if pair == "AB":
            return "#e9c716"
        if pair == "BC":
            return "#50ad9f"
    return PAIR_COLORS.get(pair)


def _add_dynamic_pair_traces(fig, trial, plot_key, pair, values, color):
    dynamic_key = "target_leader" if pair == "TL_X" else "target_follower"
    dynamic_payload = trial.metrics.get("dynamic", {}).get(dynamic_key)
    if not dynamic_payload or values is None:
        return

    alias_series = np.asarray([_normalize_dynamic_alias(alias) for alias in dynamic_payload["alias"]], dtype=object)
    values = np.asarray(values, dtype=float)
    timestamps = np.asarray(trial.timestamps, dtype=float)
    auto_sec = trial.event_times.get("auto_sec")
    time_mask = np.isfinite(timestamps)
    primary_window_mask = time_mask.copy()
    if auto_sec is not None and np.isfinite(auto_sec):
        window_start = auto_sec - 5.0
        time_mask &= timestamps >= window_start
        primary_window_mask &= (timestamps >= window_start) & (timestamps <= auto_sec)

    primary_alias = _first_dynamic_alias(alias_series[primary_window_mask])
    if primary_alias == "None":
        primary_alias = _first_dynamic_alias(alias_series[time_mask])

    for alias in ["None", "A", "B", "C"]:
        mask = (alias_series == alias) & time_mask
        if not np.any(mask):
            continue
        y = np.where(mask, values, np.nan)
        fig.add_trace(go.Scatter(
            x=trial.timestamps,
            y=y,
            mode="lines",
            name=_dynamic_pair_legend_label(pair, alias),
            line=dict(
                width=2,
                color=_dynamic_trace_color(plot_key, pair, alias, color),
                dash="solid" if alias == primary_alias else "dash",
            ),
        ))


def _vehicle_trace_color(plot_key, vehicle):
    if plot_key in {"longitudinal_position", "longitudinal_speed", "longitudinal_acceleration", "lateral_position", "lateral_speed", "lateral_acceleration"}:
        special_colors = {
            "Lead": "#0000a2",
            "LC": "#bc272d",
            "F1": "#e9c716",
            "F2": "#50ad9f",
        }
        return special_colors.get(vehicle, VEHICLE_COLORS.get(vehicle))
    return VEHICLE_COLORS.get(vehicle)


def build_vehicle_plot(trial, plot_key, x_range=None, visible_event_keys=None, height=DEFAULT_HEIGHT, custom_y_limits=None, lc_detection_methods=None, follower_decel_methods=None, follower_threshold_pairs=None, lc_detection_events=None):
    spec = PLOT_SPECS[plot_key]
    metric_map = {
        "longitudinal_position": "oblique_position",
        "longitudinal_speed": "speed",
        "longitudinal_acceleration": "long_acc",
        "lateral_position": "lateral",
        "lateral_speed": "lat_speed",
        "lateral_acceleration": "lat_acc",
    }
    metric_name = metric_map[plot_key]
    fig = go.Figure()
    for vehicle, payload in trial.metrics["vehicle"].items():
        fig.add_trace(go.Scatter(
            x=trial.timestamps,
            y=payload[metric_name],
            mode="lines",
            name=VEHICLE_MAP.get(vehicle, vehicle),
            line=dict(width=2, color=_vehicle_trace_color(plot_key, vehicle)),
        ))
    fig.update_yaxes(title_text=spec.y_label, range=_resolve_y_limits(plot_key, custom_y_limits))
    _base_layout(fig, spec.title, height=height, x_range=x_range)
    add_event_lines(fig, trial, visible_event_keys)
    add_detection_bands(fig, trial, lc_detection_methods=lc_detection_methods, follower_decel_methods=follower_decel_methods, follower_threshold_pairs=follower_threshold_pairs, lc_detection_events=lc_detection_events)
    return fig


def build_lane_end_distance_plot(trial, x_range=None, visible_event_keys=None, height=DEFAULT_HEIGHT, custom_y_limits=None, lc_detection_methods=None, follower_decel_methods=None, follower_threshold_pairs=None, lc_detection_events=None):
    spec = PLOT_SPECS["lane_end_distance"]
    if trial.site_id not in LANE_DROP_END_BY_SITE:
        fig = go.Figure()
        fig.update_layout(template=FIGURE_TEMPLATE, title="Lane-end data unavailable", height=height)
        return fig

    x_vehicle = trial.metrics.get("vehicle", {}).get("LC")
    if not x_vehicle:
        fig = go.Figure()
        fig.update_layout(template=FIGURE_TEMPLATE, title="Vehicle X data unavailable", height=height)
        return fig

    x_dist = np.asarray(x_vehicle["distance"], dtype=float)
    left_turn_lane_end = float(LANE_DROP_END_BY_SITE[trial.site_id])
    physical_lane_end = left_turn_lane_end + float(LEFT_TURN_LANE_END_OFFSET_BY_SITE[trial.site_id])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=trial.timestamps,
        y=physical_lane_end - x_dist,
        mode="lines",
        name="Physical Lane End",
        line=dict(width=2, color="#1f77b4"),
    ))
    fig.add_trace(go.Scatter(
        x=trial.timestamps,
        y=left_turn_lane_end - x_dist,
        mode="lines",
        name="Left Turn Lane End",
        line=dict(width=2, color="#2ca02c"),
    ))
    fig.update_yaxes(title_text=spec.y_label, range=_resolve_y_limits("lane_end_distance", custom_y_limits))
    _base_layout(fig, spec.title, height=height, x_range=x_range)
    add_event_lines(fig, trial, visible_event_keys)
    add_detection_bands(fig, trial, lc_detection_methods=lc_detection_methods, follower_decel_methods=follower_decel_methods, follower_threshold_pairs=follower_threshold_pairs, lc_detection_events=lc_detection_events)
    return fig


def _build_longitudinal_pair_plot(trial, plot_key, value_key, enabled_pairs=None, x_range=None, visible_event_keys=None, height=DEFAULT_HEIGHT, custom_y_limits=None, lc_detection_methods=None, follower_decel_methods=None, follower_threshold_pairs=None, lc_detection_events=None):
    spec = PLOT_SPECS[plot_key]
    fig = go.Figure()
    for pair in (enabled_pairs or []):
        if pair in {"TL_X", "X_TF"}:
            payload = trial.metrics["pairwise"].get(pair)
            _add_dynamic_pair_traces(fig, trial, plot_key, pair, None if payload is None else payload.get(value_key), PAIR_COLORS.get(pair))
            continue
        payload = trial.metrics["pairwise"].get(pair)
        if payload is None or payload.get(value_key) is None:
            continue
        fig.add_trace(go.Scatter(
            x=trial.timestamps,
            y=payload[value_key],
            mode="lines",
            name=PAIR_DISPLAY_LABELS.get(pair, pair),
            line=dict(width=2, color=_static_trace_color(plot_key, pair), dash=PAIR_LINE_DASHES.get(pair, "solid")),
        ))
    fig.update_yaxes(title_text=spec.y_label, range=_resolve_y_limits(plot_key, custom_y_limits))
    _base_layout(fig, spec.title, height=height, x_range=x_range)
    add_event_lines(fig, trial, visible_event_keys)
    add_detection_bands(fig, trial, lc_detection_methods=lc_detection_methods, follower_decel_methods=follower_decel_methods, follower_threshold_pairs=follower_threshold_pairs, lc_detection_events=lc_detection_events)
    return fig


def build_longitudinal_spacing_plot(trial, enabled_pairs=None, x_range=None, visible_event_keys=None, height=DEFAULT_HEIGHT, custom_y_limits=None, lc_detection_methods=None, follower_decel_methods=None, follower_threshold_pairs=None, lc_detection_events=None):
    return _build_longitudinal_pair_plot(
        trial,
        "longitudinal_spacing",
        "spacing",
        enabled_pairs=enabled_pairs,
        x_range=x_range,
        visible_event_keys=visible_event_keys,
        height=height,
        custom_y_limits=custom_y_limits,
        lc_detection_methods=lc_detection_methods,
        follower_decel_methods=follower_decel_methods,
        follower_threshold_pairs=follower_threshold_pairs,
        lc_detection_events=lc_detection_events,
    )


def build_longitudinal_headway_plot(trial, enabled_pairs=None, x_range=None, visible_event_keys=None, height=DEFAULT_HEIGHT, custom_y_limits=None, lc_detection_methods=None, follower_decel_methods=None, follower_threshold_pairs=None, lc_detection_events=None):
    return _build_longitudinal_pair_plot(
        trial,
        "longitudinal_headway",
        "headway",
        enabled_pairs=enabled_pairs,
        x_range=x_range,
        visible_event_keys=visible_event_keys,
        height=height,
        custom_y_limits=custom_y_limits,
        lc_detection_methods=lc_detection_methods,
        follower_decel_methods=follower_decel_methods,
        follower_threshold_pairs=follower_threshold_pairs,
        lc_detection_events=lc_detection_events,
    )


def build_longitudinal_tau_plot(trial, enabled_pairs=None, x_range=None, visible_event_keys=None, height=DEFAULT_HEIGHT, custom_y_limits=None, lc_detection_methods=None, follower_decel_methods=None, follower_threshold_pairs=None, lc_detection_events=None):
    return _build_longitudinal_pair_plot(
        trial,
        "longitudinal_tau",
        "tau",
        enabled_pairs=enabled_pairs,
        x_range=x_range,
        visible_event_keys=visible_event_keys,
        height=height,
        custom_y_limits=custom_y_limits,
        lc_detection_methods=lc_detection_methods,
        follower_decel_methods=follower_decel_methods,
        follower_threshold_pairs=follower_threshold_pairs,
        lc_detection_events=lc_detection_events,
    )


def build_safety_plot(trial, metric_key, enabled_pairs=None, x_range=None, visible_event_keys=None, height=DEFAULT_HEIGHT, custom_y_limits=None, lc_detection_methods=None, follower_decel_methods=None, follower_threshold_pairs=None, lc_detection_events=None):
    spec = PLOT_SPECS[metric_key]
    fig = go.Figure()
    for pair in (enabled_pairs or []):
        payload = trial.metrics["safety"].get(pair)
        if payload is None or payload.get(metric_key) is None:
            continue
        if pair == "X_TARGET_LEADER":
            _add_dynamic_pair_traces(fig, trial, metric_key, "TL_X", payload.get(metric_key), PAIR_COLORS.get(pair))
            continue
        if pair == "TARGET_FOLLOWER_X":
            _add_dynamic_pair_traces(fig, trial, metric_key, "X_TF", payload.get(metric_key), PAIR_COLORS.get(pair))
            continue
        fig.add_trace(go.Scatter(
            x=trial.timestamps,
            y=payload[metric_key],
            mode="lines",
            name=pair,
            line=dict(width=2, color=PAIR_COLORS.get(pair)),
        ))
    fig.update_yaxes(title_text=spec.y_label, range=_resolve_y_limits(metric_key, custom_y_limits))
    _base_layout(fig, spec.title, height=height, x_range=x_range)
    add_event_lines(fig, trial, visible_event_keys)
    add_detection_bands(fig, trial, lc_detection_methods=lc_detection_methods, follower_decel_methods=follower_decel_methods, follower_threshold_pairs=follower_threshold_pairs, lc_detection_events=lc_detection_events)
    add_safety_bands(fig, metric_key)
    return fig


def build_single_plot_figure(trial, plot_key, enabled_longitudinal_pairs=None, enabled_safety_pairs=None, x_range=None, visible_event_keys=None, height=DEFAULT_HEIGHT, custom_y_limits=None, lc_detection_methods=None, follower_decel_methods=None, follower_threshold_pairs=None, lc_detection_events=None):
    if plot_key in {"longitudinal_position", "longitudinal_speed", "longitudinal_acceleration", "lateral_position", "lateral_speed", "lateral_acceleration"}:
        return build_vehicle_plot(trial, plot_key, x_range=x_range, visible_event_keys=visible_event_keys, height=height, custom_y_limits=custom_y_limits, lc_detection_methods=lc_detection_methods, follower_decel_methods=follower_decel_methods, follower_threshold_pairs=follower_threshold_pairs, lc_detection_events=lc_detection_events)
    if plot_key == "lane_end_distance":
        return build_lane_end_distance_plot(trial, x_range=x_range, visible_event_keys=visible_event_keys, height=height, custom_y_limits=custom_y_limits, lc_detection_methods=lc_detection_methods, follower_decel_methods=follower_decel_methods, follower_threshold_pairs=follower_threshold_pairs, lc_detection_events=lc_detection_events)
    if plot_key == "longitudinal_spacing":
        return build_longitudinal_spacing_plot(trial, enabled_pairs=enabled_longitudinal_pairs, x_range=x_range, visible_event_keys=visible_event_keys, height=height, custom_y_limits=custom_y_limits, lc_detection_methods=lc_detection_methods, follower_decel_methods=follower_decel_methods, follower_threshold_pairs=follower_threshold_pairs, lc_detection_events=lc_detection_events)
    if plot_key == "longitudinal_headway":
        return build_longitudinal_headway_plot(trial, enabled_pairs=enabled_longitudinal_pairs, x_range=x_range, visible_event_keys=visible_event_keys, height=height, custom_y_limits=custom_y_limits, lc_detection_methods=lc_detection_methods, follower_decel_methods=follower_decel_methods, follower_threshold_pairs=follower_threshold_pairs, lc_detection_events=lc_detection_events)
    if plot_key == "longitudinal_tau":
        return build_longitudinal_tau_plot(trial, enabled_pairs=enabled_longitudinal_pairs, x_range=x_range, visible_event_keys=visible_event_keys, height=height, custom_y_limits=custom_y_limits, lc_detection_methods=lc_detection_methods, follower_decel_methods=follower_decel_methods, follower_threshold_pairs=follower_threshold_pairs, lc_detection_events=lc_detection_events)
    if plot_key in {"ttc", "drac", "essm"}:
        return build_safety_plot(trial, plot_key, enabled_pairs=enabled_safety_pairs, x_range=x_range, visible_event_keys=visible_event_keys, height=height, custom_y_limits=custom_y_limits, lc_detection_methods=lc_detection_methods, follower_decel_methods=follower_decel_methods, follower_threshold_pairs=follower_threshold_pairs, lc_detection_events=lc_detection_events)
    raise KeyError(plot_key)


def _add_subplot_label(fig, row, text):
    fig.add_annotation(
        x=0.01,
        y=0.98,
        xref=_axis_ref("x", row),
        yref=f"{_axis_ref('y', row)} domain",
        text=text,
        showarrow=False,
        xanchor="left",
        yanchor="top",
        bgcolor="rgba(255,255,255,0.85)",
        bordercolor="rgba(0,0,0,0.15)",
        borderwidth=1,
        font=dict(size=11),
    )


def _combined_legend_group(plot_key):
    return PLOT_SPECS[plot_key].title


def build_combined_figure(trial, plot_keys, enabled_longitudinal_pairs=None, enabled_safety_pairs=None, x_range=None, visible_event_keys=None, custom_y_limits=None, lc_detection_methods=None, follower_decel_methods=None, follower_threshold_pairs=None, lc_detection_events=None):
    plot_keys = list(plot_keys)
    if not plot_keys:
        fig = go.Figure()
        fig.update_layout(template=FIGURE_TEMPLATE, title="No plots selected")
        return fig

    fig = make_subplots(rows=len(plot_keys), cols=1, shared_xaxes=True, vertical_spacing=0.03)
    seen_group_names_by_row = {}
    for row, plot_key in enumerate(plot_keys, start=1):
        single = build_single_plot_figure(
            trial,
            plot_key,
            enabled_longitudinal_pairs=enabled_longitudinal_pairs,
            enabled_safety_pairs=enabled_safety_pairs,
            x_range=x_range,
            visible_event_keys=visible_event_keys,
            height=DEFAULT_HEIGHT,
            custom_y_limits=custom_y_limits,
            lc_detection_methods=lc_detection_methods,
            follower_decel_methods=follower_decel_methods,
            follower_threshold_pairs=follower_threshold_pairs,
            lc_detection_events=lc_detection_events,
        )
        legend_name = "legend" if row == 1 else f"legend{row}"
        seen_names = set()
        seen_group_names_by_row[row] = seen_names
        for trace in single.data:
            unique_key = trace.name
            trace.legend = legend_name
            trace.legendgroup = f"row_{row}"
            trace.showlegend = unique_key not in seen_names
            if unique_key not in seen_names:
                seen_names.add(unique_key)
            fig.add_trace(trace, row=row, col=1)
        fig.update_yaxes(title_text=PLOT_SPECS[plot_key].y_label, range=_resolve_y_limits(plot_key, custom_y_limits), title_font=dict(size=16), tickfont=dict(size=13), row=row, col=1)
        fig.update_xaxes(title_text="Time (s)", range=x_range, showticklabels=True, title_font=dict(size=16), tickfont=dict(size=13), row=row, col=1)
        _add_subplot_label(fig, row, PLOT_SPECS[plot_key].title)
        add_event_lines(fig, trial, visible_event_keys, row=row, col=1)
        add_detection_bands(fig, trial, lc_detection_methods=lc_detection_methods, follower_decel_methods=follower_decel_methods, follower_threshold_pairs=follower_threshold_pairs, lc_detection_events=lc_detection_events, row=row, col=1)

    legend_layout = {}
    for row, plot_key in enumerate(plot_keys, start=1):
        axis_name = "yaxis" if row == 1 else f"yaxis{row}"
        domain = getattr(fig.layout, axis_name).domain
        legend_key = "legend" if row == 1 else f"legend{row}"
        legend_layout[legend_key] = dict(
            orientation="v",
            yanchor="top",
            y=float(domain[1]) - 0.01,
            xanchor="left",
            x=1.01,
            font=dict(size=9),
            bgcolor="rgba(255,255,255,0.88)",
            bordercolor="rgba(0,0,0,0.12)",
            borderwidth=1,
            groupclick="toggleitem",
            itemclick="toggle",
            itemdoubleclick="toggleothers",
        )

    fig.update_layout(
        template=FIGURE_TEMPLATE,
        height=max(450, len(plot_keys) * COMBINED_HEIGHT_PER_PLOT),
        hovermode="x unified",
        dragmode="pan",
        font=dict(size=14),
        margin=dict(l=80, r=180, t=60, b=50),
        **legend_layout,
    )
    return fig


def build_summary_rows(trial, enabled_safety_pairs):
    auto_sec = trial.event_times.get("auto_sec")
    lc_start_sec = trial.event_times.get("lc_start_sec")
    lc_end_sec = trial.event_times.get("lc_end_sec")
    lc_cross_sec = trial.event_times.get("lc_cross_sec")
    timestamps = np.asarray(trial.timestamps, dtype=float)

    def _build_summary_mask(end_time):
        mask = np.isfinite(timestamps)
        if auto_sec is not None and np.isfinite(auto_sec):
            mask &= timestamps >= auto_sec
        if end_time is not None and np.isfinite(end_time):
            mask &= timestamps <= end_time
        return mask

    default_start = lc_start_sec if lc_start_sec is not None and np.isfinite(lc_start_sec) else auto_sec
    default_end = lc_end_sec + 15.0 if lc_end_sec is not None and np.isfinite(lc_end_sec) else None
    endpoint_start = auto_sec if auto_sec is not None and np.isfinite(auto_sec) else lc_start_sec

    def _build_mask_with_bounds(start_time, end_time):
        mask = np.isfinite(timestamps)
        if start_time is not None and np.isfinite(start_time):
            mask &= timestamps >= start_time
        if end_time is not None and np.isfinite(end_time):
            mask &= timestamps <= end_time
        return mask

    default_mask = _build_mask_with_bounds(default_start, default_end)
    endpoint_mask = _build_mask_with_bounds(endpoint_start, lc_cross_sec)

    def _masked_min(values, mask):
        values = np.asarray(values, dtype=float)
        values = values[mask & np.isfinite(values)]
        return float(np.min(values)) if values.size else np.nan

    def _masked_max(values, mask):
        values = np.asarray(values, dtype=float)
        values = values[mask & np.isfinite(values)]
        return float(np.max(values)) if values.size else np.nan

    def _time_at_extreme(values, mask, mode):
        values = np.asarray(values, dtype=float)
        valid_mask = mask & np.isfinite(values)
        valid_values = values[valid_mask]
        valid_times = timestamps[valid_mask]
        if not valid_values.size:
            return np.nan
        idx = np.argmin(valid_values) if mode == "min" else np.argmax(valid_values)
        return float(valid_times[idx])

    rows = []
    for pair in enabled_safety_pairs or []:
        payload = trial.metrics["safety"].get(pair)
        if not payload:
            continue
        mask = endpoint_mask if pair in {"X_LANE_DROP_END", "X_LEFT_TURN_LANE_END"} else default_mask
        min_ttc = _masked_min(payload["ttc"], mask)
        max_drac = _masked_max(payload["drac"], mask)
        min_essm = _masked_min(payload["essm"], mask)
        min_ttc_time = _time_at_extreme(payload["ttc"], mask, "min")
        max_drac_time = _time_at_extreme(payload["drac"], mask, "max")
        min_essm_time = _time_at_extreme(payload["essm"], mask, "min")
        rows.append({
            "Pair": pair,
            "Min TTC": None if not np.isfinite(min_ttc) else round(min_ttc, 3),
            "Time @ Min TTC (s)": None if not np.isfinite(min_ttc_time) else round(min_ttc_time, 3),
            "Max DRAC": None if not np.isfinite(max_drac) else round(max_drac, 3),
            "Time @ Max DRAC (s)": None if not np.isfinite(max_drac_time) else round(max_drac_time, 3),
            "Min ESSM": None if not np.isfinite(min_essm) else round(min_essm, 3),
            "Time @ Min ESSM (s)": None if not np.isfinite(min_essm_time) else round(min_essm_time, 3),
        })
    return rows

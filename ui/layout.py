from dash import dcc, html
from config import (
    APP_TITLE,
    EXPERIMENT_OPTIONS,
    EXPERIMENT_TYPE,
    PLOT_GROUPS,
    PAIR_DISPLAY_LABELS,
    LC_DETECTION_METHODS,
    FOLLOWER_DECEL_METHODS,
    FOLLOWER_PROFILE_THRESHOLD_PAIRS,
    DEFAULT_ENABLED_GROUPS,
    DEFAULT_VISIBLE_EVENT_LINES,
    DEFAULT_LONGITUDINAL_PAIRS,
    DEFAULT_SAFETY_PAIRS,
    DEFAULT_VIEW_MODE,
)
from plots.registry import PLOT_SPECS


def plot_card(plot_key):
    return html.Div(
        [
            html.Div(
                [
                    html.H4(PLOT_SPECS[plot_key].title, style={"margin": "0"}),
                    html.Div([
                        html.Button("Open popup", id={"type": "open-popup", "index": plot_key}, n_clicks=0),
                        html.Button("Reset zoom", id={"type": "reset-zoom", "index": plot_key}, n_clicks=0, style={"marginLeft": "8px"}),
                    ]),
                ],
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"},
            ),
            dcc.Graph(id={"type": "plot-graph", "index": plot_key}, config={"displaylogo": False, "scrollZoom": True}),
        ],
        style={"border": "1px solid #ddd", "borderRadius": "10px", "padding": "10px", "marginBottom": "14px", "background": "white"},
    )


def build_layout(case_options):
    plot_keys = [k for group in PLOT_GROUPS.values() for k in group]
    return html.Div([
        html.Div([
            html.Div([
                html.H1(APP_TITLE, style={"margin": "0", "color": "white", "fontSize": "30px"}),
                html.Div("SHINE LAB", style={"marginTop": "6px", "color": "#ffd7d7", "fontWeight": "700", "letterSpacing": "0.12em"}),
            ]),
        ], style={"background": "#CC0000", "padding": "22px 24px", "borderRadius": "16px", "boxShadow": "0 10px 30px rgba(102,0,0,0.18)", "marginBottom": "18px"}),
        html.Div(id="case-count-label", children=f"Found {len(case_options)} valid files.", style={"fontWeight": "700", "marginBottom": "10px", "color": "#990000"}),
        html.H3("Select Files", style={"marginBottom": "10px"}),
        html.Div([
            html.Div([
                html.Label("Experiment"),
                dcc.Dropdown(
                    id="experiment-select",
                    options=[{"label": exp, "value": exp} for exp in EXPERIMENT_OPTIONS],
                    value=EXPERIMENT_TYPE,
                    clearable=False,
                ),
            ], style={"flex": 1}),
            html.Div([
                html.Label("Primary case"),
                dcc.Dropdown(id="case-select", options=case_options, value=case_options[0]["value"] if case_options else None, clearable=False),
            ], style={"flex": 2}),
        ], style={"display": "flex", "gap": "14px", "marginBottom": "12px", "background": "white", "padding": "16px", "borderRadius": "14px", "boxShadow": "0 6px 18px rgba(0,0,0,0.05)"}),
        html.Div([
            html.Div([
                html.Label("Site"),
                dcc.Dropdown(id="site-filter", options=[], value=None, clearable=True, placeholder="All"),
            ], style={"flex": 1}),
            html.Div([
                html.Label("Configuration"),
                dcc.Dropdown(id="configuration-filter", options=[], value=None, clearable=True, placeholder="All"),
            ], style={"flex": 2}),
            html.Div([
                html.Label("Gap"),
                dcc.Dropdown(id="gap-filter", options=[], value=None, clearable=True, placeholder="All"),
            ], style={"flex": 1}),
            html.Div([
                html.Label("DS"),
                dcc.Dropdown(id="ds-filter", options=[], value=None, clearable=True, placeholder="All"),
            ], style={"flex": 1}),
            html.Div([
                html.Label("DV"),
                dcc.Dropdown(id="dv-filter", options=[], value=None, clearable=True, placeholder="All"),
            ], style={"flex": 1}),
        ], style={"display": "flex", "gap": "14px", "marginBottom": "12px", "background": "white", "padding": "16px", "borderRadius": "14px", "boxShadow": "0 6px 18px rgba(0,0,0,0.05)"}),

        html.Div([
            dcc.Checklist(
                id="compare-mode",
                options=[{"label": "View two cases side by side", "value": "enabled"}],
                value=[],
                inline=True,
            ),
        ], style={"marginBottom": "12px", "background": "white", "padding": "14px 16px", "borderRadius": "14px", "boxShadow": "0 6px 18px rgba(0,0,0,0.05)"}),
        html.Div(
            id="compare-select-wrap",
            children=[
                html.Div([
                    html.Div([
                        html.Label("Compare experiment"),
                        dcc.Dropdown(
                            id="compare-experiment-select",
                            options=[{"label": exp, "value": exp} for exp in EXPERIMENT_OPTIONS],
                            value=EXPERIMENT_TYPE,
                            clearable=False,
                        ),
                    ], style={"flex": 1}),
                    html.Div([
                        html.Label("Compare case"),
                        dcc.Dropdown(id="compare-case-select", options=case_options, value=case_options[1]["value"] if len(case_options) > 1 else None, clearable=False),
                    ], style={"flex": 2}),
                ], style={"display": "flex", "gap": "14px", "marginBottom": "12px"}),
                html.Div([
                    html.Div([
                        html.Label("Compare Site"),
                        dcc.Dropdown(id="compare-site-filter", options=[], value=None, clearable=True, placeholder="All"),
                    ], style={"flex": 1}),
                    html.Div([
                        html.Label("Compare Configuration"),
                        dcc.Dropdown(id="compare-configuration-filter", options=[], value=None, clearable=True, placeholder="All"),
                    ], style={"flex": 2}),
                    html.Div([
                        html.Label("Compare Gap"),
                        dcc.Dropdown(id="compare-gap-filter", options=[], value=None, clearable=True, placeholder="All"),
                    ], style={"flex": 1}),
                    html.Div([
                        html.Label("Compare DS"),
                        dcc.Dropdown(id="compare-ds-filter", options=[], value=None, clearable=True, placeholder="All"),
                    ], style={"flex": 1}),
                    html.Div([
                        html.Label("Compare DV"),
                        dcc.Dropdown(id="compare-dv-filter", options=[], value=None, clearable=True, placeholder="All"),
                    ], style={"flex": 1}),
                ], style={"display": "flex", "gap": "14px"}),
            ],
            style={"display": "none", "gap": "14px", "marginBottom": "12px", "background": "white", "padding": "16px", "borderRadius": "14px", "boxShadow": "0 6px 18px rgba(0,0,0,0.05)"},
        ),
        html.Div(id="selected-file-label", style={"marginBottom": "10px", "color": "#444"}),
        html.A(
            "Open Video",
            id="open-video-link",
            href="",
            target="_blank",
            style={"display": "none", "marginBottom": "12px", "fontWeight": "600"},
        ),
        html.A(
            "Open Compare Video",
            id="open-compare-video-link",
            href="",
            target="_blank",
            style={"display": "none", "marginBottom": "12px", "marginLeft": "12px", "fontWeight": "600"},
        ),

        html.Div([
            html.H3("Filters", style={"margin": "0"}),
            html.Div([
                html.Button("Select all", id="select-all-filters", n_clicks=0),
                html.Button("Deselect all", id="deselect-all-filters", n_clicks=0, style={"marginLeft": "8px"}),
            ]),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "10px", "color": "#990000"}),
        html.Div([
            html.Label("Plot groups"),
            dcc.Dropdown(
                id="group-select",
                options=[{"label": key.title(), "value": key} for key in PLOT_GROUPS],
                value=DEFAULT_ENABLED_GROUPS,
                multi=True,
                clearable=True,
            ),
        ], style={"marginBottom": "12px", "background": "white", "padding": "16px", "borderRadius": "14px", "boxShadow": "0 6px 18px rgba(0,0,0,0.05)"}),
        html.Div([
            html.Div([
                html.Label("Visible plots"),
                dcc.Dropdown(
                    id="plot-select",
                    options=[{"label": PLOT_SPECS[k].title, "value": k} for k in plot_keys],
                    value=plot_keys,
                    multi=True,
                    clearable=True,
                ),
            ]),
        ], style={"marginBottom": "12px", "background": "white", "padding": "16px", "borderRadius": "14px", "boxShadow": "0 6px 18px rgba(0,0,0,0.05)"}),

        html.Div([
            html.Div([
                html.Label("Longitudinal spacing pairs"),
                dcc.Dropdown(
                    id="longitudinal-pairs",
                    options=[{"label": PAIR_DISPLAY_LABELS[k], "value": k} for k in ["AB", "BC", "TL_X", "X_TF"]],
                    value=DEFAULT_LONGITUDINAL_PAIRS,
                    multi=True,
                    clearable=True,
                ),
            ], style={"marginBottom": "8px"}),
            html.Div([
                html.Label("Safety pairs"),
                dcc.Dropdown(
                    id="safety-pairs",
                    options=[{"label": PAIR_DISPLAY_LABELS[k], "value": k} for k in ["X_TARGET_LEADER", "TARGET_FOLLOWER_X", "BA", "CB", "X_LANE_DROP_END", "X_LEFT_TURN_LANE_END"]],
                    value=DEFAULT_SAFETY_PAIRS,
                    multi=True,
                    clearable=True,
                ),
            ]),
        ], style={"marginBottom": "12px", "background": "white", "padding": "16px", "borderRadius": "14px", "boxShadow": "0 6px 18px rgba(0,0,0,0.05)"}),

        html.Div([
            html.Label("Event lines"),
            dcc.Dropdown(
                id="event-lines",
                options=[
                    {"label": "Auto Mode Time", "value": "auto_sec"},
                    {"label": "LC Start", "value": "lc_start_sec"},
                    {"label": "LC End", "value": "lc_end_sec"},
                    {"label": "LC Cross", "value": "lc_cross_sec"},
                    {"label": "F1 dec", "value": "f1_dec_sec"},
                    {"label": "F2 dec", "value": "f2_dec_sec"},
                    {"label": "LOS Time", "value": "los_sec"},
                ],
                value=DEFAULT_VISIBLE_EVENT_LINES,
                multi=True,
                clearable=True,
            ),
        ], style={"marginBottom": "12px", "background": "white", "padding": "16px", "borderRadius": "14px", "boxShadow": "0 6px 18px rgba(0,0,0,0.05)"}),

        html.Div([
            html.Label("LC Detection Method"),
            dcc.Dropdown(
                id="lc-detection-method",
                options=[{"label": label, "value": key} for key, label in LC_DETECTION_METHODS.items()],
                value=[],
                multi=True,
                clearable=True,
                placeholder="Optional slope-regression band",
            ),
        ], style={"marginBottom": "12px", "background": "white", "padding": "16px", "borderRadius": "14px", "boxShadow": "0 6px 18px rgba(0,0,0,0.05)"}),

        html.Div([
            html.Label("LC Detection Band"),
            dcc.Dropdown(
                id="lc-detection-events",
                options=[
                    {"label": "LC Start", "value": "lc_start_sec"},
                    {"label": "LC End", "value": "lc_end_sec"},
                ],
                value=["lc_start_sec", "lc_end_sec"],
                multi=True,
                clearable=True,
                placeholder="Select LC slope band visibility",
            ),
        ], style={"marginBottom": "12px", "background": "white", "padding": "16px", "borderRadius": "14px", "boxShadow": "0 6px 18px rgba(0,0,0,0.05)"}),

        html.Div([
            html.Label("Follower Deceleration Detection Method"),
            dcc.Dropdown(
                id="follower-decel-method",
                options=[{"label": label, "value": key} for key, label in FOLLOWER_DECEL_METHODS.items()],
                value=[],
                multi=True,
                clearable=True,
                placeholder="Optional follower-detection band",
            ),
        ], style={"marginBottom": "12px", "background": "white", "padding": "16px", "borderRadius": "14px", "boxShadow": "0 6px 18px rgba(0,0,0,0.05)"}),

        html.Div([
            html.Label("Follower Threshold Pair"),
            dcc.Dropdown(
                id="follower-threshold-pairs",
                options=[{"label": label, "value": key} for key, label in FOLLOWER_PROFILE_THRESHOLD_PAIRS.items()],
                value=[],
                multi=True,
                clearable=True,
                placeholder="Optional profile-threshold pair(s)",
            ),
        ], id="follower-threshold-pairs-wrap", style={"display": "none", "marginBottom": "12px", "background": "white", "padding": "16px", "borderRadius": "14px", "boxShadow": "0 6px 18px rgba(0,0,0,0.05)"}),

        html.H3("Customize Plots", style={"marginBottom": "10px"}),
        html.Div([
            html.Div([
                html.Label("View mode"),
                dcc.Dropdown(
                    id="view-mode",
                    options=[
                        {"label": "Independent", "value": "independent"},
                        {"label": "Combined", "value": "combined"},
                        {"label": "Both", "value": "both"},
                    ],
                    value=DEFAULT_VIEW_MODE,
                    clearable=False,
                ),
            ], style={"flex": 1}),
            html.Div([
                html.Label("Sync x-range"),
                dcc.Dropdown(
                    id="sync-x",
                    options=[{"label": "Sync x-range across plots", "value": "sync"}],
                    value=["sync"],
                    multi=True,
                    clearable=True,
                ),
            ], style={"flex": 1}),
        ], style={"display": "flex", "gap": "14px", "marginBottom": "12px", "background": "white", "padding": "16px", "borderRadius": "14px", "boxShadow": "0 6px 18px rgba(0,0,0,0.05)"}),
        html.Div([
            html.Div([
                html.Label("Window preset"),
                dcc.Dropdown(
                    id="window-preset",
                    options=[
                        {"label": "Auto Mode - 2 s to LC Start", "value": "auto_to_lc_start"},
                        {"label": "Auto Mode - 2 s to LC End + 2 s", "value": "auto_to_lc_end_plus_2"},
                        {"label": "LC Start to LC End", "value": "lc_start_to_lc_end"},
                        {"label": "LC End to LC End + 20 s", "value": "lc_end_to_plus_20"},
                        {"label": "Full trial: Auto Mode - 2 s to LC End + 20 s", "value": "full_trial"},
                    ],
                    value="auto_to_lc_end_plus_2",
                    clearable=False,
                ),
            ], style={"minWidth": "300px"}),
            html.Div([html.Label("Global X min (s)"), dcc.Input(id="x-min", type="number", debounce=True, style={"width": "120px"})]),
            html.Div([html.Label("Global X max (s)"), dcc.Input(id="x-max", type="number", debounce=True, style={"width": "120px"})]),
            html.Button("Export visible plots", id="export-btn", n_clicks=0),
            html.Div(id="export-status", style={"fontWeight": "bold"}),
        ], style={"display": "flex", "gap": "14px", "alignItems": "end", "marginBottom": "14px", "background": "white", "padding": "16px", "borderRadius": "14px", "boxShadow": "0 6px 18px rgba(0,0,0,0.05)"}),
        html.Div([
            html.Div([
                html.Label("Visible plot"),
                dcc.Dropdown(id="ylimit-plot-select", options=[], value=None, clearable=False),
            ], style={"flex": 1}),
            html.Div([
                html.Div([
                    html.Label("Y-limit mode"),
                    dcc.Dropdown(
                        id="ylimit-mode",
                        options=[
                            {"label": "Default settings", "value": "default"},
                            {"label": "Saved settings", "value": "saved"},
                        ],
                        value="default",
                        clearable=False,
                    ),
                ], style={"marginBottom": "18px"}),
                html.Div([
                    html.Label("Y-limit"),
                    html.Div([
                        html.Button("Reset all", id="reset-all-ylimits", n_clicks=0),
                        html.Button("Reset current", id="reset-current-ylimit", n_clicks=0, style={"marginLeft": "8px"}),
                        html.Button("Save Slider", id="save-slider-ylimit", n_clicks=0),
                        html.Button("Save Zoom", id="save-zoom-ylimit", n_clicks=0, style={"marginLeft": "8px"}),
                        html.Button("Reset Saved", id="reset-ylimit", n_clicks=0, style={"display": "none"}),
                    ]),
                ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"}),
                dcc.RangeSlider(id="ylimit-slider", min=0, max=1, step=0.1, value=[0, 1], allowCross=False, tooltip={"always_visible": True}),
                html.Div(id="ylimit-slider-label", style={"marginTop": "8px", "color": "#444"}),
            ], style={"flex": 2, "paddingTop": "22px"}),
        ], style={"display": "flex", "gap": "18px", "alignItems": "start", "marginBottom": "16px", "background": "white", "padding": "16px", "borderRadius": "14px", "boxShadow": "0 6px 18px rgba(0,0,0,0.05)"}),

        dcc.Tabs(
            id="main-tabs",
            value="analysis-tab",
            children=[
                dcc.Tab(label="Dashboard", value="analysis-tab"),
                dcc.Tab(label="Additional Analysis", value="lane-end-tab"),
            ],
            style={"marginBottom": "14px"},
        ),
        html.Div(
            id="analysis-tab-wrap",
            children=[
                html.Div(id="combined-wrap"),
                html.Div(id="independent-plots-wrap"),
                html.Div(id="compare-wrap"),
                html.H3("Metrics and Analysis", style={"marginBottom": "10px", "marginTop": "12px", "color": "#990000"}),
                html.Div(id="summary-table-wrap", style={"marginBottom": "18px"}),
            ],
        ),
        html.Div(
            id="lane-end-tab-wrap",
            children=[
                html.H3("Shifted Lateral Analysis", style={"marginBottom": "10px", "marginTop": "12px", "color": "#990000"}),
                dcc.Graph(id="shifted-lateral-analysis-graph", config={"displaylogo": False, "scrollZoom": True}),
            ],
            style={"display": "none"},
        ),
        dcc.Store(id="x-range-store"),
        dcc.Store(id="custom-y-limits-store", data={}),
        dcc.Store(id="popup-plot-key"),
        html.Div(
            id="popup-modal",
            children=[html.Div([
                html.Div([
                    html.H3("Expanded Plot", id="popup-title"),
                    html.Button("Close", id="close-popup", n_clicks=0),
                ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"}),
                dcc.Graph(id="popup-graph", config={"displaylogo": False, "scrollZoom": True}, style={"height": "75vh"}),
            ], style={"background": "white", "padding": "16px", "borderRadius": "12px", "width": "90vw", "height": "85vh"})],
            style={"display": "none", "position": "fixed", "inset": "0", "background": "rgba(0,0,0,0.45)", "zIndex": 9999, "justifyContent": "center", "alignItems": "center"},
        ),
    ], style={"padding": "18px", "background": "linear-gradient(180deg, #fff8f8 0%, #f5f5f5 100%)", "minHeight": "100vh", "maxWidth": "1800px", "margin": "0 auto"})

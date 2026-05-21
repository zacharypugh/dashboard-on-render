import os

APP_TITLE = "Lane Change Data Analysis Dashboard"
BASIC_AUTH_ENABLED = True
BASIC_AUTH_USERNAME = os.getenv("LANE_DASH_USERNAME", "lc_experiments")
BASIC_AUTH_PASSWORD = os.getenv("LANE_DASH_PASSWORD", "visualizeplots")
RUN_MODE = os.getenv("LANE_DASH_RUN_MODE", "local").strip().lower()
LOCAL_PORT = int(os.getenv("LANE_DASH_LOCAL_PORT", "8051"))
SHARE_PORT = int(os.getenv("LANE_DASH_SHARE_PORT", "8050"))
FIGURE_TEMPLATE = "plotly_white"
DEFAULT_HEIGHT = 360
COMBINED_HEIGHT_PER_PLOT = 360
DEFAULT_MA_WINDOW = 21
WINDOW_PRE_EVENT_SEC = 5
WINDOW_POST_EVENT_SEC = 5
OBLIQUE_REFERENCE_SPEED_MPS = 40.0 * 0.44704

# Paths: update these to your machine.
EXPERIMENT_TYPE = "LC"
EXPERIMENT_OPTIONS = ["LC", "FSD"]
BASE_DIR = r"Z:\Abhinav\Research\Lane Changing\Data\NCSU LC Data\Processed Data"


def get_experiment_paths(experiment_type):
    experiment_root = os.path.join(BASE_DIR, f"{experiment_type} Experiments")
    plot_root = os.path.join(experiment_root, "Plots")
    return {
        "experiment_root": experiment_root,
        "merged_folder": os.path.join(experiment_root, "Output Files (With Common Ref)"),
        "plot_root": plot_root,
        "export_folder": os.path.join(plot_root, "Interactive Modular Dashboard"),
        "event_file_path": os.path.join(experiment_root, "Supporting Files", "Filtered Report.xlsx"),
        "verification_event_file_path": os.path.join(experiment_root, "Supporting Files", "Filtered Report_F1_F2_dec_init_manual_verification.xlsx"),
        "lc_smoothed_event_file_path": os.path.join(experiment_root, "Supporting Files", "Filtered Report with Peak Trace Mean1Sec Smoothed LC Times.xlsx"),
        "follower_decel_detection_file_path": (
            r"Z:\Abhinav\Research\Lane Changing\Analysis\Follower Behavior\Slope Regression Braking AutoModeMinus2 to LCCrossPlus10 ManualGreyDotted ThresholdBandText010_015_025\AD-ACC_FilteredReport_SlopeReg1s_Braking_AutoMode_to_LCCrossPlus10.xlsx"
            if str(experiment_type).upper() == "LC"
            else r"Z:\Abhinav\Research\Lane Changing\Analysis\Follower Behavior\Slope Regression Braking AutoModeMinus2 to LCCrossPlus10 ManualGreyDotted ThresholdBandText010_015_025\AD-AD_FilteredReport_SlopeReg1s_Braking_AutoMode_to_LCCrossPlus10.xlsx"
        ),
        "follower_profile_detection_file_path": os.path.join(experiment_root, "Supporting Files", "Filtered Report_FollowerDecelerationDetection_ProfileThresholdMethod.xlsx"),
        "los_event_file_path": os.path.join(experiment_root, "Supporting Files", "Filtered Report_LOSDetection.xlsx"),
        "lc_detection_file_path": os.path.join(experiment_root, "Supporting Files", "Filtered Report_LCStartDetection_SlopeRegressionMethod.xlsx"),
        "lc_direct_detection_file_path": os.path.join(experiment_root, "Supporting Files", "Filtered Report with Peak Trace DirectThreshold LC Times.xlsx"),
        "video_folder": os.path.join(experiment_root, "Videos_all"),
    }


DEFAULT_EXPERIMENT_PATHS = get_experiment_paths(EXPERIMENT_TYPE)
EXPERIMENT_ROOT = DEFAULT_EXPERIMENT_PATHS["experiment_root"]
MERGED_FOLDER = DEFAULT_EXPERIMENT_PATHS["merged_folder"]
PLOT_ROOT = DEFAULT_EXPERIMENT_PATHS["plot_root"]
EXPORT_FOLDER = DEFAULT_EXPERIMENT_PATHS["export_folder"]
EVENT_FILE_PATH = DEFAULT_EXPERIMENT_PATHS["event_file_path"]

# Optional report columns used if present.
REPORT_EVENT_COLUMN_CANDIDATES = {
    "auto_sec": ["Auto Mode Time", "Auto Start Time"],
    "lc_start_sec": ["LC Start Time"],
    "lc_start_band_min_sec": ["LC Start Time Min", "LC Start Min Time", "LC Start Min"],
    "lc_start_band_max_sec": ["LC Time", "LC Max Time", "LC End of Threshold", "LC Start Time Max", "LC Start Max Time", "LC Start Max"],
    "lc_end_sec": ["LC End Time"],
    "lc_end_band_min_sec": ["LC End Time Min", "LC End Min Time", "LC End Min"],
    "lc_end_band_max_sec": ["LC End Max Time", "LC End Time Max", "LC End Max"],
    "fsd_start_sec": ["FSD Start Time"],
    "lc_cross_sec": ["LC Cross Time", "Lane Cross Time"],
    "f1_dec_sec": ["F1 Decel Init", "F1 Decel Ini", "F1 Decel Init Time"],
    "f2_dec_sec": ["F2 Decel Init", "F2 Decel Ini", "F2 Decel Init Time"],
    "los_sec": ["LOS Time", "LOS Detection Time"],
    "site_id": ["Site ID", "Site", "SITE"],
}

LC_DETECTION_METHODS = {
    "slope_regression_method": "Slope Regression Method",
    "direct_threshold_method": "Direct Threshold Method",
}

FOLLOWER_DECEL_METHODS = {
    "slope_regression_method": "Slope Regression Method",
    "profile_threshold_method": "Tienan Speed and Braking Threshold",
}

FOLLOWER_PROFILE_THRESHOLD_PAIRS = {
    "dV0p22_Frac1_5": "dV 0.22 m/s | Frac 1/5",
    "dV0p22_Frac1_4": "dV 0.22 m/s | Frac 1/4",
    "dV0p22_Frac1_3": "dV 0.22 m/s | Frac 1/3",
    "dV0p34_Frac1_5": "dV 0.34 m/s | Frac 1/5",
    "dV0p34_Frac1_4": "dV 0.34 m/s | Frac 1/4",
    "dV0p34_Frac1_3": "dV 0.34 m/s | Frac 1/3",
    "dV0p45_Frac1_5": "dV 0.45 m/s | Frac 1/5",
    "dV0p45_Frac1_4": "dV 0.45 m/s | Frac 1/4",
    "dV0p45_Frac1_3": "dV 0.45 m/s | Frac 1/3",
}

# Horizontal distance only, as requested by user.
# These site values are treated as left-turn lane-end locations.
# Physical lane end is derived as: left_turn_lane_end - offset.
LANE_DROP_END_BY_SITE = {1: 1076.4, 2: 1195.6}
LEFT_TURN_LANE_END_OFFSET_BY_SITE = {1: 70.52, 2: 75.65}

VEHICLE_MAP = {"Lead": "A", "LC": "X", "F1": "B", "F2": "C"}
ALIAS_TO_VEHICLE = {v: k for k, v in VEHICLE_MAP.items()}
VEHICLE_COLORS = {
    "Lead": "orange",
    "LC": "red",
    "F1": "blue",
    "F2": "green",
}

PAIR_COLORS = {
    "AB": "#e9c716",
    "BC": "#50ad9f",
    "TL_X": "#7a3db8",
    "X_TF": "#e377c2",
    "X_TARGET_LEADER": "#7a3db8",
    "TARGET_FOLLOWER_X": "#e377c2",
    "BA": "#e9c716",
    "CB": "#50ad9f",
    "X_LANE_DROP_END": "#7f7f7f",
    "X_LEFT_TURN_LANE_END": "#bcbd22",
}

PAIR_DISPLAY_LABELS = {
    "AB": "AB",
    "BC": "BC",
    "TL_X": "TL-X",
    "X_TF": "X-TF",
    "X_TARGET_LEADER": "X-TL",
    "TARGET_FOLLOWER_X": "X-TF-X",
    "BA": "BA",
    "CB": "CB",
    "X_LANE_DROP_END": "X-RTLE",
    "X_LEFT_TURN_LANE_END": "X-LE",
}

PAIR_LINE_DASHES = {
    "TL_X": "dash",
    "X_TF": "dash",
}

EVENT_LINE_STYLES = {
    "auto_sec": {"label": "Auto Mode Time", "color": "red", "dash": "dash"},
    "lc_start_sec": {"label": "LC Start", "color": "blue", "dash": "dash"},
    "lc_end_sec": {"label": "LC End", "color": "blue", "dash": "dash"},
    "fsd_start_sec": {"label": "FSD Start", "color": "purple", "dash": "dot"},
    "lc_cross_sec": {"label": "LC Cross", "color": "teal", "dash": "dot"},
    "f1_dec_sec": {"label": "F1 dec", "color": "navy", "dash": "dot"},
    "f2_dec_sec": {"label": "F2 dec", "color": "darkgreen", "dash": "dot"},
    "los_sec": {"label": "LOS Time", "color": "black", "dash": "dot"},
}

YLIMS = {
    "longitudinal_position": (-50, 50),
    "longitudinal_speed": (14, 20),
    "longitudinal_acceleration": None,
    "longitudinal_headway": None,
    "longitudinal_tau": None,
    "longitudinal_spacing": (0, 40),
    "lane_end_distance": None,
    "lateral_position": (0, 5),
    "lateral_speed": (-2, 0.5),
    "lateral_acceleration": (-1, 1),
    "ttc": (0, 10),
    "drac": (0, 8),
    "essm": (-20, 20),
}

SAFETY_PARAMS = {
    "reaction_time": 0.5,
    "braking_deceleration": 0.8 * 9.81,
    "vehicle_length": 5.0,
    "vehicle_buffer": 2.0,
    "ttc_warning": 3.0,
    "ttc_critical": 1.5,
    "drac_warning": 2.5,
    "drac_critical": 4.0,
    "essm_warning": 0.0,
    "essm_critical": -5.0,
}

PLOT_GROUPS = {
    "longitudinal": [
        "longitudinal_position",
        "longitudinal_speed",
        "longitudinal_acceleration",
        "longitudinal_headway",
        "longitudinal_tau",
        "longitudinal_spacing",
        "lane_end_distance",
    ],
    "lateral": [
        "lateral_position",
        "lateral_speed",
        "lateral_acceleration",
    ],
    "safety": [
        "ttc",
        "drac",
        "essm",
    ],
}

DEFAULT_ENABLED_GROUPS = ["longitudinal", "lateral", "safety"]
DEFAULT_VISIBLE_EVENT_LINES = ["auto_sec", "lc_start_sec", "lc_end_sec", "lc_cross_sec", "f1_dec_sec", "f2_dec_sec"]
DEFAULT_LONGITUDINAL_PAIRS = ["AB", "BC", "TL_X", "X_TF"]
DEFAULT_SAFETY_PAIRS = [
    "X_TARGET_LEADER",
    "TARGET_FOLLOWER_X",
    "BA",
    "CB",
    "X_LANE_DROP_END",
    "X_LEFT_TURN_LANE_END",
]
DEFAULT_VIEW_MODE = "combined"

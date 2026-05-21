from models import PlotSpec

from config import YLIMS, OBLIQUE_REFERENCE_SPEED_MPS



PLOT_SPECS = {

    "longitudinal_position": PlotSpec("longitudinal_position", "Oblique Position", f"Oblique Position - Ref {OBLIQUE_REFERENCE_SPEED_MPS:.2f} m/s (m)", "longitudinal", "vehicle", YLIMS["longitudinal_position"]),

    "longitudinal_speed": PlotSpec("longitudinal_speed", "Longitudinal Speed", "Speed (m/s)", "longitudinal", "vehicle", YLIMS["longitudinal_speed"]),

    "longitudinal_acceleration": PlotSpec("longitudinal_acceleration", "Longitudinal Acceleration", "Longitudinal Acceleration (m/s^2)", "longitudinal", "vehicle", YLIMS["longitudinal_acceleration"]),

    "longitudinal_headway": PlotSpec("longitudinal_headway", "Longitudinal Headway", "Headway (s)", "longitudinal", "pair", YLIMS["longitudinal_headway"]),

    "longitudinal_tau": PlotSpec("longitudinal_tau", "Tau", "tau (s)", "longitudinal", "pair", YLIMS["longitudinal_tau"]),

    "longitudinal_spacing": PlotSpec("longitudinal_spacing", "Longitudinal Spacing", "Spacing (m)", "longitudinal", "pair", YLIMS["longitudinal_spacing"]),

    "lane_end_distance": PlotSpec("lane_end_distance", "Distance to Lane End", "Distance (m)", "longitudinal", "vehicle", YLIMS["lane_end_distance"]),

    "lateral_position": PlotSpec("lateral_position", "Lateral Position", "Lateral Position (m)", "lateral", "vehicle", YLIMS["lateral_position"]),

    "lateral_speed": PlotSpec("lateral_speed", "Lateral Speed", "Lateral Speed (m/s)", "lateral", "vehicle", YLIMS["lateral_speed"]),

    "lateral_acceleration": PlotSpec("lateral_acceleration", "Lateral Acceleration", "Lateral Acceleration (m/sÂ²)", "lateral", "vehicle", YLIMS["lateral_acceleration"]),

    "ttc": PlotSpec("ttc", "Time to Collision (TTC)", "TTC (s)", "safety", "safety", YLIMS["ttc"]),

    "drac": PlotSpec("drac", "Deceleration Rate to Avoid Crash (DRAC)", "DRAC (m/sÂ²)", "safety", "safety", YLIMS["drac"]),

    "essm": PlotSpec("essm", "Emergency Surrogate Safety Measure (ESSM)", "ESSM (m)", "safety", "safety", YLIMS["essm"]),

}


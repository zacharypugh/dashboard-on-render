import os
from plots.builders import build_combined_figure, build_single_plot_figure


def export_trial_pngs(trial, out_dir, visible_plots, enabled_longitudinal_pairs, enabled_safety_pairs, x_range=None, visible_event_keys=None, custom_y_limits=None, lc_detection_methods=None, lc_detection_events=None, follower_decel_methods=None, follower_threshold_pairs=None):
    case_out_dir = os.path.join(out_dir, trial.case_name)
    os.makedirs(case_out_dir, exist_ok=True)
    combined_path = os.path.join(case_out_dir, f"{trial.case_name}_combined.png")
    build_combined_figure(
        trial,
        visible_plots,
        enabled_longitudinal_pairs=enabled_longitudinal_pairs,
        enabled_safety_pairs=enabled_safety_pairs,
        x_range=x_range,
        visible_event_keys=visible_event_keys,
        custom_y_limits=custom_y_limits,
        lc_detection_methods=lc_detection_methods,
        lc_detection_events=lc_detection_events,
        follower_decel_methods=follower_decel_methods,
        follower_threshold_pairs=follower_threshold_pairs,
    ).write_image(combined_path)

    individual_paths = []
    for plot_key in visible_plots:
        fp = os.path.join(case_out_dir, f"{trial.case_name}_{plot_key}.png")
        build_single_plot_figure(
            trial,
            plot_key,
            enabled_longitudinal_pairs=enabled_longitudinal_pairs,
            enabled_safety_pairs=enabled_safety_pairs,
            x_range=x_range,
            visible_event_keys=visible_event_keys,
            custom_y_limits=custom_y_limits,
            lc_detection_methods=lc_detection_methods,
            follower_decel_methods=follower_decel_methods,
            follower_threshold_pairs=follower_threshold_pairs,
        ).write_image(fp)
        individual_paths.append(fp)
    return combined_path, individual_paths

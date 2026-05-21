# Lane Change Data Analysis Dashboard

Dash-based dashboard for reviewing lane-change and FSD experiment cases, comparing safety metrics, visualizing event timing, opening linked videos, and exporting figures.

## What the dashboard does

- Loads cases from both `LC Experiments` and `FSD Experiments`
- Filters available primary cases by:
  - experiment
  - site
  - configuration
  - gap
  - DS
  - DV
- Supports side-by-side comparison with separate compare-case criteria:
  - compare experiment
  - compare site
  - compare configuration
  - compare gap
  - compare DS
  - compare DV
- Uses a multi-tab layout
- Shows combined plots and individual plots on the main dashboard tab
- Exports the currently visible plots to PNG files in a case-named subfolder

## Tabs

### Dashboard tab

The first tab contains the main dashboard workflow:

- file selection
- filters
- compare mode
- plot customization
- combined plots
- independent plots
- metrics and analysis

### Lane End Distance tab

The second tab shows distance from vehicle `X` to lane-end references for the currently selected primary case:

- `Physical Lane End`
- `Left Turn Lane End`

This tab also uses the same vertical markers as the main dashboard:

- standard event lines
- LC detection bands
- follower deceleration detection bands

## Main plot groups

- Longitudinal
  - Oblique Position
  - Longitudinal Speed
  - Longitudinal Acceleration
  - Longitudinal Headway
  - Longitudinal Spacing
- Lateral
  - Lateral Position
  - Lateral Speed
  - Lateral Acceleration
- Safety
  - TTC
  - DRAC
  - ESSM

## Current signal definitions

- Oblique Position uses raw `LongDist_LeftLane_m (Common Reference)` referenced to a 40 mph moving frame
- Longitudinal Speed uses raw `Speed_mps` smoothed with a centered 21-sample moving average
- Longitudinal Acceleration is computed from raw speed using `diff(speed) / dt`, then smoothed with the same centered 21-sample moving average
- Lateral Position uses smoothed `LatDist_LeftLane_m`
- Lateral Speed is computed from lateral position and then smoothed
- Lateral Acceleration is computed from raw lateral-speed estimates and then smoothed
- Longitudinal Headway uses tau notation:
  - `tau = (spacing - 7.0) / follower_speed`

## Safety metrics

- TTC uses effective spacing:
  - `effective_spacing = spacing - vehicle_length`
  - `TTC = effective_spacing / closing_speed`
  - only when `effective_spacing > 0` and `closing_speed > 0`
- DRAC uses effective spacing:
  - `DRAC = closing_speed^2 / (2 * effective_spacing)`
  - only when `effective_spacing > 0` and `closing_speed > 0`
- ESSM uses:
  - reaction time = `1.0 s`
  - braking deceleration = `(1/3) g = 3.27 m/s^2`
  - vehicle length = `5.0 m`
  - vehicle buffer = `2.0 m`
  - `ESSM = spacing - safe_distance - vehicle_length - vehicle_buffer`

## Event lines and detection bands

### Standard event lines

These come from the main/supporting report files and are controlled by `Event lines`:

- Auto Mode Time
- LC Start
- LC End
- LC Cross
- F1 dec
- F2 dec
- LOS Time

### Detection bands

These are separate from event lines.

- `LC Detection Method`
  - supports slope-regression LC detection bands
- `LC Detection Band`
  - lets you show LC Start, LC End, or both slope-regression bands
- `Follower Deceleration Detection Method`
  - supports:
    - follower slope regression (`SRF`)
    - Tienan speed and braking threshold (`TSB`)
- `Follower Threshold Pair`
  - only appears when `TSB` is selected

Band labels currently use compact method tags:

- `SRLC` for LC slope regression
- `SRF` for follower slope regression
- `TSB` for Tienan speed and braking threshold

## Combined-view legends

The combined view uses separate Plotly legends for each subplot row so traces can be toggled within each figure independently.

## Window presets

The dashboard includes preset time windows such as:

- Auto Mode - 2 s to LC Start
- LC Start to LC End
- LC End to LC End + 20 s
- Auto Mode - 2 s to LC End + 2 s
- Full trial: Auto Mode - 2 s to LC End + 20 s

## Y-limit controls

`Customize Plots` includes per-plot y-limit controls with:

- Default settings
- Saved settings
- Save Slider
- Save Zoom
- Reset current
- Reset all

## Video links

The dashboard can generate `Open Video` links for the selected primary and compare cases when matching videos exist in the experiment `Videos_all` folder.

## Run

Install dependencies in the Python environment used for the app:

```powershell
python -m pip install dash plotly pandas numpy openpyxl pytz waitress kaleido
```

## Local mode

Use this while developing. It runs with Dash auto-reload.

```powershell
$env:LANE_DASH_RUN_MODE="local"
python app.py
```

Default local URL:

```text
http://127.0.0.1:8051
```

## Share mode

Use this when sharing on your internal network. It runs with `waitress`.

```powershell
$env:LANE_DASH_RUN_MODE="share"
python app.py
```

Default shared URLs:

```text
http://127.0.0.1:8050
http://YOUR-IP:8050
```

Optional port overrides:

```powershell
$env:LANE_DASH_LOCAL_PORT="8051"
$env:LANE_DASH_SHARE_PORT="8050"
```

## Notes

- In share mode, code changes require restarting the app.
- In local mode, Dash auto-reload is available for development.
- PNG export depends on `kaleido` being installed in the same Python environment.

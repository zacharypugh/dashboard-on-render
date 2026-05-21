# Changelog

## 2026-04-29

### Added

- Multi-tab dashboard layout
- New `Lane End Distance` tab for the selected primary case
- Lane-end time plot for vehicle `X` showing:
  - Physical Lane End
  - Left Turn Lane End
- Shared vertical-marker support on the lane-end tab using:
  - standard event lines
  - LC detection bands
  - follower deceleration detection bands

### Documentation

- Updated README to describe the multi-tab layout and lane-end tab
- Updated changelog with the new tabbed dashboard behavior

## 2026-04-28

### Added

- Side-by-side comparison mode with separate compare experiment and compare case selection
- Separate compare-side filtering criteria for:
  - compare site
  - compare configuration
  - compare gap
  - compare DS
  - compare DV
- Combined and individual plot support for:
  - Oblique Position
  - Longitudinal Speed
  - Longitudinal Acceleration
  - Longitudinal Headway
  - Longitudinal Spacing
  - Lateral Position
  - Lateral Speed
  - Lateral Acceleration
  - TTC
  - DRAC
  - ESSM
- PNG export for visible plots into a case-specific subfolder
- Video links for primary and compare cases
- Experiment-aware loading for both `LC Experiments` and `FSD Experiments`
- Case filters for site, configuration, gap, DS, and DV
- Per-plot y-limit customization with save/reset behavior
- Local and share run modes
- Basic password protection support for shared access
- Slope-regression LC detection bands
- Follower-deceleration slope-regression bands
- Tienan speed and braking threshold follower-detection bands
- LOS time support from the LOS detection workbook
- Per-subplot legends in combined view

### Changed

- Replaced FSD Start event usage with Auto Mode Time where requested
- Moved to a modular dashboard structure with clearer sections:
  - Select Files
  - Filters
  - Customize Plots
  - Metrics and Analysis
- Reworked combined-view legends and per-figure legend behavior
- Updated longitudinal color palette and pair colors, including purple for `X-TL`
- Removed fixed `XC` spacing from the active UI
- Updated safety summary windows to use lane-change event windows
- Updated TTC and DRAC to use spacing minus vehicle length
- Updated ESSM to use:
  - braking deceleration = one-third of `g`
  - vehicle length = `5.0 m`
  - vehicle buffer = `2.0 m`
- Updated longitudinal speed plotting to use smoothed raw speed
- Updated longitudinal acceleration plotting to use acceleration from raw speed, then smoothing
- Updated longitudinal headway to use tau notation:
  - `tau = (spacing - 7.0) / follower_speed`
- Updated compare filter labels to show:
  - `DV = 0 (equal), 1 (lower), 2 (higher)`
  - `DS = 2 (Tail)`

### Detection and event updates

- Standard event lines remain separate from detection bands
- `LC Detection Band` can show LC Start, LC End, or both
- `Follower Threshold Pair` is only shown when the Tienan threshold method is enabled
- Detection band annotations use compact method tags:
  - `SRLC`
  - `SRF`
  - `TSB`
- Detection band colors were updated for clearer distinction:
  - blue for `SRLC`
  - reddish for `SRF`
  - greenish for `TSB`

### Documentation

- Refreshed README to match the current dashboard behavior
- Updated the changelog to include the latest metric, legend, and compare-filter changes

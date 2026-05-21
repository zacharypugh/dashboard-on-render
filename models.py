from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd


@dataclass
class TrialData:
    timestamps: np.ndarray
    vehicle_traces: Dict[str, Dict[str, pd.Series]]
    event_times: Dict[str, Optional[float]]
    case_name: str
    label: str
    site_id: Optional[int] = None
    raw_report_row: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlotSpec:
    key: str
    title: str
    y_label: str
    group: str
    builder_type: str
    y_limits: Optional[List[float]] = None

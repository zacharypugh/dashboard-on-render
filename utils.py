import os
import re
import numpy as np
import pandas as pd


def safe_stem(path_or_label: str) -> str:
    stem = os.path.splitext(os.path.basename(path_or_label))[0]
    return re.sub(r"[^\w\-_. ]", "_", stem)


def smooth_ma(x, win=21):
    return pd.Series(x).rolling(win, center=True, min_periods=1).mean().values


def safe_divide(numerator, denominator, fill_value=np.nan):
    numerator = np.asarray(numerator, dtype=float)
    denominator = np.asarray(denominator, dtype=float)
    numerator, denominator = np.broadcast_arrays(numerator, denominator)
    out = np.full(numerator.shape, fill_value, dtype=float)
    mask = np.isfinite(numerator) & np.isfinite(denominator) & (np.abs(denominator) > 1e-9)
    out[mask] = numerator[mask] / denominator[mask]
    return out


def clamp_range(x0, x1, xmin, xmax):
    return max(x0, xmin), min(x1, xmax)

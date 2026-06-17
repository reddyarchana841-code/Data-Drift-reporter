"""
drift_engine.py

Core statistics and drift-detection logic.

Responsibilities:
- compute_snapshot_stats(df): compute per-column + overall statistics for a dataframe
- compare_snapshots(current_stats, previous_stats): compute drift metrics between
  two snapshots and an overall drift score
- classify_drift(score): map a numeric drift score to Low / Medium / High
"""

import numpy as np
import pandas as pd


def compute_snapshot_stats(df: pd.DataFrame) -> dict:
    """
    Compute summary statistics for a dataframe.

    Returns a dict with:
        row_count: int
        overall_null_rate: float (% of all cells that are null)
        overall_mean: float (average of per-column means for numeric cols)
        columns: { col_name: { dtype, null_pct, mean, median, min, max, std, unique_count } }
    """
    row_count = len(df)
    columns_stats = {}

    total_cells = row_count * len(df.columns) if row_count and len(df.columns) else 0
    total_nulls = int(df.isnull().sum().sum()) if total_cells else 0
    overall_null_rate = round((total_nulls / total_cells) * 100, 4) if total_cells else 0.0

    numeric_means = []

    for col in df.columns:
        series = df[col]
        null_count = int(series.isnull().sum())
        null_pct = round((null_count / row_count) * 100, 4) if row_count else 0.0
        unique_count = int(series.nunique(dropna=True))

        col_stat = {
            "dtype": str(series.dtype),
            "null_pct": null_pct,
            "unique_count": unique_count,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "std": None,
        }

        if pd.api.types.is_numeric_dtype(series):
            numeric_series = series.dropna()
            if len(numeric_series) > 0:
                col_stat["mean"] = float(numeric_series.mean())
                col_stat["median"] = float(numeric_series.median())
                col_stat["min"] = float(numeric_series.min())
                col_stat["max"] = float(numeric_series.max())
                col_stat["std"] = float(numeric_series.std()) if len(numeric_series) > 1 else 0.0
                numeric_means.append(col_stat["mean"])
        else:
            # For categorical/text columns, record min/max length as a lightweight signal
            non_null = series.dropna().astype(str)
            if len(non_null) > 0:
                lengths = non_null.str.len()
                col_stat["min"] = float(lengths.min())
                col_stat["max"] = float(lengths.max())
                col_stat["mean"] = float(lengths.mean())

        columns_stats[col] = col_stat

    overall_mean = float(np.mean(numeric_means)) if numeric_means else 0.0

    return {
        "row_count": row_count,
        "overall_null_rate": overall_null_rate,
        "overall_mean": round(overall_mean, 4),
        "columns": columns_stats,
    }


def _safe_pct_change(old, new):
    """Return absolute percent change between old and new. Handles old == 0."""
    if old is None or new is None:
        return 0.0
    if old == 0:
        return 100.0 if new != 0 else 0.0
    return abs((new - old) / old) * 100.0


def compare_snapshots(current_stats: dict, previous_stats: dict) -> dict:
    """
    Compare two snapshot stats dicts (output of compute_snapshot_stats) and produce
    a drift report dict:

    {
        "drift_score": float (0-100, overall severity),
        "drift_level": "Low" | "Medium" | "High",
        "row_count_change_pct": float,
        "null_rate_change_pct": float,
        "mean_change_pct": float,
        "column_changes": { col: { null_pct_change, mean_change_pct, ... } },
        "events": [ list of human-readable change descriptions for narrator ]
    }
    """
    events = []

    row_change_pct = _safe_pct_change(previous_stats["row_count"], current_stats["row_count"])
    null_change_pct = _safe_pct_change(
        previous_stats["overall_null_rate"], current_stats["overall_null_rate"]
    )
    mean_change_pct = _safe_pct_change(
        previous_stats["overall_mean"], current_stats["overall_mean"]
    )

    if previous_stats["row_count"] != current_stats["row_count"]:
        direction = "increased" if current_stats["row_count"] > previous_stats["row_count"] else "decreased"
        events.append(
            f"Row count {direction} from {previous_stats['row_count']} to "
            f"{current_stats['row_count']} ({row_change_pct:.1f}% change)."
        )

    if abs(current_stats["overall_null_rate"] - previous_stats["overall_null_rate"]) > 0.01:
        direction = "increased" if current_stats["overall_null_rate"] > previous_stats["overall_null_rate"] else "decreased"
        events.append(
            f"Overall null rate {direction} from {previous_stats['overall_null_rate']:.2f}% "
            f"to {current_stats['overall_null_rate']:.2f}%."
        )

    # Per-column comparisons
    column_changes = {}
    column_drift_scores = []

    common_cols = set(current_stats["columns"].keys()) & set(previous_stats["columns"].keys())

    for col in common_cols:
        cur = current_stats["columns"][col]
        prev = previous_stats["columns"][col]

        null_change = round(cur["null_pct"] - prev["null_pct"], 4)
        mean_chg_pct = _safe_pct_change(prev.get("mean"), cur.get("mean"))

        column_changes[col] = {
            "null_pct_previous": prev["null_pct"],
            "null_pct_current": cur["null_pct"],
            "null_pct_change": null_change,
            "mean_previous": prev.get("mean"),
            "mean_current": cur.get("mean"),
            "mean_change_pct": round(mean_chg_pct, 2),
        }

        # Track this column's drift contribution (max of null-rate jump and mean shift)
        col_drift = max(abs(null_change), mean_chg_pct)
        column_drift_scores.append(col_drift)

        # Generate narration-worthy events for significant column-level changes
        if abs(null_change) >= 1.0:
            direction = "increased" if null_change > 0 else "decreased"
            events.append(
                f"'{col}' null rate {direction} from {prev['null_pct']:.2f}% "
                f"to {cur['null_pct']:.2f}%."
            )

        if mean_chg_pct >= 5.0 and prev.get("mean") is not None:
            direction = "increased" if cur["mean"] > prev["mean"] else "decreased"
            events.append(
                f"Average '{col}' {direction} by {mean_chg_pct:.1f}% "
                f"(from {prev['mean']:.2f} to {cur['mean']:.2f})."
            )

    # Overall drift score: weighted combination of row/null/mean changes and
    # the strongest per-column drift signal.
    base_components = [row_change_pct, null_change_pct, mean_change_pct]
    if column_drift_scores:
        base_components.append(max(column_drift_scores))

    drift_score = round(float(np.mean(base_components)), 2)
    drift_level = classify_drift(drift_score)

    if not events:
        events.append("No significant changes detected compared to the previous snapshot.")

    return {
        "drift_score": drift_score,
        "drift_level": drift_level,
        "row_count_change_pct": round(row_change_pct, 2),
        "null_rate_change_pct": round(null_change_pct, 2),
        "mean_change_pct": round(mean_change_pct, 2),
        "column_changes": column_changes,
        "events": events,
    }


def classify_drift(score: float) -> str:
    """Classify a numeric drift score into Low / Medium / High."""
    if score < 5:
        return "Low"
    elif score <= 15:
        return "Medium"
    else:
        return "High"

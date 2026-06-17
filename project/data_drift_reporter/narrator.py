"""
narrator.py

AI Narration Module.

Generates business-analyst-style natural language summaries from drift
comparison data (output of drift_engine.compare_snapshots).

Two modes:
1. LLM mode (if ANTHROPIC_API_KEY is set in the environment) - sends the
   structured drift events to Claude and asks for a polished business
   narrative.
2. Template mode (default / fallback) - builds a well-formatted narrative
   directly from the structured events using rule-based templates. This
   requires no API key and produces output in the same style as the
   examples in the project spec.
"""

import os


def generate_narration(dataset_name: str, drift_result: dict, current_stats: dict) -> str:
    """
    Generate a business-friendly narrative summary for a drift report.

    Args:
        dataset_name: human-readable dataset name
        drift_result: output of drift_engine.compare_snapshots
        current_stats: output of drift_engine.compute_snapshot_stats (current snapshot)

    Returns:
        A multi-paragraph string suitable for display / PDF export.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if api_key:
        try:
            return _generate_with_llm(dataset_name, drift_result, current_stats, api_key)
        except Exception as exc:  # noqa: BLE001 - fall back gracefully
            # If the LLM call fails for any reason (no network, bad key, etc.)
            # fall back to the deterministic template-based narration so the
            # app keeps working offline.
            fallback = _generate_with_template(dataset_name, drift_result, current_stats)
            return fallback + f"\n\n(Note: AI narration service unavailable, used built-in summary. Details: {exc})"

    return _generate_with_template(dataset_name, drift_result, current_stats)


def _generate_with_llm(dataset_name: str, drift_result: dict, current_stats: dict, api_key: str) -> str:
    """Use Anthropic's API to generate a polished narrative from the drift data."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    prompt = (
        f"You are a senior business data analyst. Write a concise, professional "
        f"data quality / drift report for the dataset '{dataset_name}'.\n\n"
        f"Drift level: {drift_result['drift_level']} (score: {drift_result['drift_score']})\n"
        f"Row count change: {drift_result['row_count_change_pct']}%\n"
        f"Overall null rate change: {drift_result['null_rate_change_pct']}%\n"
        f"Overall mean change: {drift_result['mean_change_pct']}%\n\n"
        f"Key observations:\n"
        + "\n".join(f"- {e}" for e in drift_result["events"])
        + "\n\n"
        f"Write 3-5 short sentences in plain business language, like an analyst "
        f"summarizing this week's data health to a non-technical stakeholder. "
        f"Mention specific numbers. End with a one-sentence recommendation if drift "
        f"is Medium or High."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )

    return "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    ).strip()


def _generate_with_template(dataset_name: str, drift_result: dict, current_stats: dict) -> str:
    """
    Build a business-analyst-style report using rule-based templates.
    No external dependencies required - works fully offline.
    """
    level = drift_result["drift_level"]
    score = drift_result["drift_score"]

    lines = []

    # Opening summary line
    lines.append(
        f"Data Quality Report for '{dataset_name}': overall drift level is "
        f"{level} (drift score: {score:.1f}%)."
    )

    # Row count narrative
    rc_change = drift_result["row_count_change_pct"]
    if rc_change > 0.01:
        direction = "increased" if "increased" in " ".join(drift_result["events"]).lower() else "changed"
        lines.append(
            f"Row count changed by {rc_change:.1f}% compared to the previous snapshot, "
            f"now totaling {current_stats['row_count']:,} records."
        )

    # Null rate narrative
    null_change = drift_result["null_rate_change_pct"]
    if null_change > 0.01:
        lines.append(
            f"The overall null rate shifted by {null_change:.1f}%, now sitting at "
            f"{current_stats['overall_null_rate']:.2f}% of all values."
        )

    # Mean / distribution narrative
    mean_change = drift_result["mean_change_pct"]
    if mean_change > 0.01:
        lines.append(
            f"Average values across numeric fields shifted by {mean_change:.1f}% "
            f"week-over-week, indicating a potential change in underlying business activity."
        )

    # Detailed events (skip the generic "no significant changes" placeholder if other text exists)
    detail_events = [e for e in drift_result["events"] if "No significant changes" not in e]
    if detail_events:
        lines.append("Key observations:")
        for e in detail_events[:6]:  # cap to keep the report readable
            lines.append(f"  • {e}")

    if not detail_events and len(lines) == 1:
        lines.append(
            "No significant changes were detected compared to the previous snapshot. "
            "Data volume, null rates, and value distributions remain stable."
        )

    # Recommendation
    if level == "High":
        lines.append(
            "Recommendation: This dataset shows high drift and should be reviewed by "
            "the data engineering team to confirm whether the change reflects a real "
            "business shift or an upstream data issue."
        )
    elif level == "Medium":
        lines.append(
            "Recommendation: Monitor this dataset closely over the next few snapshots "
            "to confirm whether this trend continues."
        )
    else:
        lines.append("Recommendation: No action required at this time.")

    return "\n".join(lines)

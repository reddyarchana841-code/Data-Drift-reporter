"""
report_generator.py

Generates downloadable PDF drift reports and CSV snapshot reports.
Uses fpdf2 (pure-python, no system dependencies) for PDF generation.
"""

import csv
import os
from datetime import datetime

from fpdf import FPDF


def generate_pdf_report(dataset, latest_snapshot, latest_report, reports_folder) -> str:
    """
    Create a PDF drift report for a dataset and return its filepath.
    """
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "Data Drift Reporter", ln=True)

    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f"Dataset: {dataset.dataset_name}", ln=True)
    pdf.cell(0, 8, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Latest Snapshot Summary", ln=True)
    pdf.set_font("Helvetica", "", 11)

    if latest_snapshot:
        pdf.cell(0, 7, f"Snapshot Date: {latest_snapshot.snapshot_date.strftime('%Y-%m-%d %H:%M UTC')}", ln=True)
        pdf.cell(0, 7, f"Row Count: {latest_snapshot.row_count}", ln=True)
        pdf.cell(0, 7, f"Overall Null Rate: {latest_snapshot.null_rate:.2f}%", ln=True)
        pdf.cell(0, 7, f"Overall Mean (numeric cols avg): {latest_snapshot.mean_value:.2f}", ln=True)
        pdf.cell(0, 7, f"Drift Score: {latest_snapshot.drift_score:.2f}%", ln=True)
    else:
        pdf.cell(0, 7, "No snapshots available.", ln=True)

    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "AI-Generated Drift Narrative", ln=True)
    pdf.set_font("Helvetica", "", 11)

    if latest_report and latest_report.report_text:
        pdf.cell(0, 7, f"Drift Level: {latest_report.drift_level}", ln=True)
        pdf.ln(2)
        for line in latest_report.report_text.split("\n"):
            pdf.multi_cell(0, 6, line)
    else:
        pdf.multi_cell(
            0,
            6,
            "No drift report available yet. A drift report is generated once at "
            "least two snapshots exist for this dataset.",
        )

    filename = f"drift_report_{dataset.id}_{int(datetime.utcnow().timestamp())}.pdf"
    filepath = os.path.join(reports_folder, filename)
    pdf.output(filepath)
    return filepath


def generate_csv_report(dataset, snapshots, reports_folder) -> str:
    """
    Create a CSV export of all snapshots for a dataset and return its filepath.
    """
    filename = f"snapshot_report_{dataset.id}_{int(datetime.utcnow().timestamp())}.csv"
    filepath = os.path.join(reports_folder, filename)

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["snapshot_date", "row_count", "null_rate", "mean_value", "drift_score"]
        )
        for s in snapshots:
            writer.writerow(
                [
                    s.snapshot_date.strftime("%Y-%m-%d %H:%M:%S"),
                    s.row_count,
                    s.null_rate,
                    s.mean_value,
                    s.drift_score,
                ]
            )

    return filepath

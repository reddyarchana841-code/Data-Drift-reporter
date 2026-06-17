"""
app.py

Data Drift Reporter - Flask application entry point.

Run with:
    python app.py

This starts a local server on http://127.0.0.1:5000
"""

import json
import os
from datetime import datetime

import pandas as pd
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.utils import secure_filename

from drift_engine import compare_snapshots, compute_snapshot_stats
from models import Dataset, DriftReport, Snapshot, db
from narrator import generate_narration
from report_generator import generate_csv_report, generate_pdf_report

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
REPORTS_FOLDER = os.path.join(BASE_DIR, "reports")
ALLOWED_EXTENSIONS = {"csv"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORTS_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'database.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["REPORTS_FOLDER"] = REPORTS_FOLDER
app.config["SECRET_KEY"] = "dev-secret-key-change-in-production"
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB upload limit

db.init_app(app)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def dataset_csv_path(dataset: Dataset) -> str:
    return os.path.join(app.config["UPLOAD_FOLDER"], dataset.filename)


# ---------------------------------------------------------------------------
# Core: snapshot generation & drift detection
# ---------------------------------------------------------------------------

def create_snapshot_for_dataset(dataset: Dataset) -> Snapshot:
    """
    Read the dataset's CSV, compute current statistics, compare with the most
    recent previous snapshot (if any), persist the new snapshot, and (if a
    previous snapshot exists) generate a DriftReport with AI narration.
    """
    df = pd.read_csv(dataset_csv_path(dataset))
    current_stats = compute_snapshot_stats(df)

    # Update dataset row count / schema for convenience
    dataset.row_count = current_stats["row_count"]
    dataset.columns_json = json.dumps(list(df.columns))

    previous_snapshot = (
        Snapshot.query.filter_by(dataset_id=dataset.id)
        .order_by(Snapshot.snapshot_date.desc())
        .first()
    )

    drift_score = 0.0
    if previous_snapshot and previous_snapshot.stats_json:
        previous_stats = json.loads(previous_snapshot.stats_json)
        drift_result = compare_snapshots(current_stats, previous_stats)
        drift_score = drift_result["drift_score"]

        narration_text = generate_narration(dataset.dataset_name, drift_result, current_stats)

        report = DriftReport(
            dataset_id=dataset.id,
            report_text=narration_text,
            drift_level=drift_result["drift_level"],
            drift_score=drift_result["drift_score"],
            created_at=datetime.utcnow(),
        )
        db.session.add(report)

    snapshot = Snapshot(
        dataset_id=dataset.id,
        snapshot_date=datetime.utcnow(),
        row_count=current_stats["row_count"],
        null_rate=current_stats["overall_null_rate"],
        mean_value=current_stats["overall_mean"],
        drift_score=drift_score,
        stats_json=json.dumps(current_stats),
    )
    db.session.add(snapshot)
    db.session.commit()

    return snapshot


# ---------------------------------------------------------------------------
# Page routes (HTML)
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("dashboard.html", active_page="dashboard")


@app.route("/upload-page")
def upload_page():
    return render_template("upload.html", active_page="upload")


@app.route("/datasets-page")
def datasets_page():
    return render_template("datasets.html", active_page="datasets")


@app.route("/dataset/<int:dataset_id>")
def dataset_detail(dataset_id):
    dataset = Dataset.query.get_or_404(dataset_id)
    return render_template("dataset_detail.html", dataset=dataset, active_page="datasets")


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.route("/upload", methods=["POST"])
def upload():
    """
    Upload a CSV dataset. Validates that the file is a CSV with at least
    one column, saves it, creates a Dataset record, and generates the
    first snapshot.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file part in request."}), 400

    file = request.files["file"]
    dataset_name = request.form.get("dataset_name", "").strip()

    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Only .csv files are supported."}), 400

    filename = secure_filename(file.filename)
    # Prefix with timestamp to avoid collisions
    stored_filename = f"{int(datetime.utcnow().timestamp())}_{filename}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], stored_filename)
    file.save(filepath)

    # Schema validation
    try:
        df = pd.read_csv(filepath)
    except Exception as exc:  # noqa: BLE001
        os.remove(filepath)
        return jsonify({"error": f"Could not parse CSV: {exc}"}), 400

    if len(df.columns) == 0:
        os.remove(filepath)
        return jsonify({"error": "CSV file has no columns."}), 400

    if not dataset_name:
        dataset_name = filename.rsplit(".", 1)[0]

    dataset = Dataset(
        dataset_name=dataset_name,
        filename=stored_filename,
        upload_date=datetime.utcnow(),
        columns_json=json.dumps(list(df.columns)),
        row_count=len(df),
    )
    db.session.add(dataset)
    db.session.commit()

    create_snapshot_for_dataset(dataset)

    return jsonify({"message": "Dataset uploaded successfully.", "dataset": dataset.to_dict()}), 201


@app.route("/api/datasets", methods=["GET"])
@app.route("/datasets", methods=["GET"])
def api_datasets():
    datasets = Dataset.query.order_by(Dataset.upload_date.desc()).all()
    return jsonify([d.to_dict() for d in datasets])


@app.route("/api/snapshots", methods=["GET"])
@app.route("/snapshots", methods=["GET"])
def api_snapshots():
    dataset_id = request.args.get("dataset_id", type=int)
    query = Snapshot.query
    if dataset_id:
        query = query.filter_by(dataset_id=dataset_id)
    snapshots = query.order_by(Snapshot.snapshot_date.asc()).all()
    return jsonify([s.to_dict() for s in snapshots])


@app.route("/api/drift-report/<int:dataset_id>", methods=["GET"])
@app.route("/drift-report/<int:dataset_id>", methods=["GET"])
def api_drift_report(dataset_id):
    Dataset.query.get_or_404(dataset_id)
    reports = (
        DriftReport.query.filter_by(dataset_id=dataset_id)
        .order_by(DriftReport.created_at.desc())
        .all()
    )
    return jsonify([r.to_dict() for r in reports])


@app.route("/api/dashboard", methods=["GET"])
@app.route("/dashboard", methods=["GET"])
def api_dashboard():
    total_datasets = Dataset.query.count()
    total_snapshots = Snapshot.query.count()

    drift_alerts = DriftReport.query.filter(DriftReport.drift_level != "Low").count()

    latest_report = DriftReport.query.order_by(DriftReport.created_at.desc()).first()
    latest_report_data = latest_report.to_dict() if latest_report else None
    if latest_report_data:
        ds = Dataset.query.get(latest_report.dataset_id)
        latest_report_data["dataset_name"] = ds.dataset_name if ds else "Unknown"

    # Per-dataset summary for table on dashboard
    datasets = Dataset.query.order_by(Dataset.upload_date.desc()).all()
    dataset_summaries = []
    for d in datasets:
        last_snapshot = (
            Snapshot.query.filter_by(dataset_id=d.id)
            .order_by(Snapshot.snapshot_date.desc())
            .first()
        )
        dataset_summaries.append(
            {
                "id": d.id,
                "dataset_name": d.dataset_name,
                "row_count": d.row_count,
                "snapshot_count": Snapshot.query.filter_by(dataset_id=d.id).count(),
                "last_drift_score": last_snapshot.drift_score if last_snapshot else 0,
                "last_drift_level": _score_to_level(last_snapshot.drift_score) if last_snapshot else "N/A",
                "last_snapshot_date": last_snapshot.snapshot_date.isoformat() if last_snapshot else None,
            }
        )

    return jsonify(
        {
            "total_datasets": total_datasets,
            "total_snapshots": total_snapshots,
            "drift_alerts": drift_alerts,
            "latest_report": latest_report_data,
            "datasets": dataset_summaries,
        }
    )


def _score_to_level(score):
    if score is None:
        return "N/A"
    if score < 5:
        return "Low"
    elif score <= 15:
        return "Medium"
    return "High"


@app.route("/api/generate-snapshot/<int:dataset_id>", methods=["POST"])
def api_generate_snapshot(dataset_id):
    """
    Manually trigger a new snapshot for a dataset (simulates the daily job).
    Re-reads the same CSV file - in a real deployment this would pull fresh
    data from the source system, or you'd re-upload an updated CSV first.
    """
    dataset = Dataset.query.get_or_404(dataset_id)
    snapshot = create_snapshot_for_dataset(dataset)
    return jsonify({"message": "Snapshot generated.", "snapshot": snapshot.to_dict()})


@app.route("/api/dataset/<int:dataset_id>/update-data", methods=["POST"])
def api_update_dataset_data(dataset_id):
    """
    Replace this dataset's underlying CSV file with a newly uploaded CSV
    (e.g. "this week's" data) and immediately generate a new snapshot +
    drift report comparing it to the previous snapshot.

    This is the easy, UI-driven alternative to manually editing files in
    the uploads/ folder.
    """
    dataset = Dataset.query.get_or_404(dataset_id)

    if "file" not in request.files:
        return jsonify({"error": "No file part in request."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Only .csv files are supported."}), 400

    filename = secure_filename(file.filename)
    stored_filename = f"{int(datetime.utcnow().timestamp())}_{filename}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], stored_filename)
    file.save(filepath)

    # Schema validation
    try:
        df = pd.read_csv(filepath)
    except Exception as exc:  # noqa: BLE001
        os.remove(filepath)
        return jsonify({"error": f"Could not parse CSV: {exc}"}), 400

    if len(df.columns) == 0:
        os.remove(filepath)
        return jsonify({"error": "CSV file has no columns."}), 400

    # Point the dataset at the new file and generate a snapshot/drift report
    dataset.filename = stored_filename
    db.session.commit()

    snapshot = create_snapshot_for_dataset(dataset)

    return jsonify({"message": "Dataset updated and new snapshot generated.", "snapshot": snapshot.to_dict()})


@app.route("/api/dataset/<int:dataset_id>/columns", methods=["GET"])
def api_dataset_columns(dataset_id):
    dataset = Dataset.query.get_or_404(dataset_id)
    columns = json.loads(dataset.columns_json) if dataset.columns_json else []

    last_snapshot = (
        Snapshot.query.filter_by(dataset_id=dataset.id)
        .order_by(Snapshot.snapshot_date.desc())
        .first()
    )
    column_stats = {}
    if last_snapshot and last_snapshot.stats_json:
        column_stats = json.loads(last_snapshot.stats_json).get("columns", {})

    return jsonify({"columns": columns, "column_stats": column_stats})


# ---------------------------------------------------------------------------
# Report downloads
# ---------------------------------------------------------------------------

@app.route("/reports/pdf/<int:dataset_id>")
def download_pdf_report(dataset_id):
    dataset = Dataset.query.get_or_404(dataset_id)
    latest_report = (
        DriftReport.query.filter_by(dataset_id=dataset_id)
        .order_by(DriftReport.created_at.desc())
        .first()
    )
    latest_snapshot = (
        Snapshot.query.filter_by(dataset_id=dataset_id)
        .order_by(Snapshot.snapshot_date.desc())
        .first()
    )

    filepath = generate_pdf_report(dataset, latest_snapshot, latest_report, app.config["REPORTS_FOLDER"])
    return send_file(filepath, as_attachment=True)


@app.route("/reports/csv/<int:dataset_id>")
def download_csv_report(dataset_id):
    dataset = Dataset.query.get_or_404(dataset_id)
    snapshots = (
        Snapshot.query.filter_by(dataset_id=dataset_id)
        .order_by(Snapshot.snapshot_date.asc())
        .all()
    )
    filepath = generate_csv_report(dataset, snapshots, app.config["REPORTS_FOLDER"])
    return send_file(filepath, as_attachment=True)


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error", "details": str(e)}), 500


# ---------------------------------------------------------------------------
# Bootstrap: create tables and seed sample data on first run
# ---------------------------------------------------------------------------

def seed_sample_data():
    """If the database is empty, load the bundled sample CSVs and generate
    two snapshots each (so drift comparisons are visible immediately)."""
    if Dataset.query.count() > 0:
        return

    sample_dir = os.path.join(BASE_DIR, "sample_data")
    if not os.path.isdir(sample_dir):
        return

    samples = [
        ("Orders Dataset", "orders_week1.csv", "orders_week2.csv"),
        ("Customers Dataset", "customers_week1.csv", "customers_week2.csv"),
    ]

    for name, file_week1, file_week2 in samples:
        path1 = os.path.join(sample_dir, file_week1)
        path2 = os.path.join(sample_dir, file_week2)
        if not (os.path.exists(path1) and os.path.exists(path2)):
            continue

        # Use week1 as the initially "uploaded" file
        stored_filename = f"seed_{file_week1}"
        dest_path = os.path.join(app.config["UPLOAD_FOLDER"], stored_filename)
        if not os.path.exists(dest_path):
            with open(path1, "rb") as src, open(dest_path, "wb") as dst:
                dst.write(src.read())

        df = pd.read_csv(dest_path)
        dataset = Dataset(
            dataset_name=name,
            filename=stored_filename,
            upload_date=datetime.utcnow(),
            columns_json=json.dumps(list(df.columns)),
            row_count=len(df),
        )
        db.session.add(dataset)
        db.session.commit()

        # First snapshot (week 1)
        create_snapshot_for_dataset(dataset)

        # Swap in week 2 data and create second snapshot to generate a drift report
        stored_filename_2 = f"seed_{file_week2}"
        dest_path_2 = os.path.join(app.config["UPLOAD_FOLDER"], stored_filename_2)
        if not os.path.exists(dest_path_2):
            with open(path2, "rb") as src, open(dest_path_2, "wb") as dst:
                dst.write(src.read())

        dataset.filename = stored_filename_2
        db.session.commit()
        create_snapshot_for_dataset(dataset)


with app.app_context():
    db.create_all()
    seed_sample_data()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

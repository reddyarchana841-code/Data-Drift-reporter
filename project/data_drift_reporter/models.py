"""
models.py
SQLAlchemy ORM models for Data Drift Reporter.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Dataset(db.Model):
    __tablename__ = "datasets"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    dataset_name = db.Column(db.String(255), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    columns_json = db.Column(db.Text)  # JSON list of column names (schema)
    row_count = db.Column(db.Integer, default=0)

    snapshots = db.relationship(
        "Snapshot", backref="dataset", lazy=True, cascade="all, delete-orphan"
    )
    drift_reports = db.relationship(
        "DriftReport", backref="dataset", lazy=True, cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "dataset_name": self.dataset_name,
            "filename": self.filename,
            "upload_date": self.upload_date.isoformat() if self.upload_date else None,
            "row_count": self.row_count,
        }


class Snapshot(db.Model):
    __tablename__ = "snapshots"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    dataset_id = db.Column(db.Integer, db.ForeignKey("datasets.id"), nullable=False)
    snapshot_date = db.Column(db.DateTime, default=datetime.utcnow)

    row_count = db.Column(db.Integer)
    null_rate = db.Column(db.Float)  # overall average null rate (%)
    mean_value = db.Column(db.Float)  # average of column means (numeric cols)
    drift_score = db.Column(db.Float, default=0.0)  # overall drift % vs previous

    # Detailed per-column stats stored as JSON text for flexibility
    stats_json = db.Column(db.Text)

    def to_dict(self):
        return {
            "id": self.id,
            "dataset_id": self.dataset_id,
            "snapshot_date": self.snapshot_date.isoformat() if self.snapshot_date else None,
            "row_count": self.row_count,
            "null_rate": self.null_rate,
            "mean_value": self.mean_value,
            "drift_score": self.drift_score,
        }


class DriftReport(db.Model):
    __tablename__ = "drift_reports"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    dataset_id = db.Column(db.Integer, db.ForeignKey("datasets.id"), nullable=False)
    report_text = db.Column(db.Text)
    drift_level = db.Column(db.String(20))  # Low / Medium / High
    drift_score = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "dataset_id": self.dataset_id,
            "report_text": self.report_text,
            "drift_level": self.drift_level,
            "drift_score": self.drift_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

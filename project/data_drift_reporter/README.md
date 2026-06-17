# Data Drift Reporter

A full-stack application that automatically monitors data quality and detects
drift in business tables. Upload CSV snapshots of your tables, and the system
computes daily statistics, stores historical snapshots, compares trends
week-over-week, and generates business-friendly AI narratives about what
changed and why it matters.

## Tech Stack

- **Backend**: Python Flask
- **Database**: SQLite (via SQLAlchemy ORM)
- **Data Processing**: Pandas, NumPy
- **Frontend**: HTML, CSS, JavaScript, Bootstrap 5
- **Visualization**: Chart.js
- **AI Layer**: LLM-powered narration module (Claude API, with offline rule-based fallback)
- **PDF/CSV Reports**: fpdf2

## Project Structure

```
data_drift_reporter/
├── app.py                 # Flask app, routes, orchestration
├── models.py              # SQLAlchemy models (Dataset, Snapshot, DriftReport)
├── drift_engine.py         # Statistics computation + drift detection logic
├── narrator.py             # AI narration module (LLM + rule-based fallback)
├── report_generator.py     # PDF / CSV report generation
├── requirements.txt
├── database.db             # SQLite database (created automatically)
├── templates/               # Jinja2 HTML templates
│   ├── base.html
│   ├── dashboard.html
│   ├── upload.html
│   ├── datasets.html
│   └── dataset_detail.html
├── static/
│   ├── css/style.css
│   └── js/*.js
├── uploads/                 # Uploaded CSV files are stored here
├── reports/                 # Generated PDF/CSV reports are stored here
└── sample_data/             # Sample CSVs for testing drift detection
    ├── orders_week1.csv
    ├── orders_week2.csv
    ├── customers_week1.csv
    └── customers_week2.csv
```

## Setup & Run (single command)

1. Create a virtual environment (recommended) and install dependencies:

```bash
cd data_drift_reporter
python -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Run the app:

```bash
python app.py
```

3. Open your browser at **http://127.0.0.1:5000**

On first run, the app automatically:
- Creates the SQLite database and tables
- Loads the bundled sample datasets (Orders, Customers)
- Generates two snapshots for each (week 1 and week 2 data), so you can
  immediately see a drift report, charts, and AI narration without uploading
  anything yourself.

## Using the App

### Dashboard
Shows total datasets monitored, total snapshots, drift alerts, the latest
AI-generated drift narrative, a table of all datasets with their latest drift
score/level, and trend charts (drift score, null rate, row count) across all
datasets.

### Upload Dataset
Upload a `.csv` file with a dataset name. The system:
1. Validates the file is a parseable CSV with at least one column.
2. Stores the file under `uploads/`.
3. Computes the first snapshot (row count, null %, mean/median/min/max/std,
   unique counts per column).

### Dataset Detail Page
- View current stats, latest drift score, and snapshot count.
- Click **Generate New Snapshot** to simulate the daily job - this re-reads
  the dataset's CSV, computes a new snapshot, compares it to the previous
  one, computes a drift score/level, and generates a new AI narrative.
- View trend charts for drift score, null rate, and row count over time.
- View full snapshot history and drift report history.
- Download a **PDF Drift Report** or **CSV Snapshot Report**.

## Drift Detection Logic

For each new snapshot, the system compares:
- **Row count** vs previous snapshot (% change)
- **Overall null rate** vs previous snapshot (percentage point change)
- **Overall mean** (average of numeric column means) vs previous snapshot (% change)
- **Per-column** null rate changes and mean shifts

These are combined into an overall **drift score** (0-100), classified as:

| Drift Score | Level  |
|-------------|--------|
| < 5%        | Low    |
| 5% - 15%    | Medium |
| > 15%       | High   |

## AI Narration Module

`narrator.py` generates business-analyst-style summaries such as:

> "Average order_amount decreased by 18.3% (from 154.62 to 126.18).
> 'customer_email' null rate increased from 0.00% to 23.53%.
> Row count decreased by 15.0%, indicating reduced data volume.
> Recommendation: Monitor this dataset closely over the next few snapshots..."

**LLM mode**: If the `ANTHROPIC_API_KEY` environment variable is set (and the
`anthropic` package is installed), the module sends the structured drift
events to Claude to generate a more polished narrative.

**Offline fallback (default)**: If no API key is set, or the LLM call fails
for any reason (no network access, etc.), the module automatically falls
back to a deterministic, rule-based narrative built from the same structured
drift data - so the app works fully offline out of the box.

To enable LLM narration:

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
python app.py
```

## Testing Drift Detection Manually

1. Go to **Upload Dataset** and upload `sample_data/orders_week1.csv` with
   dataset name "My Orders".
2. Go to the dataset's detail page.
3. To simulate a new week of data with drift, you'd normally re-upload an
   updated CSV. For a quick demo using the bundled files, the seeded
   "Orders Dataset" and "Customers Dataset" on the dashboard already include
   both week-1 and week-2 snapshots with a generated drift report - open
   either of those datasets to see drift scores, AI narration, and charts
   immediately.

## API Endpoints

| Method | Endpoint                              | Description                                  |
|--------|----------------------------------------|----------------------------------------------|
| POST   | `/upload`                              | Upload a CSV and generate first snapshot     |
| GET    | `/api/datasets`                        | List all datasets                            |
| GET    | `/api/snapshots?dataset_id=<id>`       | List snapshots (optionally filtered)         |
| GET    | `/api/drift-report/<dataset_id>`       | List drift reports for a dataset             |
| GET    | `/api/dashboard`                       | Aggregate dashboard stats                    |
| POST   | `/api/generate-snapshot/<dataset_id>`  | Generate a new snapshot + drift report       |
| GET    | `/api/dataset/<dataset_id>/columns`    | Column names + latest column-level stats     |
| GET    | `/reports/pdf/<dataset_id>`            | Download PDF drift report                    |
| GET    | `/reports/csv/<dataset_id>`            | Download CSV snapshot history                |

## Database Schema

**datasets**: `id, dataset_name, filename, upload_date, columns_json, row_count`

**snapshots**: `id, dataset_id, snapshot_date, row_count, null_rate, mean_value, drift_score, stats_json`

**drift_reports**: `id, dataset_id, report_text, drift_level, drift_score, created_at`

## Notes / Production Considerations

- Replace SQLite with PostgreSQL for multi-user / production deployments
  (just change `SQLALCHEMY_DATABASE_URI`).
- Replace the manual "Generate New Snapshot" button with a scheduled job
  (e.g. APScheduler or a cron job calling `/api/generate-snapshot/<id>`)
  for true daily automation.
- Set `app.config["SECRET_KEY"]` to a secure random value and disable
  `debug=True` in production.
- Add authentication before exposing this publicly, since it allows file
  uploads.

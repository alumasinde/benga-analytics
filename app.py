import os
import uuid
from datetime import datetime, timezone
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory, session
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import database
from analyzer import build_insights, dataframe_records, infer_and_clean, read_dataframe
from services.subscription_service import (
    FREE,
    build_subscription,
    normalize_user_subscription,
    plan_for,
    public_user,
)

load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "development-only-change-me")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", 104857600))
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_ENV") == "production"

db = database.init_database()


def now():
    return datetime.now(timezone.utc)


def valid_uuid(value):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid identifier.") from exc


def serialize(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    return value


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    try:
        return db.get_user_by_id(valid_uuid(user_id))
    except ValueError:
        session.clear()
        return None


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"error": "Authentication required."}), 401
        return fn(user, *args, **kwargs)

    return wrapped


def active_plan_for(user):
    normalized = normalize_user_subscription(user)
    if normalized["status"] not in {"active", "trialing"}:
        return None, normalized
    return normalized["plan"], normalized


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "File exceeds the server upload limit."}), 413


@app.errorhandler(ValueError)
def bad_value(error):
    return jsonify({"error": str(error)}), 400


@app.errorhandler(Exception)
def unexpected_error(error):
    if isinstance(error, HTTPException):
        return error
    app.logger.exception(error)
    return jsonify({"error": "An unexpected server error occurred."}), 500


@app.get("/")
def home():
    return send_from_directory("templates", "dashboard.html")


@app.get("/terms")
def terms():
    return send_from_directory("templates", "terms.html")


@app.get("/privacy")
def privacy():
    return send_from_directory("templates", "privacy.html")


@app.post("/api/auth/signup")
def signup():
    payload = request.get_json(silent=True) or {}
    first_name = " ".join(str(payload.get("first_name", "")).strip().split())
    last_name = " ".join(str(payload.get("last_name", "")).strip().split())
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    confirm_password = str(payload.get("confirm_password", ""))
    accepted_terms = payload.get("accepted_terms") is True

    if not 1 <= len(first_name) <= 80:
        return jsonify({"error": "Enter a valid first name."}), 400
    if not 1 <= len(last_name) <= 80:
        return jsonify({"error": "Enter a valid last name."}), 400
    if not email or "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        return jsonify({"error": "Enter a valid email address."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must contain at least 8 characters."}), 400
    if password != confirm_password:
        return jsonify({"error": "Passwords do not match."}), 400
    if not accepted_terms:
        return jsonify({
            "error": "You must accept the Terms of Service and Privacy Policy."
        }), 400

    created = now()
    user = {
        "id": str(uuid.uuid4()),
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "password_hash": generate_password_hash(password),
        "tenant_id": str(uuid.uuid4()),
        "tier": FREE,
        "subscription": build_subscription(FREE),
        "terms": {
            "accepted": True,
            "accepted_at": created.isoformat(),
            "version": "1.0",
        },
        "active": True,
        "created_at": created,
        "updated_at": created,
    }

    try:
        db.create_user(user)
    except IntegrityError:
        return jsonify({"error": "An account already exists for this email."}), 409

    session.clear()
    session["user_id"] = user["id"]
    return jsonify({"user": serialize(public_user(user))}), 201


@app.post("/api/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))

    user = db.get_user_by_email(email)
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password."}), 401

    session.clear()
    session["user_id"] = user["id"]
    return jsonify({"user": serialize(public_user(user))})


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/auth/me")
def me():
    user = current_user()
    if not user:
        return jsonify({"authenticated": False}), 401
    return jsonify({"authenticated": True, "user": serialize(public_user(user))})


@app.get("/api/plans")
def plans():
    return jsonify({
        "plans": {
            "free": plan_for("free"),
            "enterprise_pro": plan_for("enterprise_pro"),
        }
    })


@app.get("/api/datasets")
@login_required
def list_datasets(user):
    rows = db.list_datasets(user["tenant_id"], limit=100)
    return jsonify({"datasets": serialize(rows)})


@app.post("/api/upload")
@login_required
def upload(user):
    if "file" not in request.files:
        return jsonify({"error": "No file was supplied."}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Select a file first."}), 400

    filename = secure_filename(file.filename)
    if not filename.lower().endswith((".csv", ".xlsx")):
        return jsonify({"error": "Only CSV and XLSX files are allowed."}), 400

    plan, subscription_state = active_plan_for(user)
    if not plan:
        return jsonify({
            "error": "Your subscription is not active.",
            "subscription_status": subscription_state["status"],
        }), 403

    dataset_count = db.count_datasets(user["tenant_id"])
    if dataset_count >= plan["max_datasets"]:
        return jsonify({
            "error": f"Dataset limit reached for the {plan['name']} plan.",
            "limit": plan["max_datasets"],
        }), 403

    df = read_dataframe(file)
    if len(df) > plan["max_rows_per_dataset"]:
        return jsonify({
            "error": (
                f"Your {plan['name']} plan allows "
                f"{plan['max_rows_per_dataset']:,} rows per dataset."
            ),
            "limit": plan["max_rows_per_dataset"],
        }), 403

    df, metadata = infer_and_clean(df)
    dataset_id = str(uuid.uuid4())
    created = now()
    dataset = {
        "id": dataset_id,
        "tenant_id": user["tenant_id"],
        "owner_id": user["id"],
        "filename": filename,
        "created_at": created,
        "updated_at": created,
        "status": "ready",
        "schema_metadata": metadata,
        "row_count": metadata["row_count"],
    }

    records = [
        {
            "dataset_id": dataset_id,
            "tenant_id": user["tenant_id"],
            "row_data": row,
        }
        for row in dataframe_records(df)
    ]

    db.create_dataset_with_records(dataset, records)

    response_dataset = {
        "_id": dataset["id"],
        "id": dataset["id"],
        "tenant_id": dataset["tenant_id"],
        "owner_id": dataset["owner_id"],
        "filename": dataset["filename"],
        "created_at": dataset["created_at"],
        "updated_at": dataset["updated_at"],
        "status": dataset["status"],
        "schema": metadata,
        "row_count": dataset["row_count"],
    }

    return jsonify({
        "dataset": serialize(response_dataset),
        "metadata": serialize(metadata),
        "plan": {
            "name": plan["name"],
            "max_rows_per_dataset": plan["max_rows_per_dataset"],
            "max_datasets": plan["max_datasets"],
        },
    }), 201


@app.post("/api/query")
@login_required
def query(user):
    payload = request.get_json(silent=True) or {}
    dataset_id = valid_uuid(payload.get("dataset_id", ""))
    dataset = db.get_dataset(dataset_id, user["tenant_id"])
    if not dataset:
        return jsonify({"error": "Dataset not found."}), 404

    schema = dataset["schema_metadata"]
    dimensions = set(schema.get("dimensions", []))
    metrics = set(schema.get("metrics", []))
    dates = set(schema.get("dates", []))

    aggregation = str(payload.get("aggregation", "sum")).lower()
    metric = payload.get("metric")
    group_by = payload.get("group_by")
    filters = payload.get("filters", {}) or {}
    search = str(payload.get("search", "")).strip()

    if aggregation not in {"sum", "avg", "count"}:
        return jsonify({"error": "Unsupported aggregation."}), 400
    if group_by and group_by not in dimensions and group_by not in dates:
        return jsonify({"error": "Invalid grouping field."}), 400
    if aggregation != "count" and metric not in metrics:
        return jsonify({"error": "Choose a valid numerical metric."}), 400
    if not isinstance(filters, dict):
        return jsonify({"error": "Filters must be an object."}), 400

    valid_filters = {}
    for field, values in filters.items():
        if field in dimensions and isinstance(values, list) and values:
            valid_filters[field] = values[:1000]

    rows, raw = db.query_records(
        dataset_id=dataset_id,
        tenant_id=user["tenant_id"],
        aggregation=aggregation,
        metric=metric,
        group_by=group_by,
        filters=valid_filters,
        search=search,
        dimensions=list(dimensions),
    )

    return jsonify({
        "rows": serialize(rows),
        "raw_records": serialize(raw),
        "insights": build_insights(rows, metric, aggregation, group_by),
        "query": {
            "metric": metric,
            "aggregation": aggregation,
            "group_by": group_by,
        },
    })


if __name__ == "__main__":
    db.ping()
    db.ensure_schema()
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=os.getenv("FLASK_ENV") != "production",
    )

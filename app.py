import os
import uuid
from datetime import datetime, timezone
from functools import wraps

from bson import ObjectId
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory, session
from pymongo.errors import DuplicateKeyError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import database
from analyzer import build_insights, dataframe_records, infer_and_clean, read_dataframe
from services.subscription_service import FREE, build_subscription, normalize_user_subscription, plan_for, public_user

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


def oid(value):
    try:
        return ObjectId(value)
    except Exception as exc:
        raise ValueError("Invalid identifier.") from exc


def serialize(value):
    if isinstance(value, ObjectId):
        return str(value)
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
        return db.users.find_one({"_id": oid(user_id), "active": True})
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
    app.logger.exception(error)
    return jsonify({"error": "An unexpected server error occurred."}), 500


@app.get("/")
def home():
    return send_from_directory("templates", "dashboard.html")


@app.post("/api/auth/signup")
def signup():
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))

    if not email or "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        return jsonify({"error": "Enter a valid email address."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must contain at least 8 characters."}), 400

    created = now()
    user = {
        "email": email,
        "password_hash": generate_password_hash(password),
        "tenant_id": str(uuid.uuid4()),
        "tier": FREE,
        "subscription": build_subscription(FREE),
        "active": True,
        "created_at": created,
        "updated_at": created,
    }

    try:
        result = db.users.insert_one(user)
    except DuplicateKeyError:
        return jsonify({"error": "An account already exists for this email."}), 409

    session.clear()
    session["user_id"] = str(result.inserted_id)
    return jsonify({"user": serialize(public_user(user))}), 201


@app.post("/api/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))

    user = db.users.find_one({"email": email, "active": True})
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password."}), 401

    session.clear()
    session["user_id"] = str(user["_id"])
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
    return jsonify({"plans": {"free": plan_for("free"), "enterprise_pro": plan_for("enterprise_pro")}})


@app.get("/api/datasets")
@login_required
def list_datasets(user):
    rows = list(db.datasets.find({"tenant_id": user["tenant_id"]}).sort("created_at", -1).limit(100))
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
        return jsonify({"error": "Your subscription is not active.", "subscription_status": subscription_state["status"]}), 403

    dataset_count = db.datasets.count_documents({"tenant_id": user["tenant_id"]})
    if dataset_count >= plan["max_datasets"]:
        return jsonify({"error": f"Dataset limit reached for the {plan['name']} plan.", "limit": plan["max_datasets"]}), 403

    df = read_dataframe(file)
    if len(df) > plan["max_rows_per_dataset"]:
        return jsonify({"error": f"Your {plan['name']} plan allows {plan['max_rows_per_dataset']:,} rows per dataset.", "limit": plan["max_rows_per_dataset"]}), 403

    df, metadata = infer_and_clean(df)
    dataset_id = ObjectId()
    dataset = {
        "_id": dataset_id,
        "tenant_id": user["tenant_id"],
        "owner_id": user["_id"],
        "filename": filename,
        "created_at": now(),
        "updated_at": now(),
        "status": "ready",
        "schema": metadata,
        "row_count": metadata["row_count"],
    }

    db.datasets.insert_one(dataset)
    batch = []
    try:
        for row in dataframe_records(df):
            row["dataset_id"] = dataset_id
            row["tenant_id"] = user["tenant_id"]
            batch.append(row)
            if len(batch) >= 5000:
                db.records.insert_many(batch, ordered=False)
                batch = []
        if batch:
            db.records.insert_many(batch, ordered=False)
    except Exception:
        db.records.delete_many({"dataset_id": dataset_id})
        db.datasets.delete_one({"_id": dataset_id})
        raise

    return jsonify({"dataset": serialize(dataset), "metadata": serialize(metadata), "plan": {"name": plan["name"], "max_rows_per_dataset": plan["max_rows_per_dataset"], "max_datasets": plan["max_datasets"]}}), 201


@app.post("/api/query")
@login_required
def query(user):
    payload = request.get_json(silent=True) or {}
    dataset_id = oid(payload.get("dataset_id", ""))
    dataset = db.datasets.find_one({"_id": dataset_id, "tenant_id": user["tenant_id"]})
    if not dataset:
        return jsonify({"error": "Dataset not found."}), 404

    schema = dataset["schema"]
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

    match = {"dataset_id": dataset_id, "tenant_id": user["tenant_id"]}

    for field, values in filters.items():
        if field in dimensions and isinstance(values, list) and values:
            match[field] = {"$in": values[:1000]}

    if search and dimensions:
        match["$or"] = [{field: {"$regex": search[:200], "$options": "i"}} for field in dimensions]

    value_expression = (
        {"$sum": 1}
        if aggregation == "count"
        else ({"$sum": f"${metric}"} if aggregation == "sum" else {"$avg": f"${metric}"})
    )

    group_id = f"${group_by}" if group_by else None
    result = list(db.records.aggregate([
        {"$match": match},
        {"$group": {"_id": group_id, "value": value_expression}},
        {"$sort": {"value": -1}},
        {"$limit": 1000},
    ], allowDiskUse=True))

    rows = [{"label": str(item["_id"]) if item["_id"] is not None else "All Records", "value": item["value"]} for item in result]
    raw = list(db.records.find(match, {"dataset_id": 0, "tenant_id": 0}).limit(100))

    return jsonify({
        "rows": serialize(rows),
        "raw_records": serialize(raw),
        "insights": build_insights(rows, metric, aggregation, group_by),
        "query": {"metric": metric, "aggregation": aggregation, "group_by": group_by},
    })


if __name__ == "__main__":
    db.ping()
    db.ensure_indexes()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=os.getenv("FLASK_ENV") != "production")

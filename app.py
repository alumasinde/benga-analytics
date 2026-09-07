import os
import uuid
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from pymongo import DuplicateKeyError
from bson import ObjectId
from dotenv import load_dotenv
from database import db
from analyzer import read_dataframe, infer_and_clean, dataframe_records, build_insights
load_dotenv()
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "development-only-change-me")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", 104857600))
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_ENV") == "production"
TIER_LIMITS = {"trial": {"max_rows_per_dataset": 50000, "max_datasets": 5}, "enterprise_pro": {"max_rows_per_dataset": 5000000, "max_datasets": 1000000}}
def now(): return datetime.now(timezone.utc)
def oid(value):
    try: return ObjectId(value)
    except Exception: raise ValueError("Invalid identifier.")
def serialize(value):
    if isinstance(value, ObjectId): return str(value)
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, dict): return {k: serialize(v) for k, v in value.items()}
    if isinstance(value, list): return [serialize(v) for v in value]
    return value
def current_user():
    user_id = session.get("user_id")
    if not user_id: return None
    return db.users.find_one({"_id": oid(user_id), "active": True})
def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user: return jsonify({"error": "Authentication required."}), 401
        return fn(user, *args, **kwargs)
    return wrapped
@app.errorhandler(413)
def too_large(_): return jsonify({"error": "File exceeds the server upload limit."}), 413
@app.errorhandler(Exception)
def unexpected_error(error):
    app.logger.exception(error); return jsonify({"error": "An unexpected server error occurred."}), 500
@app.get("/")
def home(): return send_from_directory("templates", "dashboard.html")
@app.post("/api/auth/signup")
def signup():
    payload = request.get_json(silent=True) or {}; email = str(payload.get("email", "")).strip().lower(); password = str(payload.get("password", ""))
    if not email or "@" not in email or len(password) < 8: return jsonify({"error": "Use a valid email and password of at least 8 characters."}), 400
    created = now()
    user = {"email": email, "password_hash": generate_password_hash(password), "tenant_id": str(uuid.uuid4()), "tier": "trial", "active": True, "billing": {"status": "trialing", "trial_started_at": created, "trial_ends_at": created + timedelta(days=7), "renewal_at": None}, "created_at": created, "updated_at": created}
    try: result = db.users.insert_one(user)
    except DuplicateKeyError: return jsonify({"error": "An account already exists for this email."}), 409
    session["user_id"] = str(result.inserted_id); return jsonify({"user": serialize(user), "id": str(result.inserted_id)}), 201
@app.post("/api/auth/login")
def login():
    payload = request.get_json(silent=True) or {}; email = str(payload.get("email", "")).strip().lower(); password = str(payload.get("password", "")); user = db.users.find_one({"email": email, "active": True})
    if not user or not check_password_hash(user["password_hash"], password): return jsonify({"error": "Invalid email or password."}), 401
    session.clear(); session["user_id"] = str(user["_id"]); return jsonify({"user": serialize(user)})
@app.post("/api/auth/logout")
def logout(): session.clear(); return jsonify({"ok": True})
@app.get("/api/auth/me")
def me():
    user = current_user()
    if not user: return jsonify({"authenticated": False}), 401
    return jsonify({"authenticated": True, "user": serialize(user)})
@app.get("/api/datasets")
@login_required
def list_datasets(user):
    rows = list(db.datasets.find({"tenant_id": user["tenant_id"]}).sort("created_at", -1).limit(100)); return jsonify({"datasets": serialize(rows)})
@app.post("/api/upload")
@login_required
def upload(user):
    if "file" not in request.files: return jsonify({"error": "No file was supplied."}), 400
    file = request.files["file"]
    if not file.filename: return jsonify({"error": "Select a file first."}), 400
    filename = secure_filename(file.filename)
    if not filename.lower().endswith((".csv", ".xlsx")): return jsonify({"error": "Only CSV and XLSX files are allowed."}), 400
    limits = TIER_LIMITS.get(user["tier"], TIER_LIMITS["trial"])
    if db.datasets.count_documents({"tenant_id": user["tenant_id"]}) >= limits["max_datasets"]: return jsonify({"error": "Dataset limit reached for your subscription tier."}), 403
    df = read_dataframe(file)
    if len(df) > limits["max_rows_per_dataset"]: return jsonify({"error": f"Your {user['tier']} tier allows {limits['max_rows_per_dataset']:,} rows per dataset."}), 403
    df, metadata = infer_and_clean(df); dataset_id = ObjectId()
    dataset = {"_id": dataset_id, "tenant_id": user["tenant_id"], "owner_id": user["_id"], "filename": filename, "created_at": now(), "updated_at": now(), "status": "ready", "schema": metadata, "row_count": metadata["row_count"]}
    db.datasets.insert_one(dataset); batch = []
    try:
        for row in dataframe_records(df):
            row["dataset_id"] = dataset_id; row["tenant_id"] = user["tenant_id"]; batch.append(row)
            if len(batch) >= 5000: db.records.insert_many(batch, ordered=False); batch = []
        if batch: db.records.insert_many(batch, ordered=False)
    except Exception:
        db.records.delete_many({"dataset_id": dataset_id}); db.datasets.delete_one({"_id": dataset_id}); raise
    return jsonify({"dataset": serialize(dataset), "metadata": serialize(metadata)}), 201
@app.post("/api/query")
@login_required
def query(user):
    payload = request.get_json(silent=True) or {}; dataset_id = oid(payload.get("dataset_id", "")); dataset = db.datasets.find_one({"_id": dataset_id, "tenant_id": user["tenant_id"]})
    if not dataset: return jsonify({"error": "Dataset not found."}), 404
    schema = dataset["schema"]; dimensions = set(schema.get("dimensions", [])); metrics = set(schema.get("metrics", [])); aggregation = str(payload.get("aggregation", "sum")).lower(); metric = payload.get("metric"); group_by = payload.get("group_by"); filters = payload.get("filters", {}) or {}; search = str(payload.get("search", "")).strip()
    if aggregation not in {"sum", "avg", "count"}: return jsonify({"error": "Unsupported aggregation."}), 400
    if group_by and group_by not in dimensions and group_by not in schema.get("dates", []): return jsonify({"error": "Invalid grouping field."}), 400
    if aggregation != "count" and metric not in metrics: return jsonify({"error": "Choose a valid numerical metric."}), 400
    match = {"dataset_id": dataset_id, "tenant_id": user["tenant_id"]}
    for field, values in filters.items():
        if field in dimensions and isinstance(values, list) and values: match[field] = {"$in": values}
    if search and dimensions: match["$or"] = [{field: {"$regex": search[:200], "$options": "i"}} for field in dimensions]
    value_expr = {"$sum": 1} if aggregation == "count" else ({"$sum": f"${metric}"} if aggregation == "sum" else {"$avg": f"${metric}"})
    group_id = f"${group_by}" if group_by else None
    result = list(db.records.aggregate([{"$match": match}, {"$group": {"_id": group_id, "value": value_expr}}, {"$sort": {"value": -1}}, {"$limit": 1000}], allowDiskUse=True))
    rows = [{"label": str(x["_id"]) if x["_id"] is not None else "All Records", "value": x["value"]} for x in result]; raw = list(db.records.find(match, {"dataset_id": 0, "tenant_id": 0}).limit(100))
    return jsonify({"rows": serialize(rows), "raw_records": serialize(raw), "insights": build_insights(rows, metric, aggregation, group_by), "query": {"metric": metric, "aggregation": aggregation, "group_by": group_by}})
if __name__ == "__main__":
    db.ping(); app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=os.getenv("FLASK_ENV") != "production")

import os
import uuid
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, jsonify, request, send_from_directory, session
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from config.settings import get_settings
from database import init_database
from services.auth_service import AuthService
from services.dataset_service import DatasetService
from services.query_service import QueryService
from services.subscription_service import (
    FREE,
    build_subscription,
    normalize_user_subscription,
    plan_for,
    public_user,
)

settings = get_settings()
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = settings["secret_key"]
app.config["MAX_CONTENT_LENGTH"] = settings["max_content_length"]
app.config["UPLOAD_FOLDER"] = settings["upload_folder"]
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = settings["environment"] == "production"

db = init_database()


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


def services():
    return AuthService(db), DatasetService(db), QueryService(db)


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    try:
        return AuthService(db).get_user(valid_uuid(user_id))
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
    try:
        user = AuthService(db).signup(request.get_json(silent=True) or {})
    except IntegrityError:
        return jsonify({"error": "An account already exists for this email."}), 409
    session.clear()
    session["user_id"] = user["id"]
    return jsonify({"user": serialize(public_user(user))}), 201


@app.post("/api/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    user = AuthService(db).authenticate(payload.get("email", ""), payload.get("password", ""))
    if not user:
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
    rows = DatasetService(db).list(user["tenant_id"])
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

    dataset_count = DatasetService(db).count(user["tenant_id"])
    if dataset_count >= plan["max_datasets"]:
        return jsonify({
            "error": f"Dataset limit reached for the {plan['name']} plan.",
            "limit": plan["max_datasets"],
        }), 403

    dataset, metadata = DatasetService(db).ingest(user, file)
    dataset_id = dataset["id"]

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
    dataset = DatasetService(db).get(dataset_id, user["tenant_id"])
    if not dataset:
        return jsonify({"error": "Dataset not found."}), 404
    result = QueryService(db).execute(dataset=dataset, dataset_id=dataset_id, tenant_id=user["tenant_id"], payload=payload)
    return jsonify(serialize(result))


if __name__ == "__main__":
    db.ping()
    db.ensure_schema()
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=settings["environment"] != "production",
    )

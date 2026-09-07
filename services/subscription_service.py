from copy import deepcopy
from datetime import datetime, timezone

FREE = "free"
ENTERPRISE_PRO = "enterprise_pro"

PLAN_CATALOG = {
    FREE: {
        "name": "Free",
        "max_rows_per_dataset": 50_000,
        "max_datasets": 5,
        "max_saved_queries": 10,
        "features": {
            "csv_upload": True,
            "xlsx_upload": True,
            "dynamic_filters": True,
            "natural_language_search": True,
            "advanced_exports": False,
            "scheduled_refresh": False,
            "team_workspaces": False,
        },
    },
    ENTERPRISE_PRO: {
        "name": "Enterprise Pro",
        "max_rows_per_dataset": 5_000_000,
        "max_datasets": 1_000_000,
        "max_saved_queries": 100_000,
        "features": {
            "csv_upload": True,
            "xlsx_upload": True,
            "dynamic_filters": True,
            "natural_language_search": True,
            "advanced_exports": True,
            "scheduled_refresh": True,
            "team_workspaces": True,
        },
    },
}


def utcnow():
    return datetime.now(timezone.utc)


def plan_for(tier):
    return deepcopy(PLAN_CATALOG.get(tier, PLAN_CATALOG[FREE]))


def build_subscription(tier=FREE):
    if tier not in PLAN_CATALOG:
        tier = FREE
    return {
        "tier": tier,
        "status": "active",
        "billing_provider": None,
        "billing_customer_id": None,
        "subscription_id": None,
        "current_period_start": None,
        "current_period_end": None,
        "cancel_at_period_end": False,
        "updated_at": utcnow(),
    }


def normalize_user_subscription(user):
    subscription = user.get("subscription") or {}
    tier = subscription.get("tier") or user.get("tier") or FREE
    plan = plan_for(tier)
    return {
        "tier": tier,
        "status": subscription.get("status", "active"),
        "plan": plan,
        "subscription": subscription,
    }


def public_user(user):
    normalized = normalize_user_subscription(user)
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "tenant_id": user["tenant_id"],
        "active": bool(user.get("active", False)),
        "tier": normalized["tier"],
        "plan": {
            "name": normalized["plan"]["name"],
            "limits": {
                "max_rows_per_dataset": normalized["plan"]["max_rows_per_dataset"],
                "max_datasets": normalized["plan"]["max_datasets"],
                "max_saved_queries": normalized["plan"]["max_saved_queries"],
            },
            "features": normalized["plan"]["features"],
        },
        "subscription": {
            "status": normalized["status"],
            "current_period_end": normalized["subscription"].get("current_period_end"),
            "cancel_at_period_end": bool(normalized["subscription"].get("cancel_at_period_end", False)),
        },
        "created_at": user.get("created_at"),
    }

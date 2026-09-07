import uuid
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash
from database.repositories import AuditRepository, UserRepository
from services.subscription_service import FREE, build_subscription, public_user

class AuthService:
    def __init__(self, database):
        self.users = UserRepository(database)
        self.audit = AuditRepository(database)

    @staticmethod
    def _now(): return datetime.now(timezone.utc)

    def signup(self, payload):
        first_name = " ".join(str(payload.get("first_name", "")).strip().split())
        last_name = " ".join(str(payload.get("last_name", "")).strip().split())
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        confirm_password = str(payload.get("confirm_password", ""))
        if not 1 <= len(first_name) <= 80: raise ValueError("Enter a valid first name.")
        if not 1 <= len(last_name) <= 80: raise ValueError("Enter a valid last name.")
        if not email or "@" not in email or "." not in email.rsplit("@", 1)[-1]: raise ValueError("Enter a valid email address.")
        if len(password) < 8: raise ValueError("Password must contain at least 8 characters.")
        if password != confirm_password: raise ValueError("Passwords do not match.")
        if payload.get("accepted_terms") is not True: raise ValueError("You must accept the Terms of Service and Privacy Policy.")
        created = self._now()
        user = {"id":str(uuid.uuid4()),"first_name":first_name,"last_name":last_name,"email":email,"password_hash":generate_password_hash(password),"tenant_id":str(uuid.uuid4()),"tier":FREE,"subscription":build_subscription(FREE),"terms":{"accepted":True,"accepted_at":created.isoformat(),"version":"1.0"},"active":True,"created_at":created,"updated_at":created}
        self.users.create(user)
        self.audit.create({"tenant_id":user["tenant_id"],"actor_id":user["id"],"event_type":"user.signup","event_data":{"email":email},"created_at":created})
        return user

    def authenticate(self, email, password):
        user = self.users.get_by_email(str(email).strip().lower())
        if not user or not check_password_hash(user["password_hash"], str(password)): return None
        return user

    def get_user(self, user_id): return self.users.get_by_id(user_id)

__all__ = ["AuthService", "IntegrityError", "public_user"]

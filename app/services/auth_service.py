from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.db.supabase import get_admin_client, get_auth_client
from app.services.local_credentials_service import demo_admin_credentials
from app.services.access_service import level_for
from app.services.demo_store import DEMO_INTERNAL_USERS, DEMO_USER_PASSWORDS


COOKIE_NAME = "vendra_staging_session" if get_settings().app_env == "staging" else "vendra_session"

DEMO_SESSIONS: dict[str, str] = {}  # session_hash -> user_id; tokens não persistidos

DEMO_USER_ID = "00000000-0000-0000-0000-000000000001"


def _demo_user() -> dict:
    credentials = demo_admin_credentials()
    return {
        "id": DEMO_USER_ID,
        "full_name": credentials["full_name"],
        "email": credentials["email"],
        "role": "administrador",
        "access_level": "administrativo",
        "can_manage_users": True,
        "status": "active",
    }



class AuthError(Exception):
    pass


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def authenticate(email: str, password: str) -> tuple[str, dict]:
    settings = get_settings()

    if settings.demo_mode:
        credentials = demo_admin_credentials()
        if email.lower() == credentials["email"].lower() and password == credentials["password"]:
            token = secrets.token_urlsafe(48)
            DEMO_SESSIONS[_hash_token(token)] = DEMO_USER_ID
            return token, _demo_user()
        for person in DEMO_INTERNAL_USERS:
            if person.get("id") == DEMO_USER_ID or person.get("status") != "active":
                continue
            record = DEMO_USER_PASSWORDS.get(person["id"])
            if person.get("email", "").lower() == email.lower() and record:
                check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(record["salt"]), 600000)
                if hmac.compare_digest(check.hex(), record["hash"]):
                    token = secrets.token_urlsafe(48)
                    DEMO_SESSIONS[_hash_token(token)] = person["id"]
                    return token, person
        raise AuthError("E-mail ou senha inválidos no modo demo.")

    auth = get_auth_client()
    admin = get_admin_client()

    try:
        auth_response = auth.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:
        raise AuthError("E-mail ou senha inválidos.") from exc

    if not auth_response.user:
        raise AuthError("Não foi possível autenticar o usuário.")

    user_id = str(auth_response.user.id)
    profile_response = (
        admin.table("profiles")
        .select("id,full_name,email,phone,role,status,access_level,can_manage_users")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )

    if not profile_response.data:
        raise AuthError("Usuário autenticado, mas sem perfil interno cadastrado.")

    profile = profile_response.data[0]
    if profile.get("status") != "active":
        raise AuthError("Usuário inativo.")

    raw_token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.session_hours)

    admin.table("app_sessions").insert(
        {
            "token_hash": _hash_token(raw_token),
            "user_id": user_id,
            "expires_at": expires_at.isoformat(),
        }
    ).execute()

    return raw_token, profile


def get_session_user(raw_token: str | None) -> dict | None:
    if not raw_token:
        return None

    settings = get_settings()
    if settings.demo_mode:
        user_id = DEMO_SESSIONS.get(_hash_token(raw_token))
        if user_id == DEMO_USER_ID:
            return _demo_user()
        return next((p for p in DEMO_INTERNAL_USERS if p["id"] == user_id and p.get("status") == "active"), None)

    admin = get_admin_client()
    now = datetime.now(timezone.utc).isoformat()

    session_response = (
        admin.table("app_sessions")
        .select("user_id,expires_at")
        .eq("token_hash", _hash_token(raw_token))
        .gt("expires_at", now)
        .limit(1)
        .execute()
    )
    if not session_response.data:
        return None

    user_id = session_response.data[0]["user_id"]
    profile_response = (
        admin.table("profiles")
        .select("id,full_name,email,phone,role,status,access_level,can_manage_users")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    if not profile_response.data:
        return None

    profile = profile_response.data[0]
    return profile if profile.get("status") == "active" else None



def csrf_token_for_session(raw_token: str | None) -> str:
    if not raw_token:
        return ""
    key = get_settings().secret_key.encode("utf-8")
    message = f"vendra-csrf:{raw_token}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def verify_csrf_token(raw_token: str | None, supplied: str | None) -> bool:
    if not raw_token or not supplied:
        return False
    expected = csrf_token_for_session(raw_token)
    return hmac.compare_digest(expected, supplied)

def logout(raw_token: str | None) -> None:
    if not raw_token:
        return
    if get_settings().demo_mode:
        DEMO_SESSIONS.pop(_hash_token(raw_token), None)
        return
    get_admin_client().table("app_sessions").delete().eq("token_hash", _hash_token(raw_token)).execute()

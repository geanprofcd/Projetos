from fastapi import HTTPException, Request, status

from app.services.auth_service import COOKIE_NAME, get_session_user


def current_user(request: Request) -> dict:
    user = getattr(request.state, 'vendra_user', None)
    if not user:
        user = get_session_user(request.cookies.get(COOKIE_NAME))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
    return user


def internal_user(user: dict) -> dict:
    if user.get("role") not in {"responsavel", "administrador"}:
        raise HTTPException(status_code=403, detail="Acesso restrito à equipe interna.")
    return user

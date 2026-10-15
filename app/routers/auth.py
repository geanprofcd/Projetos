from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.core.ui import templates
from app.services.auth_service import COOKIE_NAME, AuthError, authenticate, logout


router = APIRouter()


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        session_token, _ = authenticate(email=email, password=password)
    except AuthError as exc:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": str(exc), "email": email},
            status_code=401,
        )

    settings = get_settings()
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        max_age=settings.session_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure or settings.is_production,
        samesite="lax",
    )
    return response


@router.post("/logout")
def logout_route(request: Request):
    logout(request.cookies.get(COOKIE_NAME))
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response

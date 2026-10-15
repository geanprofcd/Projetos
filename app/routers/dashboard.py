from fastapi import APIRouter, Depends, Request

from app.core.ui import templates
from app.dependencies.auth import current_user
from app.services.ticket_service import dashboard_metrics
from app.services.metrics_service import service_metrics
from app.services.commercial_metrics_service import commercial_indicators
from app.services.access_service import level_for


router = APIRouter()


@router.get("/")
def dashboard(request: Request, user: dict = Depends(current_user)):
    if level_for(user) == 'comum':
        return templates.TemplateResponse(request=request, name='access_home.html', context={'user':user,'active_page':'dashboard'})
    metrics = dashboard_metrics(user)
    metrics.update(service_metrics(user))
    commercial = commercial_indicators() if level_for(user) in {"gerencial", "administrativo"} else None
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"user": user, "metrics": metrics, "commercial": commercial, "active_page": "dashboard"},
    )

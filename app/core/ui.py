from fastapi.templating import Jinja2Templates


templates = Jinja2Templates(directory="app/templates")

from app.services.access_service import allowed, level_for
from app.services.ticket_attention_service import date_br, time_br, datetime_br
from app.core.config import get_settings
templates.env.globals.update(allowed=allowed, level_for=level_for, vendra_environment=get_settings().app_env)
templates.env.filters.update(date_br=date_br, time_br=time_br, datetime_br=datetime_br)

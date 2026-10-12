from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import path
from django.views.generic import RedirectView

from .api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", api.urls),
]

if settings.DEBUG:
    # uvicorn does not serve static files the way `runserver` does, so the Swagger UI and
    # admin assets 404 without this. In deployment Caddy serves /static from collectstatic,
    # and "/" belongs to the React app.
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns.append(path("", RedirectView.as_view(url="/api/v1/docs", permanent=False)))

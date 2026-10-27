from django.contrib import admin
from django.urls import include, path
from core.views import health, home, service_worker

urlpatterns = [
    path("health/", health, name="health"),
    path("sw.js", service_worker, name="service_worker"),
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("", include("schools.urls")),
]

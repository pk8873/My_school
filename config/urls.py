from django.contrib import admin
from django.urls import include, path
from core.views import health, home

urlpatterns = [path("health/", health, name="health"), path("admin/", admin.site.urls), path("", home, name="home"), path("", include("schools.urls"))]

from pathlib import Path

from django.db import DatabaseError, connection
from django.http import FileResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

BASE_DIR = Path(__file__).resolve().parent.parent


@require_GET
def health(request):
    """Return service health only when the configured database can answer a query."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        response = JsonResponse(
            {"status": "unhealthy", "database": "unavailable"},
            status=503,
        )
    else:
        response = JsonResponse({"status": "ok", "database": "ok"})

    # Monitoring responses should not be cached by browsers or proxies.
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def service_worker(request):
    worker = BASE_DIR / "static" / "pwa" / "sw.js"
    response = FileResponse(open(worker, "rb"), content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "public/home.html")

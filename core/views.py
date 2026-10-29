from pathlib import Path

from django.http import FileResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

BASE_DIR = Path(__file__).resolve().parent.parent


@require_GET
def health(request):
    return JsonResponse({"status": "ok"})


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

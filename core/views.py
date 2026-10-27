from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET

@require_GET
def health(request):
    return JsonResponse({"status": "ok"})

def home(request):
    return redirect("dashboard" if request.user.is_authenticated else "login")

from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("classes/", views.classrooms, name="classrooms"),
    path("students/", views.students, name="students"),
    path("attendance/", views.attendance, name="attendance"),
    path("fees/", views.fees, name="fees"),
    path("academics/", views.academics, name="academics"),
    path("timetable/", views.timetable, name="timetable"),
    path("reports/<str:report>.csv", views.export_csv, name="export_csv"),
    path("platform/", views.platform_admin, name="platform_admin"),
    path("staff/", views.staff_management, name="staff_management"),
]

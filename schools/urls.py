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
    path("students/<int:student_id>/report-card.pdf", views.student_report_card_pdf, name="student_report_card_pdf"),
    path("students/<int:student_id>/fee-statement.pdf", views.student_fee_statement_pdf, name="student_fee_statement_pdf"),
    path("academics/", views.academics, name="academics"),
    path("homework/<int:homework_id>/submit/", views.homework_submit, name="homework_submit"),
    path("homework/submissions/<int:submission_id>/review/", views.homework_review, name="homework_review"),
    path("timetable/", views.timetable, name="timetable"),
    path("reports/<str:report>.csv", views.export_csv, name="export_csv"),
    path("platform/", views.platform_admin, name="platform_admin"),
    path("staff/", views.staff_management, name="staff_management"),
]

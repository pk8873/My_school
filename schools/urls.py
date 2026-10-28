from django.contrib.auth import views as auth_views
from django.urls import path
from . import views
from .fee_receipts import fee_payment_receipt_pdf

urlpatterns = [
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("classes/", views.classrooms, name="classrooms"),
    path("students/", views.students, name="students"),
    path("students/transfer-certificate/", views.student_transfer_certificate_draft, name="student_transfer_certificate_draft"),
    path("students/transfer-certificates/", views.transfer_certificate_register, name="transfer_certificate_register"),
    path("students/promotions/", views.student_promotions, name="student_promotions"),
    path("students/id-cards.pdf", views.student_id_cards_pdf, name="student_id_cards_pdf"),
    path("students/import/", views.import_students_csv, name="import_students_csv"),
    path("attendance/", views.attendance, name="attendance"),
    path("attendance/report.pdf", views.attendance_report_pdf, name="attendance_report_pdf"),
    path("attendance/bulk/", views.attendance_bulk, name="attendance_bulk"),
    path("attendance/history/", views.attendance_history, name="attendance_history"),
    path("fees/", views.fees, name="fees"),
    path("fees/<int:fee_id>/payments/", views.fee_payment_history, name="fee_payment_history"),
    path("fees/payments/<int:payment_id>/receipt.pdf", fee_payment_receipt_pdf, name="fee_payment_receipt_pdf"),
    path("fees/<int:fee_id>/receipt.pdf", views.fee_collection_receipt_pdf, name="fee_collection_receipt_pdf"),
    path("students/<int:student_id>/report-card.pdf", views.student_report_card_pdf, name="student_report_card_pdf"),
    path("students/<int:student_id>/fee-statement.pdf", views.student_fee_statement_pdf, name="student_fee_statement_pdf"),
    path("academics/", views.academics, name="academics"),
    path("homework/<int:homework_id>/submit/", views.homework_submit, name="homework_submit"),
    path("homework/submissions/<int:submission_id>/review/", views.homework_review, name="homework_review"),
    path("timetable/", views.timetable, name="timetable"),
    path("reports/<str:report>.csv", views.export_csv, name="export_csv"),
    path("platform/", views.platform_admin, name="platform_admin"),
    path("staff/", views.staff_management, name="staff_management"),
    path("staff/attendance/", views.staff_attendance, name="staff_attendance"),
    path("staff/leave/", views.staff_leave, name="staff_leave"),
]

"""Tenant-scoped CSV export bundle for school administrators.

This is a portability export, not a complete database backup. It deliberately
excludes authentication secrets, uploaded file contents, and platform-wide data.
"""
import csv
import io
import json
import zipfile
from datetime import datetime

from django.utils import timezone

from .models import (
    Announcement, AttendanceChangeLog, AttendanceRecord, ClassRoom, Exam,
    ExamResult, FeePayment, FeeRecord, Homework, HomeworkSubmission,
    ParentStudentLink, SchoolEvent, SchoolEventRSVP, StaffAttendance,
    StaffLeaveRequest, Student, StudentClassHistory, TimetableSlot,
    TransferCertificate,
)


def _safe_csv_cell(value):
    """Reduce spreadsheet formula injection risk in exported text cells."""
    if value is None:
        return ""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def _csv_bytes(headers, rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow(headers)
    count = 0
    for row in rows:
        writer.writerow([_safe_csv_cell(value) for value in row])
        count += 1
    return stream.getvalue().encode("utf-8-sig"), count


def build_school_export(school):
    """Return a ZIP of CSVs containing records for exactly one school."""
    datasets = [
        ("students.csv", ["admission_number", "first_name", "last_name", "date_of_birth", "class_name", "section", "academic_year", "active", "admitted_at"],
         Student.objects.filter(school=school).select_related("classroom").order_by("admission_number"),
         lambda x: [x.admission_number, x.first_name, x.last_name, x.date_of_birth, x.classroom.name, x.classroom.section, x.classroom.academic_year, x.is_active, x.admitted_at]),
        ("classes.csv", ["name", "section", "academic_year", "capacity", "active", "class_teacher_username"],
         ClassRoom.objects.filter(school=school).select_related("class_teacher").order_by("academic_year", "name", "section"),
         lambda x: [x.name, x.section, x.academic_year, x.capacity, x.is_active, x.class_teacher.username if x.class_teacher_id else ""]),
        ("attendance.csv", ["admission_number", "student_name", "date", "status", "note", "marked_by_username"],
         AttendanceRecord.objects.filter(school=school).select_related("student", "marked_by").order_by("date", "student__admission_number"),
         lambda x: [x.student.admission_number, str(x.student), x.date, x.status, x.note, x.marked_by.username if x.marked_by_id else ""]),
        ("attendance_change_log.csv", ["attendance_date", "admission_number", "student_name", "old_status", "new_status", "old_note", "new_note", "changed_by_username", "changed_at"],
         AttendanceChangeLog.objects.filter(school=school).select_related("changed_by").order_by("attendance_date", "changed_at"),
         lambda x: [x.attendance_date, x.admission_number, x.student_name, x.old_status, x.new_status, x.old_note, x.new_note, x.changed_by.username if x.changed_by_id else "", x.changed_at]),
        ("fees.csv", ["admission_number", "student_name", "title", "amount", "paid_amount", "balance", "due_date", "status", "payment_reference", "note", "created_at"],
         FeeRecord.objects.filter(school=school).select_related("student").order_by("student__admission_number", "due_date"),
         lambda x: [x.student.admission_number, str(x.student), x.title, x.amount, x.paid_amount, x.balance, x.due_date, x.status, x.payment_reference, x.note, x.created_at]),
        ("fee_payments.csv", ["admission_number", "student_name", "fee_title", "amount", "payment_date", "method", "reference", "note", "recorded_by_username", "created_at"],
         FeePayment.objects.filter(school=school).select_related("fee_record__student", "recorded_by").order_by("payment_date", "created_at"),
         lambda x: [x.fee_record.student.admission_number, str(x.fee_record.student), x.fee_record.title, x.amount, x.payment_date, x.method, x.reference, x.note, x.recorded_by.username if x.recorded_by_id else "", x.created_at]),
        ("exams.csv", ["title", "class_name", "section", "exam_date", "max_marks", "created_by_username"],
         Exam.objects.filter(school=school).select_related("classroom", "created_by").order_by("exam_date", "title"),
         lambda x: [x.title, x.classroom.name if x.classroom_id else "", x.classroom.section if x.classroom_id else "", x.exam_date, x.max_marks, x.created_by.username if x.created_by_id else ""]),
        ("exam_results.csv", ["exam_title", "admission_number", "student_name", "marks_obtained", "max_marks", "percentage", "remarks", "entered_by_username"],
         ExamResult.objects.filter(school=school).select_related("exam", "student", "entered_by").order_by("exam__exam_date", "student__admission_number"),
         lambda x: [x.exam.title, x.student.admission_number, str(x.student), x.marks_obtained, x.exam.max_marks, x.percentage, x.remarks, x.entered_by.username if x.entered_by_id else ""]),
        ("homework.csv", ["title", "class_name", "section", "instructions", "assigned_date", "due_date", "published", "assigned_by_username"],
         Homework.objects.filter(school=school).select_related("classroom", "assigned_by").order_by("assigned_date", "title"),
         lambda x: [x.title, x.classroom.name if x.classroom_id else "", x.classroom.section if x.classroom_id else "", x.instructions, x.assigned_date, x.due_date, x.is_published, x.assigned_by.username if x.assigned_by_id else ""]),
        ("homework_submissions.csv", ["homework_title", "admission_number", "student_name", "submission_text", "submitted_at", "status", "teacher_feedback", "graded_by_username", "graded_at"],
         HomeworkSubmission.objects.filter(school=school).select_related("homework", "student", "graded_by").order_by("submitted_at"),
         lambda x: [x.homework.title, x.student.admission_number, str(x.student), x.submission_text, x.submitted_at, x.status, x.teacher_feedback, x.graded_by.username if x.graded_by_id else "", x.graded_at]),
        ("parent_student_links.csv", ["parent_username", "parent_email", "admission_number", "student_name", "relationship", "can_view_fees", "can_view_results", "active"],
         ParentStudentLink.objects.filter(student__school=school).select_related("parent", "student").order_by("student__admission_number"),
         lambda x: [x.parent.username, x.parent.email, x.student.admission_number, str(x.student), x.relationship, x.can_view_fees, x.can_view_results, x.is_active]),
        ("staff_attendance.csv", ["staff_username", "staff_email", "date", "status", "note", "marked_by_username"],
         StaffAttendance.objects.filter(school=school).select_related("staff", "marked_by").order_by("date", "staff__username"),
         lambda x: [x.staff.username, x.staff.email, x.date, x.status, x.note, x.marked_by.username if x.marked_by_id else ""]),
        ("staff_leave.csv", ["staff_username", "start_date", "end_date", "reason", "status", "review_note", "reviewed_by_username", "reviewed_at"],
         StaffLeaveRequest.objects.filter(school=school).select_related("requester", "reviewed_by").order_by("start_date"),
         lambda x: [x.requester.username, x.start_date, x.end_date, x.reason, x.status, x.review_note, x.reviewed_by.username if x.reviewed_by_id else "", x.reviewed_at]),
        ("student_class_history.csv", ["admission_number", "student_name", "from_class", "from_section", "to_class", "to_section", "effective_date", "promoted_by_username", "note"],
         StudentClassHistory.objects.filter(school=school).select_related("student", "from_classroom", "to_classroom", "promoted_by").order_by("effective_date"),
         lambda x: [x.student.admission_number, str(x.student), x.from_classroom.name, x.from_classroom.section, x.to_classroom.name, x.to_classroom.section, x.effective_date, x.promoted_by.username if x.promoted_by_id else "", x.note]),
        ("transfer_certificates.csv", ["certificate_number", "admission_number", "student_name", "issue_date", "leaving_date", "reason", "conduct", "remarks", "status", "issued_by_username"],
         TransferCertificate.objects.filter(school=school).select_related("student", "issued_by").order_by("issue_date"),
         lambda x: [x.certificate_number, x.student.admission_number, str(x.student), x.issue_date, x.leaving_date, x.reason, x.conduct, x.remarks, x.status, x.issued_by.username if x.issued_by_id else ""]),
        ("announcements.csv", ["title", "body", "audience", "published", "published_at", "created_by_username"],
         Announcement.objects.filter(school=school).select_related("created_by").order_by("published_at"),
         lambda x: [x.title, x.body, x.audience, x.is_published, x.published_at, x.created_by.username if x.created_by_id else ""]),
        ("timetable.csv", ["class_name", "section", "subject", "teacher_username", "weekday", "start_time", "end_time", "room", "active"],
         TimetableSlot.objects.filter(school=school).select_related("classroom", "teacher").order_by("weekday", "start_time"),
         lambda x: [x.classroom.name, x.classroom.section, x.subject, x.teacher.username if x.teacher_id else "", x.weekday, x.start_time, x.end_time, x.room, x.is_active]),
        ("events.csv", ["title", "description", "starts_at", "ends_at", "location", "audience", "published", "created_by_username"],
         SchoolEvent.objects.filter(school=school).select_related("created_by").order_by("starts_at"),
         lambda x: [x.title, x.description, x.starts_at, x.ends_at, x.location, x.audience, x.is_published, x.created_by.username if x.created_by_id else ""]),
        ("event_rsvps.csv", ["event_title", "user_username", "user_email", "response", "updated_at"],
         SchoolEventRSVP.objects.filter(event__school=school).select_related("event", "user").order_by("event__starts_at"),
         lambda x: [x.event.title, x.user.username, x.user.email, x.response, x.updated_at]),
    ]

    manifest = {
        "school": school.name,
        "school_slug": school.slug,
        "generated_at": timezone.now().isoformat(),
        "timezone": timezone.get_current_timezone_name(),
        "format": "CSV files encoded as UTF-8 with BOM",
        "scope": "Records filtered to this school; not a full database backup",
        "files": {},
        "excluded": ["passwords and authentication secrets", "uploaded file contents", "platform-wide records"],
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, headers, queryset, row_builder in datasets:
            data, count = _csv_bytes(headers, (row_builder(item) for item in queryset.iterator(chunk_size=1000)))
            archive.writestr(filename, data)
            manifest["files"][filename] = {"rows": count, "encoding": "UTF-8-SIG"}
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
    return output.getvalue()

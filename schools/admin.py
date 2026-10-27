from django.contrib import admin
from .models import AttendanceRecord, ClassRoom, FeeRecord, Membership, ParentStudentLink, School, Student


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    search_fields = ("name", "slug", "email")
    list_filter = ("is_active",)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "school", "role", "is_active")
    list_filter = ("school", "role", "is_active")
    search_fields = ("user__username", "school__name")


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ("name", "section", "school", "academic_year", "is_active")
    list_filter = ("school", "academic_year", "is_active")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("admission_number", "first_name", "last_name", "school", "classroom", "is_active")
    list_filter = ("school", "classroom", "is_active")
    search_fields = ("admission_number", "first_name", "last_name")


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("student", "school", "date", "status", "marked_by")
    list_filter = ("school", "date", "status")
    search_fields = ("student__first_name", "student__last_name", "student__admission_number")


@admin.register(FeeRecord)
class FeeRecordAdmin(admin.ModelAdmin):
    list_display = ("student", "school", "title", "amount", "paid_amount", "due_date", "status")
    list_filter = ("school", "status", "due_date")
    search_fields = ("student__first_name", "student__last_name", "student__admission_number", "payment_reference")


admin.site.register(ParentStudentLink)

from .models import Announcement, Exam, ExamResult, Homework

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ("title", "school", "classroom", "exam_date", "max_marks")
    list_filter = ("school", "exam_date")
    search_fields = ("title",)


@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_display = ("exam", "student", "marks_obtained", "entered_by")
    list_filter = ("school", "exam")
    search_fields = ("student__first_name", "student__last_name", "exam__title")


@admin.register(Homework)
class HomeworkAdmin(admin.ModelAdmin):
    list_display = ("title", "school", "classroom", "assigned_date", "due_date", "is_published")
    list_filter = ("school", "is_published", "assigned_date")
    search_fields = ("title", "instructions")


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "school", "audience", "is_published", "published_at")
    list_filter = ("school", "audience", "is_published")
    search_fields = ("title", "body")

from .models import TimetableSlot

@admin.register(TimetableSlot)
class TimetableSlotAdmin(admin.ModelAdmin):
    list_display = ("weekday", "start_time", "end_time", "classroom", "subject", "teacher", "school", "is_active")
    list_filter = ("school", "weekday", "is_active")
    search_fields = ("subject", "classroom__name", "teacher__username")

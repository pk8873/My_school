from django.contrib import admin
from .models import ClassRoom, Membership, ParentStudentLink, School, Student
@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    search_fields = ("name", "slug", "email")
    list_filter = ("is_active",)
@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "school", "role", "is_active")
    list_filter = ("school", "role", "is_active")
@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ("name", "section", "school", "academic_year", "is_active")
    list_filter = ("school", "academic_year", "is_active")
@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("admission_number", "first_name", "last_name", "school", "classroom", "is_active")
    list_filter = ("school", "classroom", "is_active")
    search_fields = ("admission_number", "first_name", "last_name")
admin.site.register(ParentStudentLink)

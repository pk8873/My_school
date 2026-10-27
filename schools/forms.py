from django import forms
from django.contrib.auth import get_user_model
from .models import AttendanceRecord, ClassRoom, FeeRecord, Student


class BootstrapModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + (" form-select" if isinstance(field.widget, forms.Select) else " form-control")).strip()


class ClassRoomForm(BootstrapModelForm):
    class Meta:
        model = ClassRoom
        fields = ["name", "section", "academic_year", "class_teacher", "capacity", "is_active"]


class StudentForm(BootstrapModelForm):
    class Meta:
        model = Student
        fields = ["classroom", "admission_number", "first_name", "last_name", "date_of_birth", "admitted_at", "is_active"]
        widgets = {"date_of_birth": forms.DateInput(attrs={"type": "date"}), "admitted_at": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, school, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["classroom"].queryset = ClassRoom.objects.filter(school=school, is_active=True)


class AttendanceRecordForm(BootstrapModelForm):
    class Meta:
        model = AttendanceRecord
        fields = ["student", "date", "status", "note"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, school, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = Student.objects.filter(school=school, is_active=True)


class FeeRecordForm(BootstrapModelForm):
    class Meta:
        model = FeeRecord
        fields = ["student", "title", "amount", "paid_amount", "due_date", "status", "payment_reference", "note"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, school, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = Student.objects.filter(school=school, is_active=True)
        self.fields["amount"].widget.attrs.update({"min": "0", "step": "0.01"})
        self.fields["paid_amount"].widget.attrs.update({"min": "0", "step": "0.01"})

from .models import Announcement, Exam, ExamResult, Homework


class ExamForm(BootstrapModelForm):
    class Meta:
        model = Exam
        fields = ["title", "classroom", "exam_date", "max_marks"]
        widgets = {"exam_date": forms.DateInput(attrs={"type": "date"}), "max_marks": forms.NumberInput(attrs={"min": "1", "step": "0.01"})}

    def __init__(self, *args, school, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["classroom"].queryset = ClassRoom.objects.filter(school=school, is_active=True)
        self.fields["classroom"].required = False


class ExamResultForm(BootstrapModelForm):
    class Meta:
        model = ExamResult
        fields = ["exam", "student", "marks_obtained", "remarks"]
        widgets = {"marks_obtained": forms.NumberInput(attrs={"min": "0", "step": "0.01"})}

    def __init__(self, *args, school, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["exam"].queryset = Exam.objects.filter(school=school)
        self.fields["student"].queryset = Student.objects.filter(school=school, is_active=True)


class HomeworkForm(BootstrapModelForm):
    class Meta:
        model = Homework
        fields = ["classroom", "title", "instructions", "assigned_date", "due_date", "is_published"]
        widgets = {"assigned_date": forms.DateInput(attrs={"type": "date"}), "due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, school, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["classroom"].queryset = ClassRoom.objects.filter(school=school, is_active=True)
        self.fields["classroom"].required = False


class AnnouncementForm(BootstrapModelForm):
    class Meta:
        model = Announcement
        fields = ["title", "body", "audience", "is_published"]


from .models import TimetableSlot


class TimetableSlotForm(BootstrapModelForm):
    class Meta:
        model = TimetableSlot
        fields = ["classroom", "subject", "teacher", "weekday", "start_time", "end_time", "room", "is_active"]
        widgets = {"start_time": forms.TimeInput(attrs={"type": "time"}), "end_time": forms.TimeInput(attrs={"type": "time"})}

    def __init__(self, *args, school, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["classroom"].queryset = ClassRoom.objects.filter(school=school, is_active=True)
        self.fields["teacher"].queryset = get_user_model().objects.filter(school_memberships__school=school, school_memberships__role="teacher", school_memberships__is_active=True).distinct()
        self.fields["teacher"].required = False

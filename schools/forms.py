from django import forms
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

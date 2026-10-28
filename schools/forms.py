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


from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import Membership, ParentStudentLink, School, SchoolSubscription


class SchoolOnboardingForm(BootstrapModelForm):
    admin_username = forms.CharField(max_length=150)
    admin_email = forms.EmailField()
    admin_password = forms.CharField(min_length=8, widget=forms.PasswordInput)
    plan = forms.ChoiceField(choices=SchoolSubscription.Plan.choices)
    student_limit = forms.IntegerField(min_value=1, max_value=100000, initial=100)
    trial_days = forms.IntegerField(min_value=0, max_value=365, initial=14)

    class Meta:
        model = School
        fields = ["name", "slug", "email", "phone", "address", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ["admin_password"]:
            self.fields[name].widget.attrs["autocomplete"] = "new-password"

    def clean_admin_username(self):
        username = self.cleaned_data["admin_username"].strip()
        if get_user_model().objects.filter(username=username).exists():
            raise forms.ValidationError("That username is already in use.")
        return username

    def clean_slug(self):
        slug = self.cleaned_data["slug"].strip().lower()
        if School.objects.filter(slug=slug).exists():
            raise forms.ValidationError("That school slug is already in use.")
        return slug

    def save(self, *, created_by=None):
        from django.db import transaction
        User = get_user_model()
        with transaction.atomic():
            school = super().save(commit=False)
            school.full_clean()
            school.save()
            user = User.objects.create_user(
                username=self.cleaned_data["admin_username"],
                email=self.cleaned_data["admin_email"],
                password=self.cleaned_data["admin_password"],
            )
            Membership.objects.create(user=user, school=school, role=Membership.Role.SCHOOL_ADMIN)
            SchoolSubscription.objects.create(
                school=school,
                plan=self.cleaned_data["plan"],
                status=SchoolSubscription.Status.TRIAL if self.cleaned_data["trial_days"] else SchoolSubscription.Status.ACTIVE,
                student_limit=self.cleaned_data["student_limit"],
                trial_ends_at=timezone.localdate() + timedelta(days=self.cleaned_data["trial_days"]) if self.cleaned_data["trial_days"] else None,
            )
        return school


class StaffAccountForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    password = forms.CharField(min_length=8, widget=forms.PasswordInput)
    role = forms.ChoiceField(choices=[
        (Membership.Role.PRINCIPAL, "Principal"),
        (Membership.Role.TEACHER, "Teacher"),
        (Membership.Role.ACCOUNTANT, "Accountant"),
        (Membership.Role.PARENT, "Parent"),
        (Membership.Role.STUDENT, "Student"),
    ])

    def __init__(self, *args, school, **kwargs):
        super().__init__(*args, **kwargs)
        self.school = school
        for field in self.fields.values():
            field.widget.attrs["class"] = (field.widget.attrs.get("class", "") + (" form-select" if isinstance(field.widget, forms.Select) else " form-control")).strip()

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if get_user_model().objects.filter(username=username).exists():
            raise forms.ValidationError("That username is already in use.")
        return username

    def save(self):
        from django.db import transaction
        User = get_user_model()
        with transaction.atomic():
            user = User.objects.create_user(
                username=self.cleaned_data["username"],
                email=self.cleaned_data["email"],
                first_name=self.cleaned_data["first_name"],
                last_name=self.cleaned_data["last_name"],
                password=self.cleaned_data["password"],
            )
            Membership.objects.create(user=user, school=self.school, role=self.cleaned_data["role"])
        return user


class ParentStudentLinkForm(BootstrapModelForm):
    parent_username = forms.CharField(max_length=150, label="Existing parent username")

    class Meta:
        model = ParentStudentLink
        fields = ["student", "relationship", "can_view_fees", "can_view_results", "is_active"]

    def __init__(self, *args, school, **kwargs):
        super().__init__(*args, **kwargs)
        self.school = school
        self.fields["student"].queryset = Student.objects.filter(school=school, is_active=True)

    def clean_parent_username(self):
        username = self.cleaned_data["parent_username"].strip()
        User = get_user_model()
        try:
            parent = User.objects.get(username=username)
        except User.DoesNotExist:
            raise forms.ValidationError("No account exists with this username.")
        if not parent.school_memberships.filter(school=self.school, role=Membership.Role.PARENT, is_active=True).exists():
            raise forms.ValidationError("This account must have an active Parent role in this school.")
        return username

    def save(self, *, school):
        User = get_user_model()
        parent = User.objects.get(username=self.cleaned_data["parent_username"])
        link, _ = ParentStudentLink.objects.update_or_create(
            parent=parent,
            student=self.cleaned_data["student"],
            defaults={
                "relationship": self.cleaned_data["relationship"],
                "can_view_fees": self.cleaned_data["can_view_fees"],
                "can_view_results": self.cleaned_data["can_view_results"],
                "is_active": self.cleaned_data["is_active"],
            },
        )
        return link


class StudentAccountLinkForm(forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.none(), label="Student profile")
    student_username = forms.CharField(max_length=150, label="Existing student username")

    def __init__(self, *args, school, **kwargs):
        super().__init__(*args, **kwargs)
        self.school = school
        self.fields["student"].queryset = Student.objects.filter(school=school, is_active=True)
        for field in self.fields.values():
            field.widget.attrs["class"] = (field.widget.attrs.get("class", "") + (" form-select" if isinstance(field.widget, forms.Select) else " form-control")).strip()

    def clean_student_username(self):
        username = self.cleaned_data["student_username"].strip()
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise forms.ValidationError("No account exists with this username.")
        if not user.school_memberships.filter(school=self.school, role=Membership.Role.STUDENT, is_active=True).exists():
            raise forms.ValidationError("This account must have an active Student role in this school.")
        return username

    def clean(self):
        cleaned = super().clean()
        student = cleaned.get("student")
        username = cleaned.get("student_username")
        if student and username:
            User = get_user_model()
            user = User.objects.get(username=username)
            if Student.objects.filter(portal_user=user).exclude(pk=student.pk).exists():
                self.add_error("student_username", "This account is already linked to another student.")
            if student.portal_user_id and student.portal_user.username != username:
                self.add_error("student", "This student profile is already linked to another account.")
        return cleaned

    def save(self):
        User = get_user_model()
        student = self.cleaned_data["student"]
        student.portal_user = User.objects.get(username=self.cleaned_data["student_username"])
        student.save(update_fields=["portal_user"])
        return student


class SubscriptionUpdateForm(BootstrapModelForm):
    class Meta:
        model = SchoolSubscription
        fields = ["plan", "status", "student_limit", "trial_ends_at", "period_ends_at"]
        widgets = {
            "trial_ends_at": forms.DateInput(attrs={"type": "date"}),
            "period_ends_at": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student_limit"].widget.attrs.update({"min": "1"})



class HomeworkSubmissionForm(forms.ModelForm):
    class Meta:
        from .models import HomeworkSubmission
        model = HomeworkSubmission
        fields = ["submission_text"]
        widgets = {"submission_text": forms.Textarea(attrs={"rows": 3, "placeholder": "Write your answer or paste your work here..."})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["submission_text"].widget.attrs["class"] = "form-control"


class HomeworkFeedbackForm(forms.ModelForm):
    class Meta:
        from .models import HomeworkSubmission
        model = HomeworkSubmission
        fields = ["status", "teacher_feedback"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = ("form-select" if isinstance(field.widget, forms.Select) else "form-control")


class BulkAttendanceSelectionForm(forms.Form):
    classroom = forms.ModelChoiceField(queryset=ClassRoom.objects.none(), label="Class")
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, school, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["classroom"].queryset = ClassRoom.objects.filter(school=school, is_active=True)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"

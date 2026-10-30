from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .models import ClassRoom, Exam, ExamResult, Student
from .views import ACADEMIC_ROLES, get_membership, require_roles

MAX_BULK_STUDENTS = 500


@login_required
@require_http_methods(["GET", "POST"])
def bulk_exam_results(request):
    """Enter or update marks for one school-owned exam and one class atomically."""
    membership = get_membership(request)
    require_roles(membership, ACADEMIC_ROLES)
    school = membership.school

    exams = Exam.objects.filter(school=school).select_related("classroom")
    classrooms = ClassRoom.objects.filter(school=school, is_active=True)
    exam_id = request.POST.get("exam") if request.method == "POST" else request.GET.get("exam")
    classroom_id = request.POST.get("classroom") if request.method == "POST" else request.GET.get("classroom")
    exam = exams.filter(pk=exam_id).first() if exam_id else None
    if exam_id and exam is None:
        raise Http404("Exam not found.")

    classroom = None
    error = ""
    if exam and exam.classroom_id:
        classroom = exam.classroom
        if classroom_id and str(classroom.pk) != str(classroom_id):
            error = "This exam is assigned to a different class."
    elif classroom_id:
        classroom = classrooms.filter(pk=classroom_id).first()
        if classroom is None:
            error = "Choose a class belonging to your school."

    students = Student.objects.none()
    if exam and classroom and not error:
        students = Student.objects.filter(
            school=school, classroom=classroom, is_active=True
        ).order_by("first_name", "last_name", "pk")
    student_objects = list(students[: MAX_BULK_STUDENTS + 1])
    if len(student_objects) > MAX_BULK_STUDENTS:
        error = f"This class has more than {MAX_BULK_STUDENTS} active students."
        student_objects = []

    existing = {}
    if exam and student_objects:
        existing = {
            item.student_id: item
            for item in ExamResult.objects.filter(
                school=school, exam=exam,
                student_id__in=[student.pk for student in student_objects],
            )
        }

    if request.method == "POST" and not error:
        if exam is None:
            error = "Select an exam before saving marks."
        elif classroom is None:
            error = "Select the class whose marks you want to enter."
        elif not student_objects:
            error = "No active students were found for this exam and class."

        validated_results = []
        if not error:
            for student in student_objects:
                raw_marks = request.POST.get(f"marks_{student.pk}", "").strip()
                if not raw_marks:
                    continue
                try:
                    marks = Decimal(raw_marks)
                    if not marks.is_finite():
                        raise InvalidOperation
                except (InvalidOperation, ValueError):
                    error = f"Enter a valid mark for {student.first_name} {student.last_name}."
                    break

                result = existing.get(student.pk) or ExamResult(
                    school=school, exam=exam, student=student
                )
                result.school = school
                result.exam = exam
                result.student = student
                result.marks_obtained = marks
                result.remarks = request.POST.get(f"remarks_{student.pk}", "").strip()
                result.entered_by = request.user
                try:
                    result.full_clean()
                except ValidationError as exc:
                    details = exc.message_dict.values() if hasattr(exc, "message_dict") else [exc.messages]
                    detail = "; ".join(str(message) for group in details for message in group)
                    error = f"Invalid marks for {student.first_name} {student.last_name}: {detail}"
                    break
                validated_results.append(result)

        if not error and not validated_results:
            error = "Enter marks for at least one student before saving."

        if not error:
            try:
                with transaction.atomic():
                    Exam.objects.select_for_update().get(pk=exam.pk, school=school)
                    for result in validated_results:
                        result.save()
            except ValidationError as exc:
                error = "; ".join(exc.messages)
            except IntegrityError:
                error = "Another marks update was saved at the same time. Reload the page and review the latest results."
            else:
                messages.success(
                    request,
                    f"Saved marks for {len(validated_results)} students. Existing marks were updated where applicable.",
                )
                return redirect(
                    f"{request.path}?school={school.pk}&exam={exam.pk}&classroom={classroom.pk}"
                )

    if error:
        messages.error(request, error)

    if exam and student_objects:
        existing = {
            item.student_id: item
            for item in ExamResult.objects.filter(
                school=school, exam=exam,
                student_id__in=[student.pk for student in student_objects],
            )
        }
    student_rows = [
        {
            "student": student,
            "result": existing.get(student.pk),
            "input_marks": request.POST.get(f"marks_{student.pk}", "") if request.method == "POST" else "",
            "input_remarks": request.POST.get(f"remarks_{student.pk}", "") if request.method == "POST" else "",
        }
        for student in student_objects
    ]
    return render(request, "schools/bulk_exam_results.html", {
        "membership": membership,
        "exams": exams,
        "classrooms": classrooms,
        "selected_exam": exam,
        "selected_classroom": classroom,
        "student_rows": student_rows,
        "max_bulk_students": MAX_BULK_STUDENTS,
        "is_post": request.method == "POST",
    })

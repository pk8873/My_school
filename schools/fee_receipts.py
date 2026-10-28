"""PDF acknowledgements for individual manual fee-payment ledger entries."""
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.views.decorators.http import require_GET

from .models import FeePayment
from .views import FEE_ROLES, _build_pdf, get_membership, require_roles


@login_required
@require_GET
def fee_payment_receipt_pdf(request, payment_id):
    """Return a school-scoped receipt for one manually recorded payment."""
    membership = get_membership(request)
    require_roles(membership, FEE_ROLES)
    payment = FeePayment.objects.filter(
        pk=payment_id, school=membership.school,
        fee_record__school=membership.school,
    ).select_related("school", "fee_record", "fee_record__student", "fee_record__student__classroom", "recorded_by").first()
    if payment is None:
        raise Http404("Payment entry not found.")

    fee = payment.fee_record
    student = fee.student
    rows = [
        ["Field", "Recorded value"],
        ["Payment ID", f"PAY-{payment.pk:06d}"],
        ["Student", f"{student.first_name} {student.last_name}".strip()],
        ["Admission number", student.admission_number or "—"],
        ["Class", str(student.classroom)],
        ["Fee head", fee.title],
        ["Payment date", payment.payment_date.isoformat()],
        ["Amount recorded", f"INR {payment.amount:.2f}"],
        ["Method", payment.get_method_display()],
        ["Reference", payment.reference or "—"],
        ["Recorded by", payment.recorded_by.get_username() if payment.recorded_by else "—"],
        ["Fee total", f"INR {fee.amount:.2f}"],
        ["Current total paid", f"INR {fee.paid_amount:.2f}"],
        ["Current outstanding", f"INR {fee.balance:.2f}"],
        ["Note", payment.note or "—"],
    ]
    subtitle = (
        f"School: {membership.school.name} | Generated: {payment.created_at:%Y-%m-%d %H:%M} | "
        "MANUAL LEDGER ACKNOWLEDGEMENT — not a bank confirmation or proof of verified online payment"
    )
    return _build_pdf(
        "Individual Fee Payment Acknowledgement", subtitle, rows,
        filename=f"fee-payment-{payment.pk}.pdf",
    )

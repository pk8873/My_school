# School Saathi — हिन्दी सेटअप गाइड

## इस अपडेट में क्या शामिल है
यह अभी भी **development / early-access build** है, production-ready SaaS नहीं। इस चरण में शामिल हैं:

- Django login और school membership आधारित tenant selection.
- School, class, student और parent-student link data models.
- Responsive dashboard: student/class count, आज की attendance count, fee ledger summary और quick actions.
- School admin/principal के लिए class creation और student admission/search.
- School admin/principal/teacher के लिए daily attendance entry, date-wise register और class-wise bulk attendance marking; bulk save उसी class/date के मौजूदा records को update करता है. Bulk attendance creation/correction changes are recorded in a school-scoped audit history with old/new status and notes.
- School admin/principal/accountant के लिए fee ledger, manual fee collection record, partial payment balance, student/admission number/fee-head search, payment-status filter और unpaid balance वाले past-due records का overdue filter (school-scoped).
- Individual manual fee payment history: payment date, amount, method, reference, note और recorded-by; each payment updates the outstanding balance inside a database transaction and cannot exceed the remaining balance. This is a manual ledger, not a payment gateway; older paid amounts entered directly into the fee ledger do not automatically become individual payment rows.
- Exams, maximum marks, student results, percentage calculation and school/class-scoped exam selection.
- Weekly class timetable with subjects, teacher assignment, rooms, weekday grouping and time validation. School admins/principals manage the schedule; teachers see only assigned slots; students see their linked class; parents see linked children’s classes.
- Tenant-scoped CSV exports for student registers, attendance (date-filterable) and fee ledger, protected by role checks.
- Downloadable PDF student report cards and fee statements, with school isolation and parent/student record-level permissions. Manual fee collection acknowledgement PDF is available for fee entries with a recorded paid amount; it explicitly does not verify bank or online payment.
- Super Admin-only school onboarding that creates a tenant, its initial school-admin login and subscription plan metadata in one transaction; platform admin can edit plan/status/student limits (billing is not connected).
- School-scoped staff/parent/student account management, parent-child links with fee/result visibility flags, and staff-managed student portal account linking.
- Subscription plan/status metadata and student admission limits; this is not payment processing or automated subscription billing.
- Class-wise or school-wide homework assignments with due dates and publish control.
- Student text-based homework submission, teacher review status and written feedback, with school-scoped authorization.
- Repeatable synthetic demo-data command for a demo school, accounts, students, attendance, fees, exam results, homework, announcement and timetable. The command refuses to run with DEBUG=False.
- Audience-based school announcements for parents, students, staff or everyone.
- Combined Academics workspace with responsive cards, accessible form labels, helpful empty states and role-aware navigation.
- Attendance और fees के लिए Django Admin registration.
- Role-based access checks और tenant-filtered form choices/querysets.
- Responsive desktop/mobile layout, PWA manifest, static-only service worker cache. Authenticated pages/forms/student data cache नहीं होते.
- GitHub Actions checks/tests workflow.

## अभी बाकी महत्वपूर्ण modules
- Automated recurring billing, payment provider integration/webhooks and subscription lifecycle enforcement (Super Admin onboarding, plan metadata and student-limit checks are implemented; paid billing is not connected).
- Parent/student portal foundations: linked children’s attendance and fee summaries, linked student profile attendance/fee summaries, academic updates, class timetable and homework submissions.
- Payroll, staff attendance and staff self-service. Basic school-scoped account creation and staff/family directory are implemented.
- Bulk marks entry, homework file/photo uploads, push notifications and homework revision history. Text-based homework submission and teacher feedback are implemented.
- Attendance history audit trail bulk attendance updates के लिए शामिल है; attendance PDF exports और advanced report filters अभी बाकी हैं.
- Fee discounts, concessions, refunds, payment reconciliation and verified online payment gateway/webhooks. Manual fee acknowledgement PDF and individual manual payment history are implemented; gateway verification is not.
- Full CRUD edit/delete flows, password reset/email delivery, audit logs, backups/restore and monitoring.
- Dedicated school-scoped Django admin permissions, deployment review, accessibility review and end-to-end production tests.

## Windows PowerShell setup

Required: Python 3.12, Git and VS Code.

```powershell
git clone https://github.com/pk8873/My_school.git
cd My_school
py -0p
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test
python manage.py createsuperuser
python manage.py runserver
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, then activate the virtual environment again.

Open:
- App: http://127.0.0.1:8000/
- Sign in: http://127.0.0.1:8000/accounts/login/
- Dashboard: http://127.0.0.1:8000/dashboard/
- Admin: http://127.0.0.1:8000/admin/
- Health check: http://127.0.0.1:8000/health/

For a ready-made local demo, run `python manage.py seed_demo_data` after migrations. It creates only synthetic demo records and refuses to run with `DEBUG=False`. Newly created demo accounts use `DemoPass123!` and usernames `demo_admin`, `demo_teacher`, `demo_parent`, `demo_student`; existing accounts keep their existing passwords. Never expose demo accounts publicly. Alternatively, create a superuser and school membership manually. Use synthetic records only.

## Tenant security notes
Never trust a submitted school ID as authorization. Every school workflow must verify an active Membership and restrict all records to that school. Parent/student pages also need record-level authorization. Current Django Admin registrations are useful for local setup but do **not** implement school-specific admin isolation; do not grant untrusted school staff unrestricted Django Admin access.

## Production warning
Before a public launch, configure a strong `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, allowed hosts, trusted CSRF origins, HTTPS, PostgreSQL backups, email delivery, error monitoring, access reviews and a documented recovery process. Do not use real student data until security/privacy and legal requirements are reviewed. A PWA manifest/service worker does not mean all offline workflows are implemented. CI status must be checked after the latest commit; do not treat a pushed commit as proof of production readiness.

# School Saathi — हिन्दी सेटअप गाइड

## इस अपडेट में क्या शामिल है
यह अभी भी **development / early-access build** है, production-ready SaaS नहीं। इस चरण में शामिल हैं:

- Django login और school membership आधारित tenant selection.
- School, class, student और parent-student link data models.
- Responsive dashboard: student/class count, आज की attendance count, fee ledger summary और quick actions.
- School admin/principal के लिए class creation और student admission/search.
- School admin/principal/teacher के लिए daily attendance entry और date-wise register.
- School admin/principal/accountant के लिए fee ledger, manual fee collection record, partial payment balance.
- Attendance और fees के लिए Django Admin registration.
- Role-based access checks और tenant-filtered form choices/querysets.
- Responsive desktop/mobile layout, PWA manifest, static-only service worker cache. Authenticated pages/forms/student data cache नहीं होते.
- GitHub Actions checks/tests workflow.

## अभी बाकी महत्वपूर्ण modules
- Complete SaaS Super Admin dashboard, school onboarding, subscription plans/billing and usage limits.
- Full parent and student portals (attendance history, fee statements, exam results, notices, homework).
- Teacher/staff directory, staff permissions and payroll.
- Exams, marks, report cards, timetable, homework, announcements and messaging.
- Attendance bulk marking, edit/correction audit trail, PDF/CSV exports and report filters.
- Fee receipts/PDF, discounts, concessions, refunds, payment reconciliation and verified online payment gateway/webhooks.
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

After creating a superuser, create a School in Django Admin, then create a Membership linking your login user to that school with the `school_admin` role. Log in through the app to use the school pages. Use synthetic records for development.

## Tenant security notes
Never trust a submitted school ID as authorization. Every school workflow must verify an active Membership and restrict all records to that school. Parent/student pages also need record-level authorization. Current Django Admin registrations are useful for local setup but do **not** implement school-specific admin isolation; do not grant untrusted school staff unrestricted Django Admin access.

## Production warning
Before a public launch, configure a strong `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, allowed hosts, trusted CSRF origins, HTTPS, PostgreSQL backups, email delivery, error monitoring, access reviews and a documented recovery process. Do not use real student data until security/privacy and legal requirements are reviewed. A PWA manifest/service worker does not mean all offline workflows are implemented. CI status must be checked after the latest commit; do not treat a pushed commit as proof of production readiness.

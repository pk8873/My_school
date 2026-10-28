# School Saathi — हिन्दी सेटअप गाइड

## इस अपडेट में क्या शामिल है
यह अभी भी **development / early-access build** है, production-ready SaaS नहीं। इस चरण में शामिल हैं:

- Django login और school membership आधारित tenant selection; sign-in page से secure password reset flow, expiring single-use token और non-enumerating response.
- Password reset email configuration: local development में console backend; production में SMTP environment variables से configure किया जा सकता है.
- School, class, student और parent-student link data models.
- Responsive dashboard: student/class count, आज की attendance count, fee ledger summary और quick actions.
- School admin/principal के लिए class creation और student admission/search. Bulk student CSV import validates up to 500 rows atomically, checks school-local class/admission numbers and student plan limits, and never partially imports an invalid file. Student promotion/class transfer is also available for management roles: move up to 2,000 active students from one school class to another in one transaction, with per-student dated history and a note.
- School admin/principal/teacher के लिए daily attendance entry, date-wise register और class-wise bulk attendance marking; bulk save उसी class/date के मौजूदा records को update करता है. Bulk attendance creation/correction changes are recorded in a school-scoped audit history with old/new status and notes.
- School admin/principal/accountant के लिए fee ledger, manual fee collection record, partial payment balance, student/admission number/fee-head search, payment-status filter और unpaid balance वाले past-due records का overdue filter (school-scoped).
- Individual manual fee payment history with per-entry downloadable PDF acknowledgements and school-scoped CSV export. CSV exports can be filtered by fee entry, payment date range, payment method and student/admission/reference search. Receipts are school-scoped and role-protected, and state that they acknowledge a manual ledger entry rather than verify bank/online payment. Each new entry updates the outstanding balance inside a transaction and cannot exceed the remaining balance.
- Exams, maximum marks, student results, percentage calculation and school/class-scoped exam selection; academic staff can export school-scoped exam results to CSV with optional exam, class and exam-date range filters.
- Homework submission CSV export for academic staff, with homework, class, status and submission-date filters; includes review status and teacher feedback.
- Weekly class timetable with subjects, teacher assignment, rooms, weekday grouping and time validation. School admins/principals manage the schedule; teachers see only assigned slots; students see their linked class; parents see linked children’s classes.
- Tenant-scoped CSV exports for student registers, upcoming student birthdays (configurable 1–365 day window), attendance (single day or date range, optional class filter), attendance summary (marked-day totals, present/absent/late/leave counts and present-plus-late percentage, with date-range/class filters), low-attendance intervention lists (configurable percentage threshold and minimum marked days, with optional date-range/class filters), overdue fee lists (past-due pending/partial entries with outstanding balances, days overdue and optional class filter), fee ledger and individual fee payment entries (fee/date/method/search filters), plus fee collection summary grouped by payment date and method with transaction count and total collected; protected by role checks.
- Downloadable PDF attendance reports for academic staff (date range and optional class filter, capped at 2,000 records), PDF student report cards and fee statements with school isolation and parent/student record-level permissions, and printable student ID card sheets (up to 200 active students, optional class filter, management-role protected), and management-only school-scoped Transfer Certificate draft PDFs marked DRAFT (not stored as official issuance and must be verified before signing). A separate management-only Transfer Certificate register can issue a numbered PDF, record issuer/date/status, and cancel an entry while retaining its audit record; it also exports the school-scoped register to CSV with issued/cancelled filters and spreadsheet-formula neutralisation; verify and sign/seal certificates according to school policy before delivery. Manual fee collection acknowledgement PDF is available for fee entries with a recorded paid amount; it explicitly does not verify bank or online payment.
- Super Admin-only school onboarding that creates a tenant, its initial school-admin login and subscription plan metadata in one transaction; platform admin can edit plan/status/student limits (billing is not connected).
- School-scoped staff/parent/student account management, parent-child links with fee/result visibility flags, and staff-managed student portal account linking. School admins/principals can export a school-scoped staff/family/student account directory to CSV with optional role and active-status filters.
- Subscription plan/status metadata and student admission limits; this is not payment processing or automated subscription billing.
- Class-wise or school-wide homework assignments with due dates and publish control.
- Student text-based homework submission, teacher review status and written feedback, with school-scoped authorization.
- Repeatable synthetic demo-data command for a demo school, accounts, students, attendance, fees and four sample individual payment entries, exam results, homework, announcement and timetable. Demo payment rows sum to the sample paid amounts, are clearly marked synthetic, and the command refuses to run with DEBUG=False.
- Audience-based school announcements for parents, students, staff or everyone. A role-aware notification inbox tracks per-user read receipts. The school events calendar lets admins/principals publish dated events to everyone, parents, students or staff; event lists are school-scoped and audience-filtered. Parents, students and staff can RSVP as attending/not attending; users can update their own response, and school management can see response totals. School management can download a per-event RSVP CSV with formula-safe text fields; the export is restricted to management roles and the current school. The role-aware Notification Inbox shows published announcements, tracks per-user read receipts, and prevents users from marking announcements outside their permitted audience as read.
- Combined Academics workspace with responsive cards, accessible form labels, helpful empty states and role-aware navigation.
- Attendance और fees के लिए Django Admin registration.
- Role-based access checks और tenant-filtered form choices/querysets.
- Responsive desktop/mobile layout, PWA manifest, static-only service worker cache. Authenticated pages/forms/student data cache नहीं होते.
- GitHub Actions checks/tests workflow.

## अभी बाकी महत्वपूर्ण modules
- Automated recurring billing, payment provider integration/webhooks and subscription lifecycle enforcement (Super Admin onboarding, plan metadata and student-limit checks are implemented; paid billing is not connected).
- Parent/student portal foundations: linked children’s attendance and fee summaries, linked student profile attendance/fee summaries, academic updates, class timetable and homework submissions.
- Payroll अभी शामिल नहीं है. Staff attendance अब शामिल है: school admin/principal daily staff register mark/update कर सकते हैं; staff अपने attendance records देख सकते हैं; monthly Present/Absent/Late/Leave totals दिखते हैं. Staff leave self-service भी उपलब्ध है: teachers/accountants requests submit कर सकते हैं और school admins/principals review note के साथ approve/reject कर सकते हैं.
- Bulk marks entry, homework file/photo uploads, push notifications and homework revision history. Text-based homework submission and teacher feedback are implemented.
- Attendance history audit trail bulk attendance updates के लिए शामिल है; attendance CSV supports date ranges and optional class filter. Attendance PDF exports भी उपलब्ध हैं.
- Fee discounts, concessions, refunds, payment reconciliation and verified online payment gateway/webhooks. Individual manual payment PDF acknowledgements and payment history are implemented; gateway verification is not.
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


School events calendar supports search by title, description, and location, with upcoming/past/all date filters. Search results remain school-scoped and audience-filtered.


Family fee history: parent and student accounts can open `/my-fees/` to review school-scoped fee balances and manually recorded payment entries. Parents only see active linked children with `can_view_fees`; students only see their own portal-linked record. The page is read-only and does not process online payments. Existing fee statement/acknowledgement PDFs remain informational records, not bank verification.


## Password reset email setup (नया)
- Login page पर **Forgot your password?** link उपलब्ध है।
- Reset token Django के built-in password-reset flow से बनता है; link expiry `PASSWORD_RESET_TIMEOUT` से नियंत्रित होती है (default 24 घंटे)।
- Unknown email address पर भी वही confirmation page दिखता है, ताकि account existence reveal न हो।
- Local development में reset link PowerShell terminal में दिखाई देता है; email वास्तव में भेजा नहीं जाता।
- Production में `.env` या hosting environment में `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` और वास्तविक `DEFAULT_FROM_EMAIL` सेट करें। SMTP credentials को GitHub में commit न करें।
- Email delivery provider configuration के बिना production reset emails नहीं पहुँचेंगे। Deployment के बाद SMTP delivery और reset link का end-to-end test करें।


## School-wide data export (नया)
- School Admin और Principal के लिए **School data export** sidebar link उपलब्ध है।
- `/data-export.zip?school=<school-id>` एक ZIP डाउनलोड करता है जिसमें अलग-अलग CSV files और `manifest.json` शामिल हैं: students, classes, attendance and attendance change history, fee ledger/payments, exams/results, homework/submissions, parent-child links, staff attendance/leave, class history, transfer certificates, announcements, timetable, events और RSVPs।
- Export हर dataset को selected school के साथ scope करता है; Parent, Student, Teacher और Accountant roles को इस endpoint पर अनुमति नहीं है। School Admin/Principal access server-side role check से नियंत्रित है।
- CSV text cells में spreadsheet formula-injection risk कम करने के लिए basic escaping है। ZIP में credentials/passwords या uploaded file contents शामिल नहीं होते।
- **यह complete database backup नहीं है।** Restore, file attachments, auth users/permissions और full disaster recovery के लिए अलग verified backup/restore procedure आवश्यक है। ZIP में personal/student data है; इसे सुरक्षित स्थान पर रखें और केवल अधिकृत लोगों से साझा करें।

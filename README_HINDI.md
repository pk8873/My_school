# School Saathi — हिन्दी सेटअप गाइड

## वर्तमान स्थिति
यह पहला development scaffold है, पूर्ण या production-ready SaaS नहीं। अभी login, school membership, tenant-scoped शुरुआती dashboard, School/ClassRoom/Student/ParentStudentLink models, admin registration और tenant boundary tests का शुरुआती सेट है। Attendance, fees, exams, timetable, पूर्ण parent/student workflows, subscription billing, signed payment webhooks, notifications, PDF/CSV exports, PWA service worker और पूर्ण Super Admin अभी बाकी हैं।

## Windows PowerShell में setup

आवश्यक: Python 3.12, Git और VS Code।

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
python manage.py makemigrations schools
python manage.py migrate
python manage.py createsuperuser
python manage.py test
python manage.py runserver
```

अगर PowerShell activation रोकता है, उसी terminal session में चलाएं: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, फिर activation command दोबारा चलाएं। Browser में `http://127.0.0.1:8000/`, admin में `http://127.0.0.1:8000/admin/` और health check में `http://127.0.0.1:8000/health/` खोलें।

## Tenant सुरक्षा
Form से आए school ID को authorization न मानें। हर view में user की active Membership सत्यापित करें और queryset को उसी school तक सीमित रखें। Parent/student के लिए record-level authorization आवश्यक है। Django admin में मौजूदा registrations अभी school-scoped admin permissions लागू नहीं करते; production में school users को unrestricted admin access न दें।

## Production चेतावनी
`DJANGO_DEBUG=False`, मजबूत `DJANGO_SECRET_KEY`, `DATABASE_URL`, allowed hosts, HTTPS और PostgreSQL backups configure किए बिना public deployment न करें। वास्तविक student data इस्तेमाल न करें। इस GitHub connector से test suite execute नहीं की गई है; local PowerShell में commands चलाकर परिणाम सत्यापित करें।

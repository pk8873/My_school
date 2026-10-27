# School Saathi — Multi-School SaaS + PWA

A Django-based school management SaaS intended for multiple independent schools, with a school staff portal, parent/student PWA, and platform super-admin area.

## Project status

This repository started empty. The initial commit establishes project documentation. The application is not yet production-ready; modules will be added and verified incrementally. Do not use real student data or production credentials during development.

## Planned stack

- Python 3.12
- Django 5.2 LTS
- PostgreSQL
- Django Templates, Bootstrap 5, JavaScript
- Gunicorn + WhiteNoise
- Render web service and managed PostgreSQL
- PWA manifest and a conservative service worker that does not cache authenticated pages or sensitive responses

## Security principles

- Every school-owned record must be scoped to a school on the server.
- Authorization must be enforced for list, detail, create, update, delete, report, and export operations.
- Parents can access only explicitly linked children; students can access only their own records.
- Payment status is confirmed by a verified provider webhook, not a browser redirect.
- Secrets belong in environment variables; never commit `.env` or production credentials.
- A feature is not production-ready until its implementation and tests have been run and reviewed.

## Local development (planned)

Use Python 3.12 and PowerShell. See `README_HINDI.md` for Hindi setup instructions once the application scaffold is committed.

## License

No license has been selected yet. Do not assume permission to redistribute this repository until a license is added.
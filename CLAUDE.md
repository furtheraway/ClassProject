# ClassProject

Django 5 web app for a college class (~45 students) to post projects, form teams of 2–5,
and submit end-of-project reports with instructor-only peer reviews. Production target:
Azure App Service (Linux) + Azure Database for PostgreSQL, email via SendGrid (Anymail).

**Requirements live in [SPEC.md](SPEC.md) — read the relevant section before implementing
or changing a feature, and keep SPEC.md updated when requirements change.**

## Status

Milestones 1–3 complete (accounts/profiles; project board with CRUD,
cancel/reactivate, search, stats card + S-curve bonus score; applications,
memberships, eligibility guards, auto-fulfill/reopen, cancel releases team) —
all verified end-to-end 2026-07-02. Next: Milestone 4 (end-of-project reports
with required work URL + instructor-only peer reviews + CSV export via admin).
Build order = SPEC.md §10.

## Commands

Python 3.13 venv at `.venv` (Python 3.14 is also on the machine — always use the venv):

- `.\.venv\Scripts\python.exe manage.py runserver` — run locally (SQLite), http://127.0.0.1:8000
- `.\.venv\Scripts\python.exe manage.py makemigrations` / `migrate`
- `.\.venv\Scripts\python.exe manage.py test`
- Local instructor login for `/admin`: `instructor@example.com` (password known to John;
  local SQLite only, not committed)

## Conventions

- The owner (John) comes from ASP.NET Core / C#, new to Python and Django — when
  introducing a Django idiom, add a one-line explanation or C# analogy.
- Custom email-login `User` model (must exist before the first migration — never use
  `django.contrib.auth.models.User` directly).
- Configuration via environment variables (`django-environ`); secrets never committed.
  Local dev uses a git-ignored `.env`; production uses App Service settings.
- Business rules that must never regress: one group per student; one pending application
  per student; owners cancel before joining another project; peer reviews visible only
  in the admin (instructor).

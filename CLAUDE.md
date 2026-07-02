# ClassProject

Django 5 web app for a college class (~45 students) to post projects, form teams of 2–5,
and submit end-of-project reports with instructor-only peer reviews. Production target:
Azure App Service (Linux) + Azure Database for PostgreSQL, email via SendGrid (Anymail).

**Requirements live in [SPEC.md](SPEC.md) — read the relevant section before implementing
or changing a feature, and keep SPEC.md updated when requirements change.**

## Status

Spec agreed (v0.2); implementation not started. Build order = SPEC.md §10 milestones.

## Commands

To be filled in as the project scaffolds. Expected:

- `python manage.py runserver` — run locally (SQLite)
- `python manage.py makemigrations` / `migrate`
- `python manage.py test`

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

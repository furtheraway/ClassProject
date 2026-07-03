"""Template context available on every page (like _Layout view data in ASP.NET)."""

from projects.services import user_current_project


def current_project(request):
    """Exposes the user's active project so base.html can show "My report"."""
    if not request.user.is_authenticated:
        return {}
    return {"current_project": user_current_project(request.user)}

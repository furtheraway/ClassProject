from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Case, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ProjectForm
from .models import Project
from .services import current_bonus_score


def _owned_active_project(user, exclude_pk=None):
    qs = user.owned_projects.filter(status__in=Project.ACTIVE_STATUSES)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.first()


def _get_owned_project_or_403(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if project.owner != request.user:
        raise PermissionDenied
    return project


@login_required
def home(request):
    """Project list: open/fulfilled newest-first, cancelled at the bottom (SPEC §3.2)."""
    query = request.GET.get("q", "").strip()
    projects = (
        Project.objects.select_related("owner")
        .annotate(
            cancelled_last=Case(
                When(status=Project.Status.CANCELLED, then=Value(1)), default=Value(0)
            )
        )
        .order_by("cancelled_last", "-created_at")
    )
    if query:
        projects = projects.filter(
            Q(title__icontains=query)
            | Q(keywords__icontains=query)
            | Q(description__icontains=query)
        )
    active_count = Project.objects.filter(status__in=Project.ACTIVE_STATUSES).count()
    context = {
        "projects": projects,
        "query": query,
        "project_count": active_count,
        "bonus_score": current_bonus_score(active_count),
        "user_active_project": _owned_active_project(request.user),
    }
    return render(request, "projects/home.html", context)


@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project.objects.select_related("owner"), pk=pk)
    return render(request, "projects/project_detail.html", {"project": project})


@login_required
def project_create(request):
    # SPEC §3.2: one active project per owner. (Milestone 3 adds the
    # "not a member of someone else's project" check once memberships exist.)
    active = _owned_active_project(request.user)
    if active:
        messages.error(
            request, "You already have an active project — cancel it before posting a new one."
        )
        return redirect("project-detail", pk=active.pk)
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            messages.success(request, "Your project is posted!")
            return redirect("project-detail", pk=project.pk)
    else:
        form = ProjectForm(initial={"contact_info": request.user.email})
    return render(request, "projects/project_form.html", {"form": form, "is_new": True})


@login_required
def project_edit(request, pk):
    project = _get_owned_project_or_403(request, pk)
    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, "Project updated.")
            return redirect("project-detail", pk=project.pk)
    else:
        form = ProjectForm(instance=project)
    return render(
        request, "projects/project_form.html", {"form": form, "is_new": False, "project": project}
    )


@login_required
@require_POST
def project_cancel(request, pk):
    project = _get_owned_project_or_403(request, pk)
    if project.is_cancelled:
        messages.info(request, "This project is already cancelled.")
    else:
        project.status = Project.Status.CANCELLED
        project.save()
        # Milestone 3: cancelling will also release confirmed members and
        # decline pending applications (SPEC §3.2).
        messages.success(
            request,
            "Project cancelled. It stays visible at the bottom of the list; "
            "you can reactivate it later.",
        )
    return redirect("project-detail", pk=project.pk)


@login_required
@require_POST
def project_uncancel(request, pk):
    project = _get_owned_project_or_403(request, pk)
    if not project.is_cancelled:
        messages.info(request, "This project isn't cancelled.")
        return redirect("project-detail", pk=project.pk)
    if _owned_active_project(request.user, exclude_pk=project.pk):
        messages.error(
            request, "You already have another active project, so this one can't be reactivated."
        )
        return redirect("project-detail", pk=project.pk)
    # Milestone 3 adds: blocked while the owner is a member of another group
    # or has a pending application (SPEC §3.2). Former members are not restored.
    project.status = Project.Status.OPEN
    project.save()
    messages.success(request, "Project reactivated — it's open again.")
    return redirect("project-detail", pk=project.pk)


@login_required
def project_delete(request, pk):
    project = _get_owned_project_or_403(request, pk)
    if request.method == "POST":
        project.delete()
        messages.success(request, "Project deleted.")
        return redirect("home")
    return render(request, "projects/project_confirm_delete.html", {"project": project})

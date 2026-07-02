from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.db.models import Case, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import services
from .forms import ApplicationForm, ProjectForm
from .models import Application, Membership, Project


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
        "bonus_score": services.current_bonus_score(active_count),
        "user_active_project": services.owned_active_project(request.user),
    }
    return render(request, "projects/home.html", context)


@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project.objects.select_related("owner"), pk=pk)
    memberships = list(project.memberships.select_related("member"))
    context = {
        "project": project,
        "memberships": memberships,
        "is_member": any(m.member_id == request.user.pk for m in memberships),
    }
    if project.owner == request.user:
        context["pending_applications"] = project.applications.filter(
            status=Application.Status.PENDING
        ).select_related("applicant")
    else:
        context["user_application"] = project.applications.filter(
            applicant=request.user, status=Application.Status.PENDING
        ).first()
        if not context["is_member"] and not context["user_application"] and project.is_open:
            context["apply_block_reason"] = services.application_block_reason(
                request.user, project
            )
    return render(request, "projects/project_detail.html", context)


@login_required
def project_create(request):
    # SPEC §3.2: one active project per owner, and a group member can't
    # post their own project (one group per student).
    active = services.owned_active_project(request.user)
    if active:
        messages.error(
            request, "You already have an active project — cancel it before posting a new one."
        )
        return redirect("project-detail", pk=active.pk)
    if Membership.objects.filter(member=request.user).exists():
        messages.error(request, "You're already in a group, so you can't post your own project.")
        return redirect("home")
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
            # Editing group size can complete or un-complete the team.
            change = services.sync_fulfillment(project)
            if change == "fulfilled":
                messages.success(request, "Your team is complete — the project is now fulfilled!")
            elif change == "reopened":
                messages.info(request, "The larger group size reopened the project.")
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
        services.cancel_project(project)
        messages.success(
            request,
            "Project cancelled — members were released and pending applications declined. "
            "It stays at the bottom of the list and can be reactivated.",
        )
    return redirect("project-detail", pk=project.pk)


@login_required
@require_POST
def project_uncancel(request, pk):
    project = _get_owned_project_or_403(request, pk)
    if not project.is_cancelled:
        messages.info(request, "This project isn't cancelled.")
        return redirect("project-detail", pk=project.pk)
    reason = services.uncancel_block_reason(project)
    if reason:
        messages.error(request, reason)
        return redirect("project-detail", pk=project.pk)
    # Former members are not restored automatically (SPEC §3.2) — they re-apply.
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


@login_required
def project_apply(request, pk):
    project = get_object_or_404(Project.objects.select_related("owner"), pk=pk)
    reason = services.application_block_reason(request.user, project)
    if reason:
        messages.error(request, reason)
        return redirect("project-detail", pk=pk)
    if request.method == "POST":
        form = ApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.project = project
            application.applicant = request.user
            try:
                application.save()
            except IntegrityError:
                messages.error(request, "You already have a pending application.")
                return redirect("project-detail", pk=pk)
            messages.success(request, "Application sent — the owner will confirm or decline it.")
            return redirect("project-detail", pk=pk)
    else:
        form = ApplicationForm()
    return render(request, "projects/project_apply.html", {"project": project, "form": form})


@login_required
@require_POST
def application_withdraw(request, pk):
    application = get_object_or_404(
        Application, project_id=pk, applicant=request.user, status=Application.Status.PENDING
    )
    application.status = Application.Status.WITHDRAWN
    application.decided_at = timezone.now()
    application.save()
    messages.info(request, "Application withdrawn.")
    return redirect("project-detail", pk=pk)


@login_required
@require_POST
def application_confirm(request, pk, app_pk):
    project = _get_owned_project_or_403(request, pk)
    application = get_object_or_404(
        project.applications, pk=app_pk, status=Application.Status.PENDING
    )
    error = services.confirm_application(application)
    if error:
        messages.error(request, error)
    else:
        project.refresh_from_db()
        if project.status == Project.Status.FULFILLED:
            messages.success(
                request,
                f"{application.applicant.full_name} joined — your team is complete and "
                "the project is now fulfilled!",
            )
        else:
            messages.success(request, f"{application.applicant.full_name} joined your team.")
    return redirect("project-detail", pk=pk)


@login_required
@require_POST
def application_decline(request, pk, app_pk):
    project = _get_owned_project_or_403(request, pk)
    application = get_object_or_404(
        project.applications, pk=app_pk, status=Application.Status.PENDING
    )
    application.status = Application.Status.DECLINED
    application.decided_at = timezone.now()
    application.save()
    messages.info(request, "Application declined.")
    return redirect("project-detail", pk=pk)


@login_required
@require_POST
def member_remove(request, pk, member_pk):
    project = _get_owned_project_or_403(request, pk)
    membership = get_object_or_404(project.memberships, member_id=member_pk)
    name = membership.member.full_name
    change = services.remove_member(membership)
    note = " The project is open again." if change == "reopened" else ""
    messages.info(request, f"{name} was removed from the team.{note}")
    return redirect("project-detail", pk=pk)

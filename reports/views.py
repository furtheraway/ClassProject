from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from projects.services import user_current_project

from .forms import ReportForm
from .models import PeerReview, Report


@login_required
def my_report(request):
    """Submit or edit my end-of-project report (SPEC §3.5).

    One report per student per project; resubmitting overwrites the previous
    version and replaces its peer reviews.
    """
    project = user_current_project(request.user)
    if project is None:
        return render(request, "reports/no_group.html")

    team = [project.owner] + [m.member for m in project.memberships.select_related("member")]
    teammates = [u for u in team if u.pk != request.user.pk]
    report = Report.objects.filter(author=request.user, project=project).first()

    if request.method == "POST":
        form = ReportForm(request.POST, instance=report, teammates=teammates)
        if form.is_valid():
            with transaction.atomic():
                saved = form.save(commit=False)
                saved.author = request.user
                saved.project = project
                saved.save()
                # Replace reviews wholesale — the team may have changed
                # since the last submission.
                saved.peer_reviews.all().delete()
                PeerReview.objects.bulk_create(
                    PeerReview(report=saved, reviewee=user, score=score, comments=comments)
                    for user, score, comments in form.review_data()
                )
            messages.success(
                request,
                "Report submitted. You can come back and edit it any time "
                "before the deadline.",
            )
            return redirect("my-report")
    else:
        form = ReportForm(instance=report, teammates=teammates)

    return render(
        request,
        "reports/my_report.html",
        {"form": form, "project": project, "report": report},
    )

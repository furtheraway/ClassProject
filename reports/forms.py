from django import forms

from accounts.forms import BootstrapFormMixin

from .models import Report


class ReportForm(BootstrapFormMixin, forms.ModelForm):
    """Report fields plus a score/comments pair for every teammate.

    The teammate fields are added dynamically per instance (the team is
    different for every student) — the C# analogy is building form fields
    in a loop instead of declaring properties on a view model.
    """

    class Meta:
        model = Report
        fields = ["work_url", "contribution", "did_well", "to_improve"]
        widgets = {
            "work_url": forms.URLInput(attrs={"placeholder": "https://…"}),
            "contribution": forms.Textarea(attrs={"rows": 4}),
            "did_well": forms.Textarea(attrs={"rows": 4}),
            "to_improve": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, teammates=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.teammates = list(teammates)
        for user in self.teammates:
            score = forms.IntegerField(
                label="Score (0–10)",
                min_value=0,
                max_value=10,
                widget=forms.NumberInput(attrs={"min": 0, "max": 10, "class": "form-control"}),
            )
            comments = forms.CharField(
                label="Comments (optional)",
                required=False,
                widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            )
            self.fields[f"score_{user.pk}"] = score
            self.fields[f"comments_{user.pk}"] = comments
        # Pre-fill from the existing reviews when editing a saved report.
        if self.instance.pk:
            for review in self.instance.peer_reviews.all():
                self.initial.setdefault(f"score_{review.reviewee_id}", review.score)
                self.initial.setdefault(f"comments_{review.reviewee_id}", review.comments)

    def report_fields(self):
        return [self[name] for name in self.Meta.fields]

    def teammate_fields(self):
        """(teammate, score field, comments field) triples for the template."""
        return [
            (user, self[f"score_{user.pk}"], self[f"comments_{user.pk}"])
            for user in self.teammates
        ]

    def review_data(self):
        """Cleaned (teammate, score, comments) triples, for saving."""
        return [
            (
                user,
                self.cleaned_data[f"score_{user.pk}"],
                self.cleaned_data.get(f"comments_{user.pk}", ""),
            )
            for user in self.teammates
        ]

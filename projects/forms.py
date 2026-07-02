from django import forms

from accounts.forms import BootstrapFormMixin

from .models import Application, Project


class ProjectForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Project
        fields = ["title", "description", "keywords", "group_size", "talents_needed", "contact_info"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "talents_needed": forms.Textarea(attrs={"rows": 3}),
            "group_size": forms.NumberInput(attrs={"min": 2, "max": 5}),
        }

    def clean_group_size(self):
        size = self.cleaned_data["group_size"]
        # SPEC §3.2: group size can't drop below the team that already exists.
        if self.instance.pk:
            current = self.instance.members_joined
            if size < current:
                raise forms.ValidationError(
                    f"Your team already has {current} members (including you) — "
                    "group size can't be smaller than that."
                )
        return size


class ApplicationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Application
        fields = ["message", "discussed_with_owner"]
        widgets = {"message": forms.Textarea(attrs={"rows": 3})}
        labels = {"message": "Message to the owner (optional)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Model BooleanFields with a default render as optional checkboxes;
        # SPEC §3.3 makes this confirmation mandatory before applying.
        self.fields["discussed_with_owner"].required = True
        self.fields["discussed_with_owner"].error_messages["required"] = (
            "Please confirm you've discussed the project with the owner first."
        )

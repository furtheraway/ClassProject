from django import forms

from accounts.forms import BootstrapFormMixin

from .models import Project


class ProjectForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Project
        fields = ["title", "description", "keywords", "group_size", "talents_needed", "contact_info"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "talents_needed": forms.Textarea(attrs={"rows": 3}),
            "group_size": forms.NumberInput(attrs={"min": 2, "max": 5}),
        }

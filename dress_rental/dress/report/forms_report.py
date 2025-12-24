from django import forms
from .models_report import DamageReport

class DamageReportForm(forms.ModelForm):
    class Meta:
        model = DamageReport
        fields = ["report_type", "description", "evidence_image"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

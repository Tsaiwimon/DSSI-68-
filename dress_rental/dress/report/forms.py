from django import forms
from dress.models import Report, ReportAttachment


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["category", "title", "description", "damage_cost"]

class ReportAttachmentForm(forms.ModelForm):
    class Meta:
        model = ReportAttachment
        fields = ["file"]

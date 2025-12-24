from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from ..models import DamageReport



@staff_member_required
def admin_reports(request):
    reports = DamageReport.objects.select_related("shop", "order", "customer").all()
    return render(request, "admin_panel/reports_list.html", {"reports": reports})


@staff_member_required
def admin_report_detail(request, report_id):
    report = get_object_or_404(DamageReport.objects.select_related("shop", "order", "customer"), id=report_id)

    if request.method == "POST":
        action = request.POST.get("action")
        note = request.POST.get("admin_note", "").strip()

        if action == "approve":
            report.status = DamageReport.STATUS_APPROVED
            report.admin_note = note
            report.decided_at = timezone.now()
            report.save()
        elif action == "reject":
            report.status = DamageReport.STATUS_REJECTED
            report.admin_note = note
            report.decided_at = timezone.now()
            report.save()

        return redirect("admin_reports")

    return render(request, "admin_panel/report_detail.html", {"report": report})

from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .forms import ReportForm
from ..models import Report, ReportAttachment

from dress.models import Shop, RentalOrder


def create_report(request, store_id, order_id):
    shop = get_object_or_404(Shop, id=store_id)
    order = get_object_or_404(RentalOrder, id=order_id, rental_shop=shop)

    # กันรายงานซ้ำ
    if Report.objects.filter(shop=shop, order=order).exists():
        messages.warning(request, "ออเดอร์นี้มีรายงานแล้ว")
        return redirect("dress:back_office_orders_damaged", store_id=store_id)

    if request.method == "POST":
        form = ReportForm(request.POST)
        files = request.FILES.getlist("files")
        if form.is_valid():
            report = form.save(commit=False)
            report.shop = shop
            report.order = order
            report.customer = order.user
            report.save()

            for f in files:
                ReportAttachment.objects.create(report=report, file=f)

            # ย้ายออเดอร์ไปแท็บพบปัญหาชุดชำรุด
            order.status = "damaged"
            order.save(update_fields=["status"])

            messages.success(request, "ส่งรายงานเรียบร้อย")
            return redirect("dress:back_office_orders_damaged", store_id=store_id)

    else:
        form = ReportForm()

    return render(request, "reports/store_create_report.html", {
        "shop": shop,
        "order": order,
        "form": form,
    })


@login_required
def store_reports(request, store_id):
    shop = get_object_or_404(Shop, id=store_id)

    qs = (
        Report.objects
        .filter(shop=shop)
        .select_related("shop", "customer", "order")
        .order_by("-created_at")
    )

    status = request.GET.get("status")
    if status and status != "ALL":
        qs = qs.filter(status=status)

    category = request.GET.get("category")
    if category and category != "ALL":
        qs = qs.filter(category=category)

    q = request.GET.get("q")
    if q:
        qs = qs.filter(title__icontains=q)

    return render(request, "reports/store_reports.html", {
        "shop": shop,
        "reports": qs,
        "status_choices": Report.Status.choices,
        "category_choices": Report.Category.choices,
    })


@login_required
def create_damage_report(request, store_id, order_id):
    shop = get_object_or_404(Shop, id=store_id)
    order = get_object_or_404(RentalOrder, id=order_id, rental_shop=shop)

    if request.method == "POST":
        form = ReportForm(request.POST)
        files = request.FILES.getlist("files")

        if form.is_valid():
            report = form.save(commit=False)
            report.shop = shop
            report.order = order

            customer = getattr(order, "user", None)
            if customer is None:
                messages.error(request, "ไม่พบข้อมูลลูกค้าในออเดอร์นี้ (เช็คฟิลด์ user)")
                return redirect("dress:back_office_orders_returned", store_id=store_id)

            report.customer = customer
            report.save()

            for f in files:
                ReportAttachment.objects.create(report=report, file=f)

            # ส่งจากแท็บ damaged ก็ยืนยันให้ status เป็น damaged เหมือนกัน
            if order.status != "damaged":
                order.status = "damaged"
                order.save(update_fields=["status"])

            messages.success(request, "ส่งรายงานเรียบร้อย")
            return redirect("dress:back_office_orders_damaged", store_id=store_id)
    else:
        form = ReportForm(initial={"category": Report.Category.DAMAGE})

    return render(request, "reports/store_create_report.html", {
        "shop": shop,
        "order": order,
        "form": form,
    })

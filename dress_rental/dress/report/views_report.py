from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponseForbidden
from .forms_report import DamageReportForm
from ..models import Shop
from ..models import DamageReport  # ถ้าคุณ import DamageReport ไว้ใน dress/models.py แล้ว



@login_required(login_url="dress:login")
def create_damage_report(request, store_id, order_id):
    shop = get_object_or_404(Shop, id=store_id, owner=request.user)

    # ดึงออเดอร์ที่เกี่ยวกับร้านนี้จริง ๆ (สำคัญมากกันร้านอื่น report มั่ว)
    order = get_object_or_404(Order, id=order_id, shop=shop)

    if request.method == "POST":
        form = DamageReportForm(request.POST, request.FILES)
        if form.is_valid():
            report = form.save(commit=False)
            report.shop = shop
            report.order = order

            # ตั้ง customer จาก order (ปรับ field ตาม Order ของคุณ)
            # ตัวอย่างสมมติว่า order.customer หรือ order.user
            customer = getattr(order, "customer", None) or getattr(order, "user", None)
            if not customer:
                # ถ้า Order ไม่มี customer/user ให้คุณปรับเอง
                return HttpResponseForbidden("Order ไม่มีข้อมูลลูกค้า (customer/user) กรุณาปรับโมเดล Order")
            report.customer = customer

            report.save()
            return redirect("dress:store_reports", store_id=shop.id)  # หน้า list รายงานของร้าน
    else:
        form = DamageReportForm()

    return render(request, "dress/report_create.html", {
        "store": shop,
        "order": order,
        "form": form,
    })


@login_required(login_url="dress:login")
def store_reports(request, store_id):
    shop = get_object_or_404(Shop, id=store_id, owner=request.user)

    reports = shop.damage_reports.select_related("order", "customer").all()

    return render(request, "dress/store_reports.html", {
        "store": shop,
        "reports": reports,
    })

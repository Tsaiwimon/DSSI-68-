from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import get_user_model

from .decorators import admin_required

# ปรับ import ให้ตรงแอปของคุณ
from dress.models import Shop, Dress


@admin_required
def dashboard(request):
    User = get_user_model()

    total_users = User.objects.count()
    total_shops = Shop.objects.count()
    total_dresses = Dress.objects.count()
    pending_shops = Shop.objects.filter(status=Shop.STATUS_PENDING).count()

    context = {
        "total_users": total_users,
        "total_shops": total_shops,
        "total_dresses": total_dresses,
        "pending_shops": pending_shops,
    }
    return render(request, "backoffice/dashboard.html", context)


@admin_required
def shop_pending_list(request):
    shops = Shop.objects.filter(status=Shop.STATUS_PENDING).order_by("-created_at")
    return render(request, "backoffice/shops_pending.html", {"shops": shops})


@admin_required
def shop_approve(request, shop_id):
    if request.method != "POST":
        return redirect("backoffice:shop_pending_list")

    shop = get_object_or_404(Shop, id=shop_id)
    shop.status = Shop.STATUS_APPROVED
    shop.approved_by = request.user
    shop.approved_at = timezone.now()
    shop.reject_reason = ""
    shop.save(update_fields=["status", "approved_by", "approved_at", "reject_reason"])

    messages.success(request, "อนุมัติร้านเรียบร้อยแล้ว")
    return redirect("backoffice:shop_pending_list")


@admin_required
def shop_reject(request, shop_id):
    if request.method != "POST":
        return redirect("backoffice:shop_pending_list")

    shop = get_object_or_404(Shop, id=shop_id)
    reason = request.POST.get("reason", "").strip()

    shop.status = Shop.STATUS_REJECTED
    shop.reject_reason = reason
    shop.approved_by = request.user
    shop.approved_at = timezone.now()
    shop.save(update_fields=["status", "reject_reason", "approved_by", "approved_at"])

    messages.success(request, "ปฏิเสธร้านเรียบร้อยแล้ว")
    return redirect("backoffice:shop_pending_list")

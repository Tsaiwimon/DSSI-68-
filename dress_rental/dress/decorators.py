from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden
from .models import Shop
from django.shortcuts import render



def shop_approved_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("dress:login")

        shop = Shop.objects.filter(owner=request.user).order_by("-created_at").first()
        if not shop:
            messages.error(request, "ยังไม่มีข้อมูลร้านของคุณ")
            return redirect("dress:open_store")

        # กันแอบเข้าร้านคนอื่น (สำคัญมาก)
        store_id = kwargs.get("store_id")
        if store_id is not None and shop.id != int(store_id):
            return render(request, "dress/403.html", status=403)

        # กันสถานะร้าน
        if shop.status != Shop.STATUS_APPROVED:
            messages.warning(request, "ร้านของคุณกำลังรอการอนุมัติจากผู้ดูแลระบบ")
            return redirect("dress:shop_pending_notice")

        return view_func(request, *args, **kwargs)

    return _wrapped

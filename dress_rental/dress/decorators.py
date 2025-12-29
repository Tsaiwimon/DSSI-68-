from functools import wraps
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib import messages
from .models import Shop


def shop_approved_required(view_func):
    """
    ใช้กับ view ฝั่งเจ้าของร้านที่ต้องการ:
    - ต้อง login
    - ต้องเป็นเจ้าของร้านตาม store_id
    - ร้านต้องสถานะ approved
    หมายเหตุ: ถ้าเป็น staff จะให้ผ่าน (เพื่อแอดมินช่วยดูได้) -> ปรับได้ตามต้องการ
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("dress:login")

        # ถ้าเป็น staff/admin ให้ผ่าน (ถ้าไม่ต้องการ ให้ลบบล็อกนี้ทิ้ง)
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)

        store_id = kwargs.get("store_id")

        # ถ้ามี store_id: ดึงร้านจาก store_id แล้วเช็คเจ้าของแบบตรง ๆ (ถูกที่สุด)
        if store_id is not None:
            shop = get_object_or_404(Shop, id=store_id)

            if shop.owner != request.user:
                return render(request, "dress/403.html", status=403)

        else:
            # ไม่มี store_id: fallback เป็นร้านล่าสุดของ user (ใช้เฉพาะบางหน้า)
            shop = Shop.objects.filter(owner=request.user).order_by("-created_at").first()
            if not shop:
                messages.error(request, "ยังไม่มีข้อมูลร้านของคุณ")
                return redirect("dress:open_store")

        # เช็คสถานะอนุมัติ
        if shop.status != Shop.STATUS_APPROVED:
            messages.warning(request, "ร้านของคุณกำลังรอการอนุมัติจากผู้ดูแลระบบ")
            return redirect("dress:shop_pending_notice")

        # ฝาก shop ไว้ใน request เผื่อ view ใช้ต่อได้ (optional)
        request.shop = shop

        return view_func(request, *args, **kwargs)

    return _wrapped




def member_required(view_func):
    """
    สำหรับหน้า member: ต้อง login และห้ามเป็น staff (admin)
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("dress:login")
        if request.user.is_staff:
            return redirect("backoffice:dashboard")
        return view_func(request, *args, **kwargs)
    return _wrapped


def shop_owner_required(view_func):
    """
    สำหรับหน้าเจ้าของร้าน: ต้อง login และต้องเป็นเจ้าของร้านตาม store_id
    ไม่บังคับ approved (เหมาะกับหน้าตั้งค่า/โปรไฟล์ร้าน/อัปโหลดเอกสาร)
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("dress:login")

        # ถ้าคุณไม่อยากให้ staff เข้าหน้าร้าน ให้ลบบล็อกนี้
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)

        store_id = kwargs.get("store_id")
        if store_id is None:
            messages.error(request, "ไม่พบรหัสร้าน (store_id)")
            return redirect("dress:home")

        shop = get_object_or_404(Shop, id=store_id)

        if shop.owner != request.user:
            return render(request, "dress/403.html", status=403)

        request.shop = shop
        return view_func(request, *args, **kwargs)
    return _wrapped
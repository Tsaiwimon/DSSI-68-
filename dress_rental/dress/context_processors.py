# dress/context_processors.py
from .models import Notification

def unread_notifications(request):
    # ค่าเริ่มต้น เผื่อไม่ล็อกอิน
    unread_notifications_count = 0      # ฝั่งลูกค้า
    shop_unread_count = 0               # ฝั่งร้าน (หลังร้าน)

    if request.user.is_authenticated:
        # ฝั่งลูกค้า/สมาชิก
        unread_notifications_count = Notification.objects.filter(
            user=request.user,
            is_read=False,
            audience="CUSTOMER",
        ).count()

        # ฝั่งร้าน/หลังร้าน
        shop_unread_count = Notification.objects.filter(
            user=request.user,
            is_read=False,
            audience="SHOP",
        ).count()

    return {
        "unread_notifications_count": unread_notifications_count,
        "shop_unread_count": shop_unread_count,
    }




def shop_unread_notifications(request):
    """
    อันนี้เพิ่มมาเพื่อให้ตรงกับที่ settings.py เรียก
    + ส่ง count ทั้ง 2 ฝั่งให้ใช้ได้ทุกหน้า
    """
    if not request.user.is_authenticated:
        return {
            "unread_customer_notify_count": 0,
            "unread_shop_notify_count": 0,
            "unread_notifications_count": 0,  # กันพังของเก่า
        }

    unread_customer = Notification.objects.filter(
        user=request.user,
        is_read=False,
        audience="CUSTOMER",
    ).count()

    unread_shop = Notification.objects.filter(
        user=request.user,
        is_read=False,
        audience="SHOP",
    ).count()

    return {
        "unread_customer_notify_count": unread_customer,
        "unread_shop_notify_count": unread_shop,
        "unread_notifications_count": unread_customer,  # ให้ชื่อเดิมยังใช้ได้
    }

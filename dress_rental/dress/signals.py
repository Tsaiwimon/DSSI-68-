from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import RentalOrder
from .notifications.shop import (
    notify_shop_order_new,
    notify_shop_payment_success,
    notify_shop_status_changed,
)



@receiver(pre_save, sender=RentalOrder)
def rentalorder_pre_save(sender, instance, **kwargs):
    """
    เก็บค่า status เก่าก่อนบันทึก เพื่อเอาไปเทียบใน post_save
    """
    instance._old_status = None
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._old_status = getattr(old, "status", None)
        except sender.DoesNotExist:
            instance._old_status = None


@receiver(post_save, sender=RentalOrder)
def rentalorder_post_save(sender, instance, created, **kwargs):
    """
    ยิงแจ้งเตือนหลังร้านอัตโนมัติเมื่อ:
    - สร้างออเดอร์ใหม่
    - เปลี่ยนสถานะออเดอร์
    - สถานะเปลี่ยนเป็น paid (ชำระเงินแล้ว)
    """
    new_status = getattr(instance, "status", None)
    old_status = getattr(instance, "_old_status", None)

    # 1) สร้างออเดอร์ใหม่
    if created:
        notify_shop_order_new(instance)

        # ถ้าสร้างมาแล้วเป็น paid เลย (บาง flow ทำได้)
        if str(new_status).lower() == "paid":
            notify_shop_payment_success(instance)
        return

    # 2) อัปเดตสถานะ
    if old_status is not None and new_status is not None and old_status != new_status:
        notify_shop_status_changed(instance, old_status=old_status)

        # 3) เพิ่งกลายเป็น paid -> ยิงแจ้งเตือนเตรียมจัดส่ง/รับงาน
        if str(new_status).lower() == "paid" and str(old_status).lower() != "paid":
            notify_shop_payment_success(instance)

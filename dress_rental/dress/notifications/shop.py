# dress/notifications/shop.py

from django.db import IntegrityError
from django.urls import reverse

from ..models import Notification


# -----------------------------
# Helpers: หา shop / owner user
# -----------------------------
def _get_shop_from_order(order):
    """
    พยายามดึง Shop จาก order แบบยืดหยุ่น
    ปรับเพิ่มตามโครงโมเดลของคุณได้
    """
    # case 1: order.shop หรือ order.store
    shop = getattr(order, "shop", None) or getattr(order, "store", None)
    if shop:
        return shop

    # case 2: order.dress.shop (ถ้า order ผูกกับชุด)
    dress = getattr(order, "dress", None)
    if dress:
        shop = getattr(dress, "shop", None) or getattr(dress, "store", None)
        if shop:
            return shop

    # case 3: order.items.first().dress.shop (ถ้ามี order items)
    items = getattr(order, "items", None)
    if items and hasattr(items, "all"):
        first = items.all().first()
        if first:
            d = getattr(first, "dress", None)
            if d:
                shop = getattr(d, "shop", None) or getattr(d, "store", None)
                if shop:
                    return shop

    return None


def _get_shop_owner_user(shop):
    """
    ดึง user เจ้าของร้าน
    ส่วนมากจะเป็น shop.owner หรือ shop.user
    """
    return getattr(shop, "owner", None) or getattr(shop, "user", None)


# -----------------------------
# Core creator
# -----------------------------
def create_shop_notification(
    *,
    shop_user,
    title,
    message,
    event_code="",
    related_order=None,
    sender_shop=None,
    chat_thread=None,
    link_url="",
    dedupe_key=None,
    n_type="order",
):
    """
    สร้างแจ้งเตือนฝั่งหลังร้าน (SHOP)
    - ถ้าใส่ dedupe_key จะกันแจ้งซ้ำตาม UniqueConstraint (user+dedupe_key)
    """
    try:
        Notification.objects.create(
            user=shop_user,
            title=title,
            message=message,
            type=n_type,          # "order" | "chat" | "review"
            audience="SHOP",
            event_code=event_code,
            related_order=related_order,
            sender_shop=sender_shop,
            chat_thread=chat_thread,
            link_url=link_url or "",
            dedupe_key=dedupe_key,
        )
        return True
    except IntegrityError:
        # กันแจ้งซ้ำกรณี dedupe_key ซ้ำ
        return False


# -----------------------------
# Order events
# -----------------------------
def _order_detail_link(shop, order):
    """
    ลิงก์ไปหน้ารายละเอียดออเดอร์หลังร้าน
    ถ้า url name ไม่ตรง ปรับที่นี่จุดเดียว
    """
    try:
        return reverse("dress:back_office_order_detail", args=[shop.id, order.id])
    except Exception:
        return ""


def notify_shop_order_new(order):
    """
    เรียกหลังจากสร้าง order สำเร็จ
    """
    shop = _get_shop_from_order(order)
    if not shop:
        return False

    shop_user = _get_shop_owner_user(shop)
    if not shop_user:
        return False

    link = _order_detail_link(shop, order)

    return create_shop_notification(
        shop_user=shop_user,
        title="มีออเดอร์ใหม่เข้า",
        message=f"มีคำสั่งเช่าใหม่ #{order.id} กรุณาตรวจสอบและดำเนินการ",
        event_code="ORDER_NEW",
        related_order=order,
        sender_shop=shop,
        link_url=link,
        dedupe_key=f"ORDER_NEW:{order.id}",
        n_type="order",
    )


def notify_shop_order_cancelled(order, old_status=None):
    """
    เรียกเมื่อออเดอร์ถูกยกเลิก
    """
    shop = _get_shop_from_order(order)
    if not shop:
        return False

    shop_user = _get_shop_owner_user(shop)
    if not shop_user:
        return False

    link = _order_detail_link(shop, order)
    extra = f" (จาก {old_status})" if old_status else ""

    return create_shop_notification(
        shop_user=shop_user,
        title="ออเดอร์ถูกยกเลิก",
        message=f"ออเดอร์ #{order.id} ถูกยกเลิกแล้ว{extra}",
        event_code="ORDER_CANCEL",
        related_order=order,
        sender_shop=shop,
        link_url=link,
        dedupe_key=f"ORDER_CANCEL:{order.id}",
        n_type="order",
    )


def notify_shop_payment_success(order):
    """
    เรียกหลังจากยืนยันว่าชำระเงินสำเร็จแล้ว
    """
    shop = _get_shop_from_order(order)
    if not shop:
        return False

    shop_user = _get_shop_owner_user(shop)
    if not shop_user:
        return False

    link = _order_detail_link(shop, order)

    return create_shop_notification(
        shop_user=shop_user,
        title="ชำระเงินสำเร็จ",
        message=f"ออเดอร์ #{order.id} ชำระเงินแล้ว กรุณาเตรียมจัดส่ง/ส่งมอบ",
        event_code="PAYMENT_OK",
        related_order=order,
        sender_shop=shop,
        link_url=link,
        dedupe_key=f"PAYMENT_OK:{order.id}",
        n_type="order",
    )


def notify_shop_status_changed(order, old_status=None):
    """
    เรียกหลังจากมีการเปลี่ยน status ของออเดอร์
    - ถ้า status เปลี่ยนเป็น CANCELLED จะโยนไป notify_shop_order_cancelled()
    """
    status = getattr(order, "status", "")
    status_upper = str(status).upper()

    # ถ้ายกเลิก แยก event ให้ชัด + กันซ้ำง่าย
    if status_upper == "CANCELLED":
        return notify_shop_order_cancelled(order, old_status=old_status)

    shop = _get_shop_from_order(order)
    if not shop:
        return False

    shop_user = _get_shop_owner_user(shop)
    if not shop_user:
        return False

    link = _order_detail_link(shop, order)

    msg = (
        f"ออเดอร์ #{order.id} เปลี่ยนสถานะจาก {old_status} เป็น {status}"
        if old_status
        else f"ออเดอร์ #{order.id} เปลี่ยนสถานะเป็น {status}"
    )
    dk = (
        f"STATUS:{order.id}:{old_status}->{status}"
        if old_status
        else f"STATUS:{order.id}:{status}"
    )

    # map สถานะ -> event_code (ปรับตาม status จริงในระบบคุณ)
    status_to_event = {
        "PREPARING": "ORDER_STATUS",
        "SHIPPING": "ORDER_STATUS",
        "DAMAGED": "ORDER_ISSUE",
    }
    event = status_to_event.get(status_upper, "ORDER_STATUS")

    return create_shop_notification(
        shop_user=shop_user,
        title="อัปเดตสถานะออเดอร์",
        message=msg,
        event_code=event,
        related_order=order,
        sender_shop=shop,
        link_url=link,
        dedupe_key=dk,
        n_type="order",
    )


# -----------------------------
# Chat events
# -----------------------------
def _get_shop_from_chat_thread(thread):
    """
    หา shop จาก thread แบบยืดหยุ่น
    ปรับเพิ่มตามโครงโมเดลของคุณได้
    """
    shop = getattr(thread, "shop", None) or getattr(thread, "sender_shop", None)
    if shop:
        return shop

    order = getattr(thread, "order", None) or getattr(thread, "related_order", None)
    if order:
        return _get_shop_from_order(order)

    return None


def _chat_thread_link(thread):
    """
    ลิงก์ไปหน้าแชทหลังร้าน
    ปรับ url name ให้ตรงของคุณ
    """
    try:
        return reverse("dress:shop_chat_thread", args=[thread.id])
    except Exception:
        return ""


def notify_shop_chat_incoming(message):
    """
    message: ChatMessage ที่สร้างใหม่ (ฝั่งลูกค้าส่งเข้า)
    - ต้องปรับ field ชื่อข้อความตามของจริง: text/content/message
    """
    thread = getattr(message, "thread", None) or getattr(message, "chat_thread", None)
    if not thread:
        return False

    shop = _get_shop_from_chat_thread(thread)
    if not shop:
        return False

    shop_user = _get_shop_owner_user(shop)
    if not shop_user:
        return False

    link = _chat_thread_link(thread)

    text = (
        getattr(message, "text", None)
        or getattr(message, "content", None)
        or getattr(message, "message", None)
        or ""
    )
    preview = (text[:80] + "...") if len(text) > 80 else text

    return create_shop_notification(
        shop_user=shop_user,
        title="แชทลูกค้าเข้า",
        message=f"มีข้อความใหม่: {preview}",
        event_code="CHAT_NEW",
        sender_shop=shop,
        chat_thread=thread,
        link_url=link,
        dedupe_key=f"CHAT_NEW:{thread.id}:{message.id}",
        n_type="chat",
    )


# -----------------------------
# Review events
# -----------------------------
def _get_shop_from_review(review):
    """
    หา shop จาก review แบบยืดหยุ่น
    ปรับเพิ่มตามโครงโมเดลของคุณได้
    """
    shop = getattr(review, "shop", None) or getattr(review, "sender_shop", None)
    if shop:
        return shop

    order = getattr(review, "order", None) or getattr(review, "related_order", None)
    if order:
        return _get_shop_from_order(order)

    dress = getattr(review, "dress", None)
    if dress:
        return getattr(dress, "shop", None) or getattr(dress, "store", None)

    return None


def _review_detail_link(review):
    """
    ลิงก์ไปหน้ารายละเอียดรีวิวหลังร้าน
    ปรับ url name ให้ตรงของคุณ
    """
    try:
        return reverse("dress:shop_review_detail", args=[review.id])
    except Exception:
        return ""


def notify_shop_low_review(review, threshold=2):
    """
    รีวิวที่ต่ำ (<= threshold)
    - ต้องปรับ field rating/stars ให้ตรงของจริง
    """
    rating = getattr(review, "rating", None) or getattr(review, "stars", None)
    if rating is None:
        return False

    try:
        rating_value = float(rating)
    except Exception:
        return False

    if rating_value > threshold:
        return False

    shop = _get_shop_from_review(review)
    if not shop:
        return False

    shop_user = _get_shop_owner_user(shop)
    if not shop_user:
        return False

    link = _review_detail_link(review)

    return create_shop_notification(
        shop_user=shop_user,
        title="มีรีวิวคะแนนต่ำ",
        message=f"มีรีวิว {rating_value} ดาว กรุณาตรวจสอบและตอบกลับ",
        event_code="REVIEW_LOW",
        sender_shop=shop,
        link_url=link,
        dedupe_key=f"REVIEW_LOW:{review.id}",
        n_type="review",
    )

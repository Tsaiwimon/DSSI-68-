from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.apps import apps
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .decorators import admin_required
from dress.models import Shop, Dress, RentalOrder, Review, PlatformSettings

 













@admin_required
def dashboard(request):
    User = get_user_model()

    total_users = User.objects.count()
    total_shops = Shop.objects.count()
    total_dresses = Dress.objects.count()
    pending_shops = Shop.objects.filter(status=Shop.STATUS_PENDING).count()

    # เพิ่ม: ร้านที่เปิดแล้ว
    approved_shops = Shop.objects.filter(status=Shop.STATUS_APPROVED).count()

    # เพิ่ม: ข้อมูลกราฟ (demo ก่อน)
    chart_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    chart_values = [12, 22, 18, 30, 24, 28, 20]

    # เพิ่ม: ตารางรายการล่าสุด (demo ก่อน)
    latest_issues = [
        {"date": "5 เม.ย. 2025", "user": "Bee", "topic": "การจัดส่งสินค้า", "shop": "ร้านChinRent", "status": "ดูรายละเอียด"},
        {"date": "20 เม.ย. 2025", "user": "GHB", "topic": "ไม่ได้ของ", "shop": "ผู้ใช้CVFdjg", "status": "ดูรายละเอียด"},
        {"date": "1 พ.ค. 2025", "user": "mala", "topic": "ยกเลิกการจอง", "shop": "malaShop", "status": "ดูรายละเอียด"},
    ]

    context = {
        "total_users": total_users,
        "total_shops": total_shops,
        "total_dresses": total_dresses,
        "pending_shops": pending_shops,

        # ใหม่
        "approved_shops": approved_shops,
        "chart_labels": chart_labels,
        "chart_values": chart_values,
        "latest_issues": latest_issues,
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









@admin_required
def users_page(request):
    User = get_user_model()

    q = (request.GET.get("q") or "").strip()
    role = (request.GET.get("role") or "").strip()      # admin | shop | user | ""
    status = (request.GET.get("status") or "").strip()  # active | inactive | ""

    users_qs = User.objects.all().order_by("-date_joined")

    # ค้นหา
    if q:
        users_qs = users_qs.filter(
            Q(username__icontains=q) |
            Q(email__icontains=q)
        )

    # สถานะ
    if status == "active":
        users_qs = users_qs.filter(is_active=True)
    elif status == "inactive":
        users_qs = users_qs.filter(is_active=False)

    # role: ใช้ตรรกะง่าย ๆ ไม่พึ่ง OuterRef/Exists (กัน NameError)
    # shop owner: คนที่เป็น owner ในตาราง Shop
    shop_owner_ids = list(
        Shop.objects.values_list("owner_id", flat=True).distinct()
    )

    if role == "admin":
        users_qs = users_qs.filter(Q(is_superuser=True) | Q(is_staff=True))
    elif role == "shop":
        users_qs = users_qs.filter(id__in=shop_owner_ids).exclude(Q(is_superuser=True) | Q(is_staff=True))
    elif role == "user":
        users_qs = users_qs.exclude(Q(is_superuser=True) | Q(is_staff=True)).exclude(id__in=shop_owner_ids)

    # paginate
    paginator = Paginator(users_qs, 10)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    # ใส่ flag ให้ template ใช้ได้ง่าย
    # (ช่วยให้ {% if u.is_shop_owner %} ทำงาน แม้ model user จะไม่มี field นี้)
    shop_owner_set = set(shop_owner_ids)
    for u in page_obj.object_list:
        setattr(u, "is_shop_owner", u.id in shop_owner_set)

    # preserved querystring สำหรับ pagination
    preserved = {}
    if q:
        preserved["q"] = q
    if role:
        preserved["role"] = role
    if status:
        preserved["status"] = status
    preserved_qs = urlencode(preserved)

    context = {
        "page_obj": page_obj,
        "total_filtered": paginator.count,
        "q": q,
        "role": role,
        "status": status,
        "preserved_qs": preserved_qs,
        "next_url": request.get_full_path(),  # กลับหน้าเดิมหลังทำ action
    }
    return render(request, "backoffice/users.html", context)


def _safe_next(request, fallback_name="backoffice:users"):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return reverse(fallback_name)


@require_POST
@admin_required
def user_suspend(request, user_id):
    if request.method != "POST":
        return redirect("backoffice:users")

    User = get_user_model()
    target = get_object_or_404(User, id=user_id)

    if target == request.user:
        messages.error(request, "ไม่สามารถระงับบัญชีของตัวเองได้")
        return redirect(_safe_next(request))

    if target.is_superuser or target.is_staff:
        messages.error(request, "ไม่สามารถระงับบัญชีแอดมินได้")
        return redirect(_safe_next(request))

    target.is_active = False
    target.save(update_fields=["is_active"])
    messages.success(request, f"ระงับผู้ใช้ {target.username} แล้ว")
    return redirect(_safe_next(request))

@require_POST
@admin_required
def user_activate(request, user_id):
    if request.method != "POST":
        return redirect("backoffice:users")

    User = get_user_model()
    target = get_object_or_404(User, id=user_id)

    if target.is_superuser or target.is_staff:
        messages.error(request, "ไม่สามารถแก้สถานะแอดมินจากหน้านี้ได้")
        return redirect(_safe_next(request))

    target.is_active = True
    target.save(update_fields=["is_active"])
    messages.success(request, f"ยกเลิกระงับผู้ใช้ {target.username} แล้ว")
    return redirect(_safe_next(request))

@require_POST
@admin_required
def user_delete(request, user_id):
    if request.method != "POST":
        return redirect("backoffice:users")

    User = get_user_model()
    target = get_object_or_404(User, id=user_id)

    if target == request.user:
        messages.error(request, "ไม่สามารถลบบัญชีของตัวเองได้")
        return redirect(_safe_next(request))

    if target.is_superuser or target.is_staff:
        messages.error(request, "ไม่สามารถลบบัญชีแอดมินได้")
        return redirect(_safe_next(request))

    username = target.username
    target.delete()
    messages.success(request, f"ลบผู้ใช้ {username} แล้ว")
    return redirect(_safe_next(request))







@admin_required
def reports_page(request):
    """
    หน้ารายงาน:
    - ถ้ายังไม่มี model รายงาน => โชว์ 0 รายการ (ไม่ error)
    - ถ้ามี model รายงานภายหลัง => จะดึงข้อมูลขึ้นตารางให้อัตโนมัติ (ตามฟิลด์พื้นฐานที่พอเดาได้)
    """

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()  # "" | "pending" | "done" (ตาม UI)

    # พยายามหาโมเดลรายงานแบบปลอดภัย (ถ้าไม่มีจะคืน None)
    report_model = None
    candidate_models = [
        ("dress", "Report"),
        ("dress", "UserReport"),
        ("reports", "Report"),
        ("reports", "UserReport"),
        ("backoffice", "Report"),
    ]
    for app_label, model_name in candidate_models:
        try:
            report_model = apps.get_model(app_label, model_name)
            if report_model:
                break
        except LookupError:
            continue

    reports = []
    total_count = 0

    if report_model:
        qs = report_model.objects.all()

        # ค้นหาแบบกว้าง ๆ (ถ้ามีฟิลด์เหล่านี้)
        search_fields = ["reason", "detail", "description", "message", "title"]
        if q:
            query = Q()
            for f in search_fields:
                try:
                    report_model._meta.get_field(f)
                    query |= Q(**{f"{f}__icontains": q})
                except Exception:
                    pass
            if query.children:
                qs = qs.filter(query)

        # filter สถานะ (ถ้ามีฟิลด์ status)
        if status:
            try:
                report_model._meta.get_field("status")
                qs = qs.filter(status=status)
            except Exception:
                pass

        # order_by วันที่ (พยายามจับชื่อฟิลด์ยอดฮิต)
        for dt_field in ["created_at", "created", "date", "reported_at"]:
            try:
                report_model._meta.get_field(dt_field)
                qs = qs.order_by(f"-{dt_field}")
                break
            except Exception:
                continue

        total_count = qs.count()

        # แปลงเป็น dict สำหรับ template (ยืดหยุ่น ไม่ผูกกับชื่อฟิลด์ 100%)
        for obj in qs[:50]:
            # ผู้ถูกรายงาน / ผู้รายงาน (ลองดึงจากฟิลด์ยอดฮิต)
            reported_name = "-"
            reporter_name = "-"

            for f in ["reported_user", "target_user", "reported", "shop", "target_shop"]:
                if hasattr(obj, f) and getattr(obj, f) is not None:
                    reported_name = str(getattr(obj, f))
                    break

            for f in ["reporter", "user", "reported_by", "created_by"]:
                if hasattr(obj, f) and getattr(obj, f) is not None:
                    reporter_name = str(getattr(obj, f))
                    break

            # รายละเอียด
            detail = "-"
            for f in ["detail", "description", "reason", "message", "title"]:
                if hasattr(obj, f) and getattr(obj, f):
                    detail = str(getattr(obj, f))
                    break

            # วันที่
            date_value = None
            for f in ["created_at", "created", "date", "reported_at"]:
                if hasattr(obj, f) and getattr(obj, f):
                    date_value = getattr(obj, f)
                    break

            # สถานะ
            status_value = getattr(obj, "status", "") if hasattr(obj, "status") else ""

            reports.append({
                "id": getattr(obj, "id", None),
                "reported_name": reported_name,
                "reporter_name": reporter_name,
                "detail": detail,
                "date": date_value,
                "status": status_value,
            })

    context = {
        "q": q,
        "status": status,
        "total_count": total_count,
        "reports": reports,
    }
    return render(request, "backoffice/reports.html", context)





@admin_required
def bookings_page(request):
    q = (request.GET.get("q") or "").strip()
    status_filter = (request.GET.get("status") or "all").strip()

    # 1) ฐานข้อมูลหลัก
    qs = RentalOrder.objects.select_related("user", "rental_shop").all()

    # 2) search
    if q:
        qs = qs.filter(
            Q(id__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__email__icontains=q) |
            Q(rental_shop__name__icontains=q)
        )

    # 3) map กลุ่มสถานะตามระบบจริงของ RentalOrder
    SUCCESS_STATUSES = {"paid", "returned", "completed"}   # ปรับได้ตามนิยามของคุณ
    CANCEL_STATUSES  = {"cancelled"}

    def status_key(raw: str) -> str:
        s = (raw or "").strip().lower()
        if s in SUCCESS_STATUSES:
            return "success"
        if s in CANCEL_STATUSES:
            return "cancel"
        return "pending"

    # 4) filter ตาม dropdown
    if status_filter != "all":
        # กรองด้วย python แบบชัวร์ (ไม่ต้องเดาชุด status__in ที่อาจเปลี่ยน)
        tmp = []
        for obj in qs.order_by("-id"):
            if status_key(obj.status) == status_filter:
                tmp.append(obj)
        qs_list = tmp
    else:
        qs_list = list(qs.order_by("-id"))

    # 5) sort ให้ "เสร็จสิ้นขึ้นมาก่อน" (priority)
    # อยากให้เสร็จสิ้นอยู่บนสุด: success -> pending -> cancel
    priority = {"success": 0, "pending": 1, "cancel": 2}
    qs_list.sort(key=lambda o: (priority[status_key(o.status)], -o.id))

    # 6) build rows ให้ template ใช้ง่าย
    rows = []
    for obj in qs_list:
        sk = status_key(obj.status)
        if sk == "success":
            label = "เสร็จสิ้น"
        elif sk == "cancel":
            label = "ยกเลิก"
        else:
            label = "กำลังดำเนินการ"

        user_name = obj.user.username if obj.user else "-"
        user_initial = (user_name[:1] or "U").upper()

        rows.append({
            "id": obj.id,
            "code": f"#{obj.id:06d}",
            "user_name": user_name,
            "user_initial": user_initial,
            "shop_name": obj.rental_shop.name if obj.rental_shop else "-",
            "date": obj.created_at,   # ใช้ created_at ของ RentalOrder
            "status_key": sk,
            "status_label": label,
        })

    # 7) สรุปยอด (อิง “ทั้งหมดจริง” ไม่ว่า filter อะไร)
    # ถ้าคุณอยากให้การ์ดเปลี่ยนตาม filter บอก เดี๋ยวปรับให้
    all_rows = []
    for obj in RentalOrder.objects.all():
        all_rows.append(status_key(obj.status))
    total_count = len(all_rows)
    success_count = sum(1 for s in all_rows if s == "success")
    pending_count = sum(1 for s in all_rows if s == "pending")
    cancel_count  = sum(1 for s in all_rows if s == "cancel")

    # 8) paginate จาก rows ที่กรองแล้ว/จัดลำดับแล้ว
    paginator = Paginator(rows, 10)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    return render(request, "backoffice/bookings.html", {
        "page_obj": page_obj,
        "total_count": total_count,
        "success_count": success_count,
        "pending_count": pending_count,
        "cancel_count": cancel_count,
        "status_filter": status_filter,
        "q": q,
        "model_found": True,
    })



def _compute_late_fee(settings_obj: PlatformSettings, due_date, returned_at):
    """
    โหมดที่คุณใช้ตอนนี้: per_day
    คิดคืนช้าหลัง "วันกำหนดคืน" โดยให้ grace_hours ได้
    - ค่าปรับ = late_days * late_fee_per_day
    - cap ไม่เกิน late_fee_cap
    """
    grace_hours = int(settings_obj.late_fee_grace_hours or 0)

    # กำหนดเส้นตายเป็น "จบวันกำหนดคืน" แล้วค่อยบวก grace
    due_dt = timezone.make_aware(datetime.combine(due_date, time(23, 59, 59)))
    start_penalty_dt = due_dt + timedelta(hours=grace_hours)

    if returned_at <= start_penalty_dt:
        return 0, Decimal("0.00")

    delta = returned_at - start_penalty_dt
    late_days = math.ceil(delta.total_seconds() / 86400)

    fee = Decimal(late_days) * Decimal(settings_obj.late_fee_per_day)
    cap = Decimal(settings_obj.late_fee_cap)
    if fee > cap:
        fee = cap

    return late_days, fee.quantize(Decimal("0.01"))


@require_POST
def booking_mark_returned(request, order_id):
    # ถ้าคุณใช้ @admin_required อยู่แล้ว ให้ใส่กลับ
    # ผมใส่แยกไว้เผื่อคุณจัดตำแหน่ง decorator เอง
    from .decorators import admin_required
    return _booking_mark_returned_impl(admin_required, request, order_id)


def _booking_mark_returned_impl(admin_required, request, order_id):
    @admin_required
    def inner(request, order_id):
        order = get_object_or_404(RentalOrder, id=order_id)

        settings_obj = PlatformSettings.current()
        if not settings_obj:
            settings_obj = PlatformSettings.objects.create(name="Default", is_active=True)

        now = timezone.now()
        late_days, late_fee = _compute_late_fee(settings_obj, order.return_date, now)

        with transaction.atomic():
            order.returned_at = now
            order.late_days = late_days
            order.late_fee_amount = late_fee

            # ปรับสถานะตาม flow ของคุณ (ถ้าคุณอยากให้ไป waiting_return ก่อนแล้วค่อย returned ก็ได้)
            order.status = RentalOrder.STATUS_RETURNED

            order.save(update_fields=["returned_at", "late_days", "late_fee_amount", "status"])

        if late_fee > 0:
            messages.warning(request, f"คืนช้า {late_days} วัน ค่าปรับ {late_fee} บาท (cap ตามระบบกลาง)")
        else:
            messages.success(request, "บันทึกคืนชุดเรียบร้อย (ไม่พบการคืนช้า)")

        return redirect("backoffice:bookings")

    return inner(request, order_id)





@admin_required
def reviews_page(request):
    """
    หน้า 'รีวิว' (Backoffice)
    - ดึงข้อมูลจริงจาก Review
    - มีค้นหา + ตัวกรอง (ดาว/ร้าน/ตอบกลับแล้ว/มีรูป) + pagination
    - รองรับ POST: ตอบกลับรีวิว / ลบรีวิว / ซ่อนรีวิว
    """

    # ---------- POST actions (รองรับยิงกลับหน้าเดียวด้วย) ----------
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        review_id = request.POST.get("review_id")

        if action in {"reply", "delete", "toggle_hidden"} and review_id:
            review = get_object_or_404(Review, id=review_id)

            if action == "reply":
                reply_text = (request.POST.get("reply_text") or "").strip()
                review.shop_reply = reply_text
                review.replied_at = timezone.now() if reply_text else None
                review.save()
                messages.success(request, "บันทึกการตอบกลับเรียบร้อยแล้ว")
                return redirect(request.get_full_path())

            if action == "toggle_hidden":
                # ต้องมี field is_hidden ใน Review ถ้าไม่มีให้ตัดส่วนนี้ออก
                review.is_hidden = not getattr(review, "is_hidden", False)
                review.save(update_fields=["is_hidden"])
                messages.success(request, "อัปเดตสถานะการซ่อนเรียบร้อยแล้ว")
                return redirect(request.get_full_path())

            if action == "delete":
                review.delete()
                messages.success(request, "ลบรีวิวเรียบร้อยแล้ว")
                return redirect(request.get_full_path())

    # ---------- Filters ----------
    q = (request.GET.get("q") or "").strip()
    rating = (request.GET.get("rating") or "all").strip()         # all, 1..5
    shop_id = (request.GET.get("shop") or "all").strip()          # all, shop.id
    replied = (request.GET.get("replied") or "all").strip()       # all, yes, no
    has_image = (request.GET.get("has_image") or "all").strip()   # all, yes, no
    sort = (request.GET.get("sort") or "new").strip()             # new, old, rating_high, rating_low

    qs = (
        Review.objects
        .select_related("user", "dress", "dress__shop")
        .all()
    )

    # search
    if q:
        qs = qs.filter(
            Q(user__username__icontains=q) |
            Q(user__email__icontains=q) |
            Q(dress__name__icontains=q) |
            Q(dress__shop__name__icontains=q) |
            Q(comment__icontains=q) |
            Q(shop_reply__icontains=q)
        )

    # rating filter
    if rating.isdigit():
        qs = qs.filter(rating=int(rating))

    # shop filter
    if shop_id.isdigit():
        qs = qs.filter(dress__shop_id=int(shop_id))

    # replied filter
    if replied == "yes":
        qs = qs.exclude(shop_reply__isnull=True).exclude(shop_reply__exact="")
    elif replied == "no":
        qs = qs.filter(Q(shop_reply__isnull=True) | Q(shop_reply__exact=""))

    # has image filter (เช็คจาก Review.image)
    if has_image == "yes":
        qs = qs.exclude(image__isnull=True).exclude(image__exact="")
    elif has_image == "no":
        qs = qs.filter(Q(image__isnull=True) | Q(image__exact=""))

    # sorting
    if sort == "old":
        qs = qs.order_by("created_at", "id")
    elif sort == "rating_high":
        qs = qs.order_by("-rating", "-created_at", "-id")
    elif sort == "rating_low":
        qs = qs.order_by("rating", "-created_at", "-id")
    else:
        qs = qs.order_by("-created_at", "-id")  # new

    # summary counts (ตาม filter)
    total_count = qs.count()
    rating5_count = qs.filter(rating=5).count()
    rating4_count = qs.filter(rating=4).count()
    pending_reply_count = qs.filter(Q(shop_reply__isnull=True) | Q(shop_reply__exact="")).count()

    # pagination
    paginator = Paginator(qs, 6)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    shops = Shop.objects.all().order_by("name")

    return render(
        request,
        "backoffice/reviews.html",
        {
            "page_obj": page_obj,
            "total_count": total_count,
            "rating5_count": rating5_count,
            "rating4_count": rating4_count,
            "pending_reply_count": pending_reply_count,
            "q": q,
            "rating": rating,
            "shop_id": shop_id,
            "replied": replied,
            "has_image": has_image,
            "sort": sort,
            "shops": shops,
            "star_range": range(1, 6),
        },
    )


# ---------- แยก endpoint ให้ตรง urls.py (ถ้าคุณยังใช้ใน template) ----------
@admin_required
def review_reply(request, review_id):
    if request.method != "POST":
        return redirect("backoffice:reviews")

    review = get_object_or_404(Review, id=review_id)
    reply_text = (request.POST.get("reply_text") or "").strip()
    review.shop_reply = reply_text
    review.replied_at = timezone.now() if reply_text else None
    review.save()
    messages.success(request, "บันทึกการตอบกลับเรียบร้อยแล้ว")

    next_url = request.POST.get("next") or "backoffice:reviews"
    return redirect(next_url)


@admin_required
def review_toggle_hidden(request, review_id):
    if request.method != "POST":
        return redirect("backoffice:reviews")

    review = get_object_or_404(Review, id=review_id)
    review.is_hidden = not getattr(review, "is_hidden", False)
    review.save(update_fields=["is_hidden"])
    messages.success(request, "อัปเดตสถานะการซ่อนเรียบร้อยแล้ว")

    next_url = request.POST.get("next") or "backoffice:reviews"
    return redirect(next_url)


@admin_required
def review_delete(request, review_id):
    if request.method != "POST":
        return redirect("backoffice:reviews")

    review = get_object_or_404(Review, id=review_id)
    review.delete()
    messages.success(request, "ลบรีวิวเรียบร้อยแล้ว")

    next_url = request.POST.get("next") or "backoffice:reviews"
    return redirect(next_url)







def _to_decimal(val, fallback: Decimal) -> Decimal:
    """
    แปลง string -> Decimal แบบปลอดภัย
    - รับ "1,234.50" ได้
    - ถ้าว่าง/แปลงไม่ได้ ใช้ fallback
    """
    if val is None:
        return fallback
    s = str(val).strip().replace(",", "")
    if s == "":
        return fallback
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return fallback

def _to_rate(val, fallback: Decimal) -> Decimal:
    """
    แปลง commission_rate / vat_rate
    - ถ้ากรอก 10 => 0.10
    - ถ้ากรอก 0.10 => 0.10
    - ถ้ากรอก 10% => 0.10
    """
    if val is None:
        return fallback
    s = str(val).strip().replace("%", "").replace(",", "")
    if s == "":
        return fallback
    try:
        d = Decimal(s)
        # ถ้าคนกรอก 10 แปลว่า 10%
        if d > 1:
            d = d / Decimal("100")
        # clamp 0..1
        if d < 0:
            d = Decimal("0")
        if d > 1:
            d = Decimal("1")
        return d
    except (InvalidOperation, ValueError):
        return fallback

@admin_required
def settings_page(request):
    settings_obj = PlatformSettings.current()
    if not settings_obj:
        settings_obj = PlatformSettings.objects.create(name="Default", is_active=True)

    if request.method == "POST":
        with transaction.atomic():
            # --- Commission ---
            settings_obj.commission_rate = _to_rate(
                request.POST.get("commission_rate"), settings_obj.commission_rate
            )
            settings_obj.commission_min_fee = _to_decimal(
                request.POST.get("commission_min_fee"), settings_obj.commission_min_fee
            )
            settings_obj.commission_vat_rate = _to_rate(
                request.POST.get("commission_vat_rate"), settings_obj.commission_vat_rate
            )

            # --- Late fee (ระบบกลาง) ---
            settings_obj.late_fee_mode = (request.POST.get("late_fee_mode") or settings_obj.late_fee_mode).strip()
            settings_obj.late_fee_per_day = _to_decimal(
                request.POST.get("late_fee_per_day"), settings_obj.late_fee_per_day
            )
            settings_obj.late_fee_cap = _to_decimal(
                request.POST.get("late_fee_cap"), settings_obj.late_fee_cap
            )
            try:
                settings_obj.late_fee_grace_hours = int(
                    request.POST.get("late_fee_grace_hours") or settings_obj.late_fee_grace_hours
                )
            except ValueError:
                pass

            # --- Refund/Inspection ---
            try:
                settings_obj.inspection_days = int(request.POST.get("inspection_days") or settings_obj.inspection_days)
            except ValueError:
                pass
            try:
                settings_obj.refund_days = int(request.POST.get("refund_days") or settings_obj.refund_days)
            except ValueError:
                pass
            settings_obj.refund_method = (request.POST.get("refund_method") or settings_obj.refund_method).strip()

            # กัน active ซ้อน: ให้มี active ตัวเดียว
            PlatformSettings.objects.exclude(id=settings_obj.id).update(is_active=False)
            settings_obj.is_active = True

            settings_obj.save()

        messages.success(request, "บันทึกการตั้งค่าเรียบร้อยแล้ว")
        return redirect("backoffice:settings")

    commission_percent = (settings_obj.commission_rate * Decimal("100")).quantize(Decimal("0.01"))
    commission_vat_percent = (settings_obj.commission_vat_rate * Decimal("100")).quantize(Decimal("0.01"))

    context = {
        "settings_obj": settings_obj,
        "commission_percent": commission_percent,
        "commission_vat_percent": commission_vat_percent,
        "deposit_source": "ดึงจาก Dress.deposit (ต่อชิ้น)",
        "late_fee_modes": PlatformSettings.LATE_FEE_MODE_CHOICES,
        "refund_methods": PlatformSettings.REFUND_METHOD_CHOICES,
    }
    return render(request, "backoffice/settings.html", context)



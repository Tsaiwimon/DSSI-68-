from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode
import math
from datetime import datetime, time, timedelta

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
from dress.models import Report, ReportAttachment


# =============================
# Utils
# =============================
def _has_field(model_cls, field_name: str) -> bool:
    try:
        model_cls._meta.get_field(field_name)
        return True
    except Exception:
        return False


def _safe_str(obj) -> str:
    try:
        return str(obj)
    except Exception:
        return "-"


def _pick_first_attr(obj, candidates):
    for f in candidates:
        if hasattr(obj, f):
            val = getattr(obj, f)
            if val is not None and val != "":
                return val
    return None


# =============================
# Report / DamageReport support
# =============================
STATUS_LABEL_TH = {
    "SUBMITTED": "ส่งรายงานแล้ว",
    "PROCESSING": "กำลังตรวจสอบ",
    "RESOLVED": "จัดการแล้ว",
    "REJECTED": "ปฏิเสธ",
}

STATUS_KEY = {
    "SUBMITTED": "submitted",
    "PROCESSING": "processing",
    "RESOLVED": "done",
    "REJECTED": "rejected",
}

STATUS_TH_TO_CODE = {v: k for k, v in STATUS_LABEL_TH.items()}

STATUS_OPTIONS = [
    ("", "ทั้งหมด"),
    ("SUBMITTED", "ส่งรายงานแล้ว"),
    ("PROCESSING", "กำลังตรวจสอบ"),
    ("RESOLVED", "จัดการแล้ว"),
    ("REJECTED", "ปฏิเสธ"),
]


def _normalize_status_param(raw: str) -> str:
    s = (raw or "").strip()
    if s == "" or s.lower() in {"all", "ทั้งหมด"}:
        return ""
    # ถ้าส่งมาเป็นภาษาไทย ให้แปลงกลับเป็น code
    if s in STATUS_TH_TO_CODE:
        return STATUS_TH_TO_CODE[s]
    return s  # น่าจะเป็น code อยู่แล้ว เช่น SUBMITTED


def _get_report_models():
    """
    รองรับ:
    - dress.models.Report
    - dress.report.models_report.DamageReport (อยู่ใน app 'dress')
    """
    models = [("Report", Report)]

    try:
        DamageReport = apps.get_model("dress", "DamageReport")
        models.append(("DamageReport", DamageReport))
    except LookupError:
        pass

    return models


def _report_detail_text(obj) -> str:
    for f in ["description", "detail", "reason", "message", "title", "note"]:
        if hasattr(obj, f):
            v = getattr(obj, f)
            if v:
                return str(v)
    return "-"


def _report_date(obj):
    for f in ["created_at", "created", "reported_at", "date"]:
        if hasattr(obj, f):
            v = getattr(obj, f)
            if v:
                return v
    return None


def _build_report_rows(q: str = "", status: str = "", limit_each_model: int = 200):
    """
    รวม rows จากหลายโมเดล (Report + DamageReport) เพื่อให้ list ไม่หาย
    """
    q = (q or "").strip()
    status = _normalize_status_param(status)

    models = _get_report_models()
    all_items = []

    for model_label, Model in models:
        qs = Model.objects.all()

        # filter status ถ้ามี field status
        if status and _has_field(Model, "status"):
            qs = qs.filter(status=status)

        # search
        if q:
            query = Q()

            for f in ["title", "detail", "description", "reason", "message", "note"]:
                if _has_field(Model, f):
                    query |= Q(**{f"{f}__icontains": q})

            if _has_field(Model, "shop"):
                query |= Q(shop__name__icontains=q)
            if _has_field(Model, "customer"):
                query |= Q(customer__username__icontains=q)
            if _has_field(Model, "order"):
                query |= Q(order__id__icontains=q)

            if query.children:
                qs = qs.filter(query)

        # order by newest
        if _has_field(Model, "created_at"):
            qs = qs.order_by("-created_at", "-id")
        elif _has_field(Model, "created"):
            qs = qs.order_by("-created", "-id")
        elif _has_field(Model, "reported_at"):
            qs = qs.order_by("-reported_at", "-id")
        else:
            qs = qs.order_by("-id")

        for obj in qs[:limit_each_model]:
            dt = _report_date(obj)

            shop_val = _pick_first_attr(obj, ["shop", "target_shop"])
            customer_val = _pick_first_attr(obj, ["customer", "reported_user", "target_user", "user"])

            reporter_name = _safe_str(shop_val) if shop_val is not None else "-"
            reported_name = _safe_str(customer_val) if customer_val is not None else "-"

            order_val = _pick_first_attr(obj, ["order"])
            if reported_name == "-" and order_val is not None:
                reported_name = f"Order #{getattr(order_val, 'id', '-')}"

            status_code = getattr(obj, "status", "") if hasattr(obj, "status") else ""

            # กัน datetime None/naive
            sort_dt = dt
            if sort_dt is None:
                sort_dt = timezone.make_aware(datetime(1970, 1, 1))
            else:
                try:
                    if timezone.is_naive(sort_dt):
                        sort_dt = timezone.make_aware(sort_dt)
                except Exception:
                    sort_dt = timezone.make_aware(datetime(1970, 1, 1))

            all_items.append({
                "id": getattr(obj, "id", None),
                "model": model_label,  # ใช้ช่วย debug/กันชน
                "reported_name": reported_name,
                "reported_initial": (reported_name[:1] or "U").upper(),
                "reporter_name": reporter_name,
                "reporter_initial": (reporter_name[:1] or "S").upper(),
                "detail": _report_detail_text(obj),
                "date": dt,
                "status_code": status_code,
                "status_key": STATUS_KEY.get(status_code, "submitted"),
                "status_label": STATUS_LABEL_TH.get(status_code, str(status_code)),
                "_sort_dt": sort_dt,
            })

    all_items.sort(key=lambda x: x["_sort_dt"], reverse=True)
    for x in all_items:
        x.pop("_sort_dt", None)

    return all_items


# =============================
# Dashboard
# =============================
@admin_required
def dashboard(request):
    User = get_user_model()

    total_users = User.objects.count()
    total_shops = Shop.objects.count()
    total_dresses = Dress.objects.count()
    pending_shops = Shop.objects.filter(status=Shop.STATUS_PENDING).count()

    chart_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    chart_values = [12, 22, 18, 30, 24, 28, 20]

    report_rows = _build_report_rows(limit_each_model=30)
    issues_count = len(report_rows)

    latest_issues = []
    for r in report_rows[:3]:
        dt = r.get("date")
        if dt:
            try:
                date_str = timezone.localtime(dt).strftime("%d/%m/%Y %H:%M")
            except Exception:
                date_str = str(dt)
        else:
            date_str = "-"

        latest_issues.append({
            "date": date_str,
            "user": r.get("reporter_name", "-"),
            "topic": r.get("detail", "-"),
            "shop": r.get("reported_name", "-"),
            "status": "ดูรายละเอียด",
        })

    context = {
        "total_users": total_users,
        "total_shops": total_shops,
        "total_dresses": total_dresses,
        "pending_shops": pending_shops,

        "chart_labels": chart_labels,
        "chart_values": chart_values,

        "issues_count": issues_count,
        "latest_issues": latest_issues,
    }
    return render(request, "backoffice/dashboard.html", context)


# =============================
# Shop approval
# =============================
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


# =============================
# Users
# =============================
@admin_required
def users_page(request):
    User = get_user_model()

    q = (request.GET.get("q") or "").strip()
    role = (request.GET.get("role") or "").strip()
    status = (request.GET.get("status") or "").strip()

    users_qs = User.objects.all().order_by("-date_joined")

    if q:
        users_qs = users_qs.filter(Q(username__icontains=q) | Q(email__icontains=q))

    if status == "active":
        users_qs = users_qs.filter(is_active=True)
    elif status == "inactive":
        users_qs = users_qs.filter(is_active=False)

    shop_owner_ids = list(Shop.objects.values_list("owner_id", flat=True).distinct())

    if role == "admin":
        users_qs = users_qs.filter(Q(is_superuser=True) | Q(is_staff=True))
    elif role == "shop":
        users_qs = users_qs.filter(id__in=shop_owner_ids).exclude(Q(is_superuser=True) | Q(is_staff=True))
    elif role == "user":
        users_qs = users_qs.exclude(Q(is_superuser=True) | Q(is_staff=True)).exclude(id__in=shop_owner_ids)

    paginator = Paginator(users_qs, 10)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    shop_owner_set = set(shop_owner_ids)
    for u in page_obj.object_list:
        setattr(u, "is_shop_owner", u.id in shop_owner_set)

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
        "next_url": request.get_full_path(),
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


# =============================
# Reports (LIST / DETAIL / UPDATE)
# =============================
@admin_required
def reports_page(request):
    q = (request.GET.get("q") or "").strip()
    status_raw = (request.GET.get("status") or "").strip()
    status = _normalize_status_param(status_raw)

    rows_all = _build_report_rows(q=q, status=status, limit_each_model=200)

    paginator = Paginator(rows_all, 10)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    return render(request, "backoffice/reports.html", {
        "rows": page_obj.object_list,
        "page_obj": page_obj,
        "total": paginator.count,
        "q": q,
        "status": status,  # ส่งเป็น code กลับไป
        "status_options": STATUS_OPTIONS,
    })


@admin_required
def report_detail(request, report_id):
    """
    พยายามหาใน Report ก่อน ถ้าไม่เจอค่อยไป DamageReport
    """
    report_obj = None
    model_label = "Report"

    try:
        report_obj = Report.objects.select_related("shop", "order", "customer").get(id=report_id)
        model_label = "Report"
    except Report.DoesNotExist:
        try:
            DamageReport = apps.get_model("dress", "DamageReport")
            report_obj = DamageReport.objects.select_related("shop", "order", "customer").get(id=report_id)
            model_label = "DamageReport"
        except Exception:
            report_obj = None

    if report_obj is None:
        messages.error(request, "ไม่พบรายงาน")
        return redirect("backoffice:reports")

    # attachments: มีเฉพาะ ReportAttachment (ของ Report) ถ้าเป็น DamageReport จะให้ว่างไว้แบบไม่พัง
    attachments = []
    if model_label == "Report":
        attachments = list(ReportAttachment.objects.filter(report_id=report_obj.id).all())

    status_code = getattr(report_obj, "status", "") if hasattr(report_obj, "status") else ""

    context = {
        "report": report_obj,
        "model_label": model_label,
        "detail_text": _report_detail_text(report_obj),
        "date_value": _report_date(report_obj),
        "status_code": status_code,
        "status_label": STATUS_LABEL_TH.get(status_code, str(status_code)),
        "status_options": STATUS_OPTIONS[1:],  # ตัด "ทั้งหมด"
        "attachments": attachments,
        "admin_note_value": getattr(report_obj, "admin_note", ""),
    }
    return render(request, "backoffice/report_detail.html", context)


@require_POST
@admin_required
def report_update(request, report_id):
    """
    อัปเดตสถานะ (และ admin_note ถ้ามี)
    รองรับทั้ง Report และ DamageReport
    """
    new_status_raw = (request.POST.get("status") or "").strip()
    new_status = _normalize_status_param(new_status_raw)  # รับได้ทั้งไทย/โค้ด
    admin_note = (request.POST.get("admin_note") or "").strip()

    if new_status not in STATUS_LABEL_TH:
        messages.error(request, "สถานะไม่ถูกต้อง")
        return redirect("backoffice:report_detail", report_id=report_id)

    # หา obj
    obj = None
    model_label = "Report"

    try:
        obj = Report.objects.get(id=report_id)
        model_label = "Report"
    except Report.DoesNotExist:
        try:
            DamageReport = apps.get_model("dress", "DamageReport")
            obj = DamageReport.objects.get(id=report_id)
            model_label = "DamageReport"
        except Exception:
            obj = None

    if obj is None:
        messages.error(request, "ไม่พบรายงาน")
        return redirect("backoffice:reports")

    # update
    if hasattr(obj, "status"):
        obj.status = new_status

    if hasattr(obj, "admin_note"):
        obj.admin_note = admin_note

    if new_status in {"RESOLVED", "REJECTED"}:
        if hasattr(obj, "handled_by"):
            obj.handled_by = request.user
        if hasattr(obj, "handled_at"):
            obj.handled_at = timezone.now()

    obj.save()
    messages.success(request, "อัปเดตสถานะรายงานเรียบร้อยแล้ว")
    return redirect("backoffice:report_detail", report_id=report_id)


# =============================
# Bookings
# =============================
@admin_required
def bookings_page(request):
    q = (request.GET.get("q") or "").strip()
    status_filter = (request.GET.get("status") or "all").strip()

    qs = RentalOrder.objects.select_related("user", "rental_shop").all()

    if q:
        qs = qs.filter(
            Q(id__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__email__icontains=q) |
            Q(rental_shop__name__icontains=q)
        )

    SUCCESS_STATUSES = {"paid", "returned", "completed"}
    CANCEL_STATUSES = {"cancelled"}

    def status_key(raw: str) -> str:
        s = (raw or "").strip().lower()
        if s in SUCCESS_STATUSES:
            return "success"
        if s in CANCEL_STATUSES:
            return "cancel"
        return "pending"

    if status_filter != "all":
        tmp = []
        for obj in qs.order_by("-id"):
            if status_key(obj.status) == status_filter:
                tmp.append(obj)
        qs_list = tmp
    else:
        qs_list = list(qs.order_by("-id"))

    priority = {"success": 0, "pending": 1, "cancel": 2}
    qs_list.sort(key=lambda o: (priority[status_key(o.status)], -o.id))

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
            "date": obj.created_at,
            "status_key": sk,
            "status_label": label,
        })

    all_rows = [status_key(obj.status) for obj in RentalOrder.objects.all()]
    total_count = len(all_rows)
    success_count = sum(1 for s in all_rows if s == "success")
    pending_count = sum(1 for s in all_rows if s == "pending")
    cancel_count = sum(1 for s in all_rows if s == "cancel")

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
    grace_hours = int(settings_obj.late_fee_grace_hours or 0)
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
            order.status = RentalOrder.STATUS_RETURNED
            order.save(update_fields=["returned_at", "late_days", "late_fee_amount", "status"])

        if late_fee > 0:
            messages.warning(request, f"คืนช้า {late_days} วัน ค่าปรับ {late_fee} บาท (cap ตามระบบกลาง)")
        else:
            messages.success(request, "บันทึกคืนชุดเรียบร้อย (ไม่พบการคืนช้า)")

        return redirect("backoffice:bookings")

    return inner(request, order_id)


# =============================
# Reviews
# =============================
@admin_required
def reviews_page(request):
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
                review.is_hidden = not getattr(review, "is_hidden", False)
                review.save(update_fields=["is_hidden"])
                messages.success(request, "อัปเดตสถานะการซ่อนเรียบร้อยแล้ว")
                return redirect(request.get_full_path())

            if action == "delete":
                review.delete()
                messages.success(request, "ลบรีวิวเรียบร้อยแล้ว")
                return redirect(request.get_full_path())

    q = (request.GET.get("q") or "").strip()
    rating = (request.GET.get("rating") or "all").strip()
    shop_id = (request.GET.get("shop") or "all").strip()
    replied = (request.GET.get("replied") or "all").strip()
    has_image = (request.GET.get("has_image") or "all").strip()
    sort = (request.GET.get("sort") or "new").strip()

    qs = Review.objects.select_related("user", "dress", "dress__shop").all()

    if q:
        qs = qs.filter(
            Q(user__username__icontains=q) |
            Q(user__email__icontains=q) |
            Q(dress__name__icontains=q) |
            Q(dress__shop__name__icontains=q) |
            Q(comment__icontains=q) |
            Q(shop_reply__icontains=q)
        )

    if rating.isdigit():
        qs = qs.filter(rating=int(rating))

    if shop_id.isdigit():
        qs = qs.filter(dress__shop_id=int(shop_id))

    if replied == "yes":
        qs = qs.exclude(shop_reply__isnull=True).exclude(shop_reply__exact="")
    elif replied == "no":
        qs = qs.filter(Q(shop_reply__isnull=True) | Q(shop_reply__exact=""))

    if has_image == "yes":
        qs = qs.exclude(image__isnull=True).exclude(image__exact="")
    elif has_image == "no":
        qs = qs.filter(Q(image__isnull=True) | Q(image__exact=""))

    if sort == "old":
        qs = qs.order_by("created_at", "id")
    elif sort == "rating_high":
        qs = qs.order_by("-rating", "-created_at", "-id")
    elif sort == "rating_low":
        qs = qs.order_by("rating", "-created_at", "-id")
    else:
        qs = qs.order_by("-created_at", "-id")

    total_count = qs.count()
    rating5_count = qs.filter(rating=5).count()
    rating4_count = qs.filter(rating=4).count()
    pending_reply_count = qs.filter(Q(shop_reply__isnull=True) | Q(shop_reply__exact="")).count()

    paginator = Paginator(qs, 6)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    shops = Shop.objects.all().order_by("name")

    return render(request, "backoffice/reviews.html", {
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
    })


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


# =============================
# Settings
# =============================
def _to_decimal(val, fallback: Decimal) -> Decimal:
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
    if val is None:
        return fallback
    s = str(val).strip().replace("%", "").replace(",", "")
    if s == "":
        return fallback
    try:
        d = Decimal(s)
        if d > 1:
            d = d / Decimal("100")
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
            settings_obj.commission_rate = _to_rate(request.POST.get("commission_rate"), settings_obj.commission_rate)
            settings_obj.commission_min_fee = _to_decimal(request.POST.get("commission_min_fee"), settings_obj.commission_min_fee)
            settings_obj.commission_vat_rate = _to_rate(request.POST.get("commission_vat_rate"), settings_obj.commission_vat_rate)

            settings_obj.late_fee_mode = (request.POST.get("late_fee_mode") or settings_obj.late_fee_mode).strip()
            settings_obj.late_fee_per_day = _to_decimal(request.POST.get("late_fee_per_day"), settings_obj.late_fee_per_day)
            settings_obj.late_fee_cap = _to_decimal(request.POST.get("late_fee_cap"), settings_obj.late_fee_cap)
            try:
                settings_obj.late_fee_grace_hours = int(request.POST.get("late_fee_grace_hours") or settings_obj.late_fee_grace_hours)
            except ValueError:
                pass

            try:
                settings_obj.inspection_days = int(request.POST.get("inspection_days") or settings_obj.inspection_days)
            except ValueError:
                pass
            try:
                settings_obj.refund_days = int(request.POST.get("refund_days") or settings_obj.refund_days)
            except ValueError:
                pass
            settings_obj.refund_method = (request.POST.get("refund_method") or settings_obj.refund_method).strip()

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

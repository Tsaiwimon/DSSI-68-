from decimal import Decimal
import json
import time
from datetime import datetime , timedelta, date
from urllib import request
from django.http import Http404

from django.utils.dateparse import parse_date

from .decorators import shop_approved_required
import omise
from django.conf import settings

from django.urls import reverse ,NoReverseMatch
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError
from django.db.models import Q, Avg, Sum, Count
from django.db.models.functions import TruncMonth
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.db.models.functions import TruncDate
from .utils import get_store_or_403
from django.contrib.auth import get_user_model
User = get_user_model()





from .models import (
    Shop,  Dress, Category, Review, Favorite, CartItem, Rental, UserProfile,
    PriceTemplate, PriceTemplateItem, ShippingRule, ShippingBracket,
    RentalOrder,Notification,StoreTransaction,WithdrawalRequest, # ใช้สำหรับระบบ "การเช่าของฉัน"
    ShopChatThread, ShopChatMessage, Order, OrderItem)  # แชททั่วไปก่อนเช่า

# รูป QR fallback (กรณีไม่มีคีย์/เกิดข้อผิดพลาด)
FALLBACK_QR_URL = "/static/img/mock-qr.svg"






# =========================
# หน้าแรก (สาธารณะ)
# =========================
def home(request):
    q = str(request.GET.get("q", "")).strip()
    category = str(request.GET.get("category", "")).strip()

    # แสดงเฉพาะชุดที่ “เปิดให้เช่า” และ “ไม่ถูกเก็บเข้าคลัง”
    dresses = Dress.objects.filter(
        is_available=True,
        is_archived=False,
    )

    categories = Category.objects.all()

    if q:
        dresses = dresses.filter(name__icontains=q)
    if category:
        dresses = dresses.filter(categories__name=category)

    context = {
        "dresses": list(dresses),
        "categories": list(categories),
        "selected_category": category,
    }
    return render(request, "dress/home.html", context)




# =========================
# Auth
# =========================
def signup_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password != confirm_password:
            messages.error(request, "รหัสผ่านไม่ตรงกัน")
            return redirect("dress:signup")

        if User.objects.filter(username=username).exists():
            messages.error(request, "ชื่อผู้ใช้นี้ถูกใช้งานแล้ว")
            return redirect("dress:signup")

        if User.objects.filter(email=email).exists():
            messages.error(request, "อีเมลนี้ถูกใช้งานแล้ว")
            return redirect("dress:signup")

        User.objects.create_user(username=username, email=email, password=password)
        messages.success(request, "สมัครสมาชิกสำเร็จ กรุณาเข้าสู่ระบบ")
        return redirect("dress:login")

    return render(request, "dress/signup.html")





def login_redirect(request):
    if not request.user.is_authenticated:
        return redirect("dress:login")

    # แอดมินไปหลังบ้านเสมอ
    if request.user.is_staff:
        return redirect("backoffice:dashboard")

    # เจ้าของร้านไปหลังร้านของตัวเอง
    shop = Shop.objects.filter(owner=request.user).only("id").first()
    if shop:
        return redirect("dress:my_store", store_id=shop.id)

    # สมาชิกทั่วไป
    return redirect("dress:member_home")


def login_view(request):
    next_url = request.POST.get("next") or request.GET.get("next") or ""

    def is_safe_next(url: str) -> bool:
        if not url:
            return False
        parsed = urlparse(url)
        return parsed.netloc == "" and url.startswith("/")

    def is_backoffice_url(url: str) -> bool:
        return url.startswith("/backoffice/")

    def is_shop_url(url: str) -> bool:
        # ปรับ prefix ให้ตรงกับระบบคุณ ถ้ามีหลายหน้า shop ก็เติมเพิ่มได้
        return url.startswith("/my-store/") or url.startswith("/store/")

    def is_shop_owner(user) -> bool:
        return Shop.objects.filter(owner=user).exists()

    # ถ้าล็อกอินอยู่แล้ว
    if request.user.is_authenticated:
        if is_safe_next(next_url):
            if is_backoffice_url(next_url) and not request.user.is_staff:
                messages.error(request, "บัญชีนี้ไม่มีสิทธิ์เข้าหน้าแอดมิน")
                return redirect("dress:home")

            if is_shop_url(next_url) and not is_shop_owner(request.user) and not request.user.is_staff:
                messages.error(request, "บัญชีนี้ไม่มีสิทธิ์เข้าหน้าร้าน")
                return redirect("dress:member_home")

            return redirect(next_url)

        if request.user.is_staff:
            return redirect("backoffice:dashboard")
        return redirect("dress:home")

    # ยังไม่ล็อกอิน
    if request.method == "POST":
        username_or_email = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        try:
            user_obj = User.objects.get(Q(username=username_or_email) | Q(email=username_or_email))
            username = user_obj.username
        except User.DoesNotExist:
            messages.error(request, "ไม่พบบัญชีผู้ใช้งานนี้")
            return redirect("dress:login")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)

            if is_safe_next(next_url):
                if is_backoffice_url(next_url) and not user.is_staff:
                    messages.error(request, "บัญชีนี้ไม่มีสิทธิ์เข้าหน้าแอดมิน")
                    return redirect("dress:home")

                if is_shop_url(next_url) and not is_shop_owner(user) and not user.is_staff:
                    messages.error(request, "บัญชีนี้ไม่มีสิทธิ์เข้าหน้าร้าน")
                    return redirect("dress:member_home")

                return redirect(next_url)

            if user.is_staff:
                return redirect("backoffice:dashboard")
            return redirect(reverse("dress:login_redirect"))

        messages.error(request, "รหัสผ่านไม่ถูกต้อง")
        return redirect("dress:login")

    return render(request, "dress/login.html", {"next": next_url})


def logout_view(request):
    logout(request)
    messages.info(request, "ออกจากระบบเรียบร้อยแล้ว")
    return redirect("dress:login")





# =========================
# Member
# =========================
@login_required(login_url="dress:login")
def member_home(request):
    q = request.GET.get("q")
    category = request.GET.get("category")

    # แสดงเฉพาะชุดที่ยังไม่ถูกเก็บเข้าคลัง และเปิดให้เช่าอยู่
    dresses = Dress.objects.filter(is_archived=False, is_available=True)

    if q:
        dresses = dresses.filter(name__icontains=q)
    if category:
        dresses = dresses.filter(categories__name=category)

    # ดึงหมวดหมู่จากชุดที่ยัง active อยู่เท่านั้น (จะได้ไม่โชว์หมวดของชุดที่ถูกเก็บคลัง)
    categories = Category.objects.filter(dress__is_archived=False).distinct()

    return render(request, "dress/member_home.html", {
        "dresses": dresses,
        "categories": categories,
        "selected_category": category,
    })


@login_required(login_url="dress:login")
def open_store(request):
    if request.method == "POST":
        shop_name = request.POST.get("shop_name", "").strip()
        province = request.POST.get("province", "").strip()
        phone = request.POST.get("phone", "").strip()
        fee = request.POST.get("fee", "").strip()

        shop_logo = request.FILES.get("shop_logo")
        id_card_image = request.FILES.get("id_card")
        bankbook_image = request.FILES.get("bank_book")


        if not shop_name or not province:
            messages.error(request, "กรุณากรอกข้อมูลร้านให้ครบถ้วน")
            return redirect("dress:open_store")

        # (ทางเลือก) บังคับแนบเอกสาร
        if not id_card_image or not bankbook_image:
            messages.error(request, "กรุณาแนบรูปบัตรประชาชน และรูปหน้าสมุดบัญชีให้ครบถ้วน")
            return redirect("dress:open_store")

        shop = Shop.objects.create(
            owner=request.user,
            name=shop_name,
            province=province,
            phone=phone,
            fee=fee,
            shop_logo=shop_logo,
            id_card_image=id_card_image,
            bankbook_image=bankbook_image,
            status=Shop.STATUS_PENDING,
        )

        messages.success(
            request,
            "ส่งคำขอเปิดร้านเรียบร้อยแล้ว กรุณารอแอดมินตรวจสอบและอนุมัติ"
        )
        return redirect("dress:shop_pending_notice")

    return render(request, "dress/open_store.html")





# ดูหน้าร้านของตัวเอง
@login_required(login_url="dress:login")
def my_store(request, store_id):
    shop = get_object_or_404(Shop, id=store_id, owner=request.user)

    # แสดงเฉพาะชุดที่ยังไม่ถูกเก็บเข้าคลัง
    products = shop.dresses.filter(is_archived=False)

    return render(request, "dress/my_store.html", {
        "store": shop,
        "products": products,
    })


#ดูรายชุดในร้าน
@login_required(login_url="dress:login")
@shop_approved_required
def store_dress(request, store_id):
    # 1) หา “ร้าน” ก่อน (ถ้าไม่มีจริง ๆ -> 404)
    store = get_object_or_404(Shop, id=store_id)

    # 2) ถ้าไม่ใช่เจ้าของร้าน -> 403
    if store.owner != request.user:
        return render(request, "dress/403.html", status=403)

    # 3) ถ้าร้านยังไม่ approved -> เด้งไป pending
    if store.status != Shop.STATUS_APPROVED:
        return redirect("dress:shop_pending_notice")

    # อ่านค่าหมวดหมู่จาก query string
    category = (request.GET.get("category") or "ทั้งหมด").strip()

    # ดึงเฉพาะชุดที่ยังไม่ถูกเก็บเข้าคลัง
    dresses = store.dresses.filter(is_archived=False)

    if category != "ทั้งหมด":
        dresses = dresses.filter(categories__name=category)

    categories = (
        Category.objects
        .filter(dress__shop=store, dress__is_archived=False)
        .distinct()
    )

    total_dresses = dresses.count()

    return render(request, "dress/store_dress.html", {
        "store": store,
        "dresses": dresses,
        "categories": categories,
        "selected_category": category,
        "total_dresses": total_dresses,
    })




# คลังชุด (เก็บชุดที่ไม่อยากให้แสดงหน้าร้าน แต่ไม่อยากลบทิ้ง)
@login_required(login_url="dress:login")
def store_dress_archive(request, store_id):
    """
    หน้ารายการ 'ชุดในคลัง' ของร้าน
    แสดงเฉพาะชุดที่ is_archived = True
    """
    shop = get_object_or_404(Shop, id=store_id, owner=request.user)

    # ชุดที่เก็บเข้าคลังแล้ว
    dresses = shop.dresses.filter(is_archived=True)

    category = request.GET.get("category")
    if category and category != "ทั้งหมด":
        dresses = dresses.filter(categories__name=category)

    categories = Category.objects.filter(dress__shop=shop).distinct()
    total_dresses = dresses.count()  # นับเฉพาะชุดในคลัง

    return render(request, "dress/store_dress_archive.html", {
        "store": shop,
        "dresses": dresses,
        "categories": categories,
        "selected_category": category,
        "total_dresses": total_dresses,
    }) 


#เพิ่มชุดใหม่
@shop_approved_required
@login_required(login_url="dress:login")
def add_dress(request, store_id):
    shop = get_object_or_404(Shop, id=store_id, owner=request.user)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        size = request.POST.get("size", "").strip()

        daily_price = float(request.POST.get("daily_price") or 0)
        deposit = float(request.POST.get("deposit") or 0)
        shipping_fee = float(request.POST.get("shipping_fee") or 0)

        image = request.FILES.get("image")

        dress = Dress.objects.create(
            shop=shop,
            name=name,
            description=description,
            size=size,
            daily_price=daily_price,
            deposit=deposit,
            shipping_fee=shipping_fee,
            image=image,
        )

        category_ids = request.POST.get("categories", "").split(",")
        category_ids = [int(cid) for cid in category_ids if cid.strip().isdigit()]
        if category_ids:
            dress.categories.set(category_ids)

        tpl_id = request.POST.get("price_template_id")
        max_days_override = request.POST.get("max_days_override")

        if tpl_id and tpl_id.isdigit():
            tpl = PriceTemplate.objects.filter(id=int(tpl_id), store=shop).first()
            if tpl:
                dress.price_template = tpl

        if max_days_override and str(max_days_override).isdigit():
            md = int(max_days_override)
            if md > 0:
                dress.max_rental_days_override = md

        dress.save()
        messages.success(request, "เพิ่มชุดใหม่เรียบร้อยแล้ว")
        return redirect("dress:store_dress", store_id=store_id)

    categories = Category.objects.all()
    price_templates = shop.price_templates.order_by("name")

    rule = getattr(shop, "shipping_rule", None)
    if rule:
        shipping_init = {
            "clamp_to_max": bool(rule.clamp_to_max),
            "brackets": [
                {"min_qty": b.min_qty, "max_qty": b.max_qty, "fee": str(b.fee)}
                for b in rule.brackets.order_by("min_qty")
            ],
        }
    else:
        shipping_init = {"clamp_to_max": True, "brackets": []}

    return render(
        request,
        "dress/add_dress.html",
        {
            "store": shop,
            "categories": categories,
            "price_templates": price_templates,
            "shipping_init_json": json.dumps(shipping_init, ensure_ascii=False),
        },
    )


def _assert_store_owner(store: Shop, user):
    return (store.owner_id == getattr(user, "id", None)) or getattr(user, "is_superuser", False)

# แก้ไขชุด
@shop_approved_required
@login_required(login_url="dress:login")
def edit_dress(request, store_id, dress_id):
    shop = get_object_or_404(Shop, id=store_id, owner=request.user)
    dress = get_object_or_404(Dress, id=dress_id, shop=shop)

    if request.method == "POST":
        dress.name = request.POST.get("name", "").strip()
        dress.description = request.POST.get("description", "").strip()
        dress.size = request.POST.get("size", "").strip()
        dress.daily_price = float(request.POST.get("daily_price") or 0)
        dress.deposit = float(request.POST.get("deposit") or 0)
        dress.shipping_fee = float(request.POST.get("shipping_fee") or 0)
        dress.stock = int(request.POST.get("stock") or 1)

        selected_cats = request.POST.getlist("categories")
        if selected_cats:
            cats = [int(cid) for cid in selected_cats if str(cid).isdigit()]
            dress.categories.set(cats)

        if request.POST.get("remove_image") == "1":
            if dress.image:
                dress.image.delete(save=False)
            dress.image = None
        elif request.FILES.get("image"):
            dress.image = request.FILES.get("image")

        tpl_id = request.POST.get("price_template_id")
        if tpl_id and tpl_id.isdigit():
            tpl = PriceTemplate.objects.filter(id=int(tpl_id), store=shop).first()
            dress.price_template = tpl
        elif tpl_id == "" or tpl_id is None:
            dress.price_template = None

        max_days_override = request.POST.get("max_days_override")
        if max_days_override and str(max_days_override).isdigit():
            md = int(max_days_override)
            dress.max_rental_days_override = md if md > 0 else None
        else:
            dress.max_rental_days_override = None

        dress.save()
        messages.success(request, "แก้ไขชุดเรียบร้อยแล้ว")
        return redirect("dress:store_dress", store_id=store_id)

    categories = Category.objects.all()
    price_templates = shop.price_templates.order_by("name")

    tpl_preview_items = []
    if dress.price_template:
        tpl_preview_items = list(
            dress.price_template.items.order_by("day_count").values("day_count", "total_price")
        )

    rule = getattr(shop, "shipping_rule", None)
    if rule:
        shipping_init = {
            "clamp_to_max": bool(rule.clamp_to_max),
            "brackets": [
                {"min_qty": b.min_qty, "max_qty": b.max_qty, "fee": str(b.fee)}
                for b in rule.brackets.order_by("min_qty")
            ],
        }
    else:
        shipping_init = {"clamp_to_max": True, "brackets": []}

    return render(
        request,
        "dress/edit_dress.html",
        {
            "store": shop,
            "dress": dress,
            "categories": categories,
            "price_templates": price_templates,
            "tpl_preview_items": tpl_preview_items,
            "shipping_init_json": json.dumps(shipping_init, ensure_ascii=False),
        },
    )


# ---------- API: Price Template ----------
@login_required(login_url="dress:login")
def api_get_price_template(request, store_id: int, tpl_id: int):
    store = get_object_or_404(Shop, id=store_id)
    if not _assert_store_owner(store, request.user):
        return JsonResponse({"ok": False, "error": "ไม่มีสิทธิ์จัดการร้านนี้"}, status=403)

    tpl = get_object_or_404(PriceTemplate, id=tpl_id, store=store)
    payload = {
        "id": tpl.id,
        "name": tpl.name,
        "max_days": tpl.max_days,
        "items": [
            {"day_count": it.day_count, "total_price": str(it.total_price)}
            for it in tpl.items.order_by("day_count")
        ],
    }
    return JsonResponse({"ok": True, "template": payload})


@login_required(login_url="dress:login")
@require_POST
def api_update_price_template(request, store_id: int, tpl_id: int):
    store = get_object_or_404(Shop, id=store_id)
    if not _assert_store_owner(store, request.user):
        return JsonResponse({"ok": False, "error": "ไม่มีสิทธิ์จัดการร้านนี้"}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "รูปแบบข้อมูลไม่ถูกต้อง"}, status=400)

    name = (payload.get("name") or "").strip()
    max_days = payload.get("max_days")
    items = payload.get("items") or []

    tpl = get_object_or_404(PriceTemplate, id=tpl_id, store=store)

    if not name:
        return JsonResponse({"ok": False, "error": "กรุณากรอกชื่อเทมเพลต"}, status=400)
    if not isinstance(max_days, int) or max_days < 1:
        return JsonResponse({"ok": False, "error": "จำนวนวันสูงสุดต้องเป็นจำนวนเต็ม >= 1"}, status=400)
    if not items:
        return JsonResponse({"ok": False, "error": "กรุณาใส่รายการราคาอย่างน้อย 1 แถว"}, status=400)

    normalized = []
    seen = set()
    for row in items:
        day = int(row.get("day_count") or 0)
        price_raw = row.get("total_price")
        try:
            price = Decimal(str(price_raw))
        except Exception:
            return JsonResponse({"ok": False, "error": f"ราคาของ {day} วัน ไม่ถูกต้อง"}, status=400)

        if day < 1 or day > max_days:
            return JsonResponse({"ok": False, "error": f"จำนวนวัน {day} เกิน {max_days}"}, status=400)
        if day in seen:
            return JsonResponse({"ok": False, "error": f"วัน {day} ซ้ำกัน"}, status=400)
        if price < 0:
            return JsonResponse({"ok": False, "error": f"ราคา {day} วัน ต้องไม่ติดลบ"}, status=400)
        seen.add(day)
        normalized.append((day, price))

    with transaction.atomic():
        tpl.name = name
        tpl.max_days = max_days
        tpl.save()
        tpl.items.all().delete()
        PriceTemplateItem.objects.bulk_create([
            PriceTemplateItem(template=tpl, day_count=d, total_price=p) for d, p in normalized
        ])

    return JsonResponse({
        "ok": True,
        "template": {"id": tpl.id, "name": tpl.name, "max_days": tpl.max_days}
    })


# ======================================================================
# ลบชุด
# ======================================================================
@shop_approved_required
@login_required(login_url="dress:login")
def delete_dress(request, store_id, dress_id):
    shop = get_object_or_404(Shop, id=store_id, owner=request.user)
    dress = get_object_or_404(Dress, id=dress_id, shop=shop)
    if request.method == "POST":
        if dress.image:
            dress.image.delete(save=False)
        dress.delete()
        messages.success(request, "ลบชุดเรียบร้อยแล้ว")
        return redirect("dress:store_dress", store_id=store_id)
    return render(request, "dress/delete_dress.html", {"store": shop, "dress": dress})

# เปิด/ปิดให้เช่า
@login_required(login_url="dress:login")
def toggle_availability(request, store_id, dress_id):
    shop = get_object_or_404(Shop, id=store_id, owner=request.user)
    dress = get_object_or_404(Dress, id=dress_id, shop=shop)
    dress.is_available = not dress.is_available
    dress.save()
    if dress.is_available:
        messages.success(request, f"{dress.name} เปิดให้เช่าแล้ว")
    else:
        messages.warning(request, f"{dress.name} ปิดการเช่าชั่วคราว")
    return redirect("dress:store_dress", store_id=store_id)

# หน้าควบคุมหลังร้าน
@login_required(login_url="dress:login")
@require_POST
def send_shop_message(request, order_id):
    """
    ให้เจ้าของร้านส่งข้อความถึงลูกค้า ผ่าน Notification type=shop_message
    """
    order = get_object_or_404(RentalOrder, id=order_id)

    # เช็คให้แน่ใจว่าคนที่ส่งเป็นเจ้าของร้านนี้จริง
    if order.rental_shop.owner != request.user and not request.user.is_superuser:
        messages.error(request, "คุณไม่มีสิทธิ์ส่งข้อความสำหรับออเดอร์นี้")
        return redirect("dress:back_office", store_id=order.rental_shop.id)

    title = request.POST.get("title", "").strip() or "ข้อความจากร้าน"
    message = request.POST.get("message", "").strip()

    if not message:
        messages.error(request, "กรุณากรอกข้อความ")
        return redirect("dress:back_office", store_id=order.rental_shop.id)

    create_notification(
        user=order.user,
        title=title,
        message=message,
        type="shop_message",
        order=order,
        sender_shop=order.rental_shop,
    )

    messages.success(request, "ส่งข้อความถึงลูกค้าเรียบร้อยแล้ว")
    return redirect("dress:back_office", store_id=order.rental_shop.id)


# ==============================================================================================
# รีวิวชุด
# ==============================================================================================
def review_list(request, dress_id):
    dress = get_object_or_404(Dress, pk=dress_id)
    sort = request.GET.get('sort', 'newest')

    reviews = Review.objects.filter(dress=dress)
    if sort == 'high_rating':
        reviews = reviews.order_by('-rating')
    elif sort == 'low_rating':
        reviews = reviews.order_by('rating')
    elif sort == 'oldest':
        reviews = reviews.order_by('created_at')
    else:
        reviews = reviews.order_by('-created_at')

    return render(request, 'dress/review_list.html', {'dress': dress, 'reviews': reviews})

# ดูรายละเอียดชุด
def dress_detail(request, dress_id):
    dress = get_object_or_404(Dress, pk=dress_id)

    # ถ้าชุดถูกเก็บลงคลัง และคนที่เปิดไม่ใช่เจ้าของร้าน / แอดมิน → ไม่ให้ดู
    if dress.is_archived and request.user != dress.shop.owner and not request.user.is_superuser:
        raise Http404("ไม่พบชุดนี้")


    # รีวิว
    reviews = Review.objects.filter(dress=dress)
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    latest_reviews = reviews.order_by('-created_at')[:2]

    # เช็ค favorite
    is_favorite = False
    if request.user.is_authenticated:
        is_favorite = Favorite.objects.filter(user=request.user, dress=dress).exists()

    # ชุดอื่นในร้านเดียวกัน
    related_dresses = Dress.objects.filter(shop=dress.shop).exclude(id=dress.id)[:4]

    # แพ็กเกจราคา
    pack_prices = []
    if dress.price_template:
        for it in dress.price_template.items.order_by('day_count'):
            if it.day_count <= dress.allowed_max_days():
                pack_prices.append({"days": it.day_count, "price": it.total_price})
    else:
        overrides = list(dress.override_prices.order_by('day_count'))
        if overrides:
            for it in overrides:
                if it.day_count <= dress.allowed_max_days():
                    pack_prices.append({"days": it.day_count, "price": it.total_price})
        else:
            maxd = min(dress.allowed_max_days(), 8)
            if float(dress.daily_price) > 0:
                for d in range(1, maxd + 1):
                    pack_prices.append({"days": d, "price": dress.daily_price * d})

    # กฎค่าส่ง
    shipping_tiers = []
    shipping_clamp_note = None
    rule = getattr(dress.shop, "shipping_rule", None)
    if rule:
        for b in rule.brackets.all().order_by("min_qty"):
            shipping_tiers.append({"min_qty": b.min_qty, "max_qty": b.max_qty, "fee": b.fee})
        if rule.clamp_to_max and rule.brackets.exists():
            top = rule.brackets.order_by("-max_qty").first()
            shipping_clamp_note = f"มากกว่า {top.max_qty} ชุด คิดค่าส่ง {top.fee} บาท"

    # -----------------------------
    # เพิ่มส่วนคำนวณยอดเช่า / จำนวนคงเหลือ
    # -----------------------------
    # ออเดอร์ทั้งหมดของชุดนี้ (ใช้ related_name จากโมเดล RentalOrder)
    orders_qs = dress.rental_orders.all()  # ถ้า related_name ไม่ใช่อันนี้ ให้เปลี่ยนตามโมเดล

    # 1) เคยถูกเช่าไปแล้วทั้งหมดกี่ครั้ง (ออเดอร์สถานะเช่าสำเร็จ / เคยเช่าแล้ว)
    finished_orders = orders_qs.filter(
        status__in=[
            RentalOrder.STATUS_IN_RENTAL,
            RentalOrder.STATUS_WAITING_RETURN,
            RentalOrder.STATUS_RETURNED,
        ]
    )
    total_rented = finished_orders.count()

    # 2) ตอนนี้กำลังถูกเช่าอยู่กี่ชุด (ยังไม่คืน)
    active_orders = orders_qs.filter(
        status__in=[
            RentalOrder.STATUS_IN_RENTAL,
            RentalOrder.STATUS_WAITING_RETURN,
        ]
    )
    currently_rented = active_orders.count()

    # 3) จำนวนคงเหลือให้เช่า = stock - จำนวนที่กำลังถูกเช่าอยู่
    base_stock = dress.stock or 0
    remaining_stock = max(base_stock - currently_rented, 0)

    return render(request, "dress/dress_detail.html", {
        "dress": dress,
        "review_count": reviews.count(),
        "avg_rating": round(avg_rating, 1),
        "latest_reviews": latest_reviews,
        "is_favorite": is_favorite,
        "related_dresses": related_dresses,
        "pack_prices": pack_prices,
        "shipping_tiers": shipping_tiers,
        "shipping_clamp_note": shipping_clamp_note,

        # ตัวแปรใหม่ส่งไป template
        "total_rented": total_rented,          # เคยถูกเช่าทั้งหมดกี่ครั้ง
        "remaining_stock": remaining_stock,    # เหลือให้เช่าอีกกี่ชุด
    })


# เพิ่มรีวิว
@login_required(login_url="dress:login")
def review_create(request, dress_id):
    dress = get_object_or_404(Dress, pk=dress_id)
    if request.method == 'POST':
        comment = request.POST.get('comment')
        rating = request.POST.get('rating')
        image = request.FILES.get("image")

        if not comment or not rating:
            messages.error(request, "กรุณากรอกข้อมูลให้ครบถ้วน")
        else:
            Review.objects.create(
                dress=dress,
                user=request.user,
                comment=comment,
                rating=rating,
                image=image
            )
            messages.success(request, "เพิ่มรีวิวเรียบร้อยแล้ว")
            return redirect('dress:review_list', dress_id=dress.id)

    return render(request, 'dress/review_form.html', {'dress': dress})

# แก้ไขรีวิว
@login_required(login_url="dress:login")
def review_edit(request, dress_id, review_id):
    dress = get_object_or_404(Dress, pk=dress_id)
    review = get_object_or_404(Review, pk=review_id, user=request.user)

    if request.method == 'POST':
        review.rating = request.POST.get('rating')
        review.comment = request.POST.get('comment')
        if 'image' in request.FILES:
            review.image = request.FILES['image']
        review.save()
        messages.success(request, "อัปเดตรีวิวเรียบร้อยแล้ว")
        return redirect('dress:review_list', dress_id=dress.id)

    return render(request, 'dress/review_edit.html', {'dress': dress, 'review': review})

#ลบรีวิว
@login_required(login_url="dress:login")
def review_delete(request, dress_id, review_id):
    dress = get_object_or_404(Dress, pk=dress_id)
    review = get_object_or_404(Review, pk=review_id, user=request.user)

    if request.method == 'POST':
        review.delete()
        messages.success(request, "ลบรีวิวเรียบร้อยแล้ว")
        return redirect('dress:review_list', dress_id=dress.id)

    return redirect('dress:review_list', dress_id=dress.id)


# =============================================================================================
# Favorites
# =============================================================================================
@login_required(login_url="dress:login")
def add_to_favorite(request, dress_id):
    dress = get_object_or_404(Dress, pk=dress_id)
    Favorite.objects.get_or_create(user=request.user, dress=dress)
    messages.success(request, "บันทึกชุดนี้ไว้ในรายการโปรดแล้ว")
    return redirect('dress:dress_detail', dress_id=dress.id)

#สลับสถานะรายการโปรด
@login_required(login_url="dress:login")
def toggle_favorite(request, dress_id):
    dress = get_object_or_404(Dress, id=dress_id)
    favorite, created = Favorite.objects.get_or_create(user=request.user, dress=dress)

    if not created:
        favorite.delete()
        is_favorite = False
    else:
        is_favorite = True

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'is_favorite': is_favorite})

    return redirect('dress:dress_detail', dress_id=dress.id)

#รายการโปรดทั้งหมด
@login_required(login_url="dress:login")
def favorite_list(request):
    favorites = Favorite.objects.filter(user=request.user).select_related("dress")
    return render(request, "dress/favorite_list.html", {"favorites": favorites})

# นับจำนวนรายการโปรด (API)
@login_required(login_url="dress:login")
def favorite_count_api(request):
    count = Favorite.objects.filter(user=request.user).count()
    return JsonResponse({'count': count})


# ================================================================================
# Cart
# ================================================================================
@login_required(login_url="dress:login")
def cart_view(request):
    cart_items = CartItem.objects.filter(user=request.user).select_related("dress", "dress__shop")

    grouped_cart = {}
    total_price = 0

    for item in cart_items:
        shop = item.dress.shop
        item_total = float(item.dress.daily_price) * item.quantity
        total_price += item_total

        if shop not in grouped_cart:
            grouped_cart[shop] = {"items": [], "total": 0}

        grouped_cart[shop]["items"].append(item)
        grouped_cart[shop]["total"] += item_total

    return render(request, "dress/cart.html", {
        "cart_items": cart_items,
        "grouped_cart": grouped_cart,
        "total_price": total_price,
    })

# เพิ่มสินค้าลงตะกร้า
@login_required(login_url="dress:login")
def add_to_cart(request, dress_id):
    dress = get_object_or_404(Dress, pk=dress_id)
    cart_item, created = CartItem.objects.get_or_create(user=request.user, dress=dress)
    if not created:
        cart_item.quantity += 1
        cart_item.save()
        messages.info(request, "เพิ่มจำนวนสินค้าในตะกร้าแล้ว")
    else:
        messages.success(request, "เพิ่มสินค้าในตะกร้าสำเร็จ")
    return redirect('dress:dress_detail', dress_id=dress.id)


def cart_item_count(request):
    count = CartItem.objects.filter(user=request.user).count() if request.user.is_authenticated else 0
    return JsonResponse({'count': count})

# ลบสินค้าหลายรายการจากตะกร้า
@csrf_exempt
@login_required(login_url="dress:login")
def remove_bulk(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        ids = data.get("ids", [])
        if not ids:
            return JsonResponse({"status": "error", "message": "ไม่มีสินค้าให้ลบ"}, status=400)

        items = CartItem.objects.filter(user=request.user, id__in=ids)
        if not items.exists():
            return JsonResponse({"status": "error", "message": "ไม่พบสินค้าที่ต้องการลบ"}, status=404)

        deleted_count = items.count()
        items.delete()

        return JsonResponse({"status": "ok", "message": f"ลบสินค้าที่เลือกแล้ว ({deleted_count} รายการ)"})
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "ข้อมูลไม่ถูกต้อง"}, status=400)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

#ย้ายไปยังรายการโปรด
@csrf_exempt
@login_required(login_url="dress:login")
def move_to_favorite(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        ids = data.get("ids", [])
        if not ids:
            return JsonResponse({"status": "error", "message": "ไม่มีสินค้าให้ย้าย"}, status=400)

        items = CartItem.objects.filter(user=request.user, id__in=ids)
        if not items.exists():
            return JsonResponse({"status": "error", "message": "ไม่พบสินค้าที่ต้องการย้าย"}, status=404)

        moved_count = 0
        for item in items:
            Favorite.objects.get_or_create(user=request.user, dress=item.dress)
            item.delete()
            moved_count += 1

        return JsonResponse({"status": "ok", "message": f"ย้ายสินค้าไปยังรายการโปรดแล้ว ({moved_count} รายการ)"})
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "ข้อมูลไม่ถูกต้อง"}, status=400)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

#อัปเดตจำนวนสินค้าในตะกร้าแบบ AJAX ใช้ตอนกดปุ่ม + / – ในหน้า Cart
@csrf_exempt
@login_required(login_url="dress:login")
def update_quantity(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            item_id = data.get("id")
            action = data.get("action")

            item = CartItem.objects.get(id=item_id, user=request.user)

            if action == "increase":
                item.quantity += 1
            elif action == "decrease" and item.quantity > 1:
                item.quantity -= 1
            item.save()

            return JsonResponse({
                "status": "ok",
                "new_quantity": item.quantity,
                "item_total": float(item.dress.daily_price) * item.quantity
            })
        # ส่วนจับ error
        except CartItem.DoesNotExist:
            return JsonResponse({"status": "error", "message": "ไม่พบสินค้า"}, status=404)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    return JsonResponse({"status": "error", "message": "Invalid request"}, status=405)


# ================================================================================================
# ประวัติ/โปรไฟล์
# ================================================================================================
@login_required(login_url="dress:login")
def rental_history_view(request):
    """
    แสดงประวัติการเช่าของลูกค้า
    - เอาเฉพาะออเดอร์ที่สิ้นสุดการเช่าจริง ๆ แล้ว
      เช่น คืนชุดแล้ว / completed เดิม / damaged (ถ้าต้องการให้เห็นในประวัติ)
    """
    orders = (
        RentalOrder.objects
        .filter(
            user=request.user,
            status__in=[
                RentalOrder.STATUS_RETURNED,   # คืนชุดแล้ว
                "completed",                   # กันเคสข้อมูลเก่า
                RentalOrder.STATUS_DAMAGED,    # ถ้าต้องการให้ขึ้นในประวัติด้วย
            ],
        )
        .select_related("dress", "rental_shop")
        .order_by("-return_date", "-created_at")
    )

    context = {
        "rentals": orders,   # ใช้ชื่อ rentals เหมือนเดิม เพื่อให้ template เดิมยังใช้ได้
    }
    return render(request, "dress/rental_history.html", context)

# ระบบแจ้งเตือน
@login_required(login_url="dress:login")
def notification_page(request):
    # ดึงรายการแจ้งเตือนทั้งหมดของผู้ใช้
    notifications = (
        Notification.objects
        .filter(user=request.user)
        .select_related("related_order", "sender_shop")
        .order_by("-created_at")
    )

    # อัปเดตแจ้งเตือนที่ยังไม่อ่านให้เป็นอ่านแล้ว
    Notification.objects.filter(
        user=request.user,
        is_read=False
    ).update(is_read=True)

    return render(request, "dress/notification.html", {
        "notifications": notifications
    })




# ระบบ "การเช่าของฉัน"
@login_required(login_url="dress:login")
def rental_list_view(request):
    """
    หน้า 'การเช่าของฉัน'
    """
    today = timezone.localdate()

    # 1) กำลังเช่าอยู่
    current_rentals = RentalOrder.objects.filter(
        user=request.user,
        status__in=[
            RentalOrder.STATUS_PAID,        # จ่ายแล้ว แต่ยังไม่ถึงวันรับ
            RentalOrder.STATUS_IN_RENTAL,   # รับชุดแล้ว → อยู่ระหว่างการเช่า
            RentalOrder.STATUS_SHIPPING,    # ร้านกดส่งแล้ว
            RentalOrder.STATUS_PREPARING,   # ร้านกำลังเตรียมส่ง
        ],
        pickup_date__lte=today,
        return_date__gte=today,
    ).select_related("dress", "rental_shop").order_by("pickup_date")

    # 2) เช่าในอนาคต
    upcoming_rentals = RentalOrder.objects.filter(
        user=request.user,
        status__in=[
            RentalOrder.STATUS_PAID,
            RentalOrder.STATUS_PREPARING,
            RentalOrder.STATUS_SHIPPING,
        ],
        pickup_date__gt=today,
    ).select_related("dress", "rental_shop").order_by("pickup_date")

    # 3) เช่าเสร็จแล้ว
    completed_rentals = RentalOrder.objects.filter(
        user=request.user,
        status__in=[
            RentalOrder.STATUS_RETURNED,   # คืนชุดแล้ว
            RentalOrder.STATUS_WAITING_RETURN,
            RentalOrder.STATUS_DAMAGED,
            "completed",                   # กันข้อมูลเก่า
        ],
        return_date__lte=today,
    ).select_related("dress", "rental_shop").order_by("-return_date")

    context = {
        "current_rentals": current_rentals,
        "upcoming_rentals": upcoming_rentals,
        "completed_rentals": completed_rentals,
        "today": today,
    }
    return render(request, "dress/rental_list.html", context)



#ยกเลิกการเช่า
@login_required(login_url="dress:login")
def cancel_rental(request, order_id):
    """
    ยกเลิกการเช่าได้เฉพาะออเดอร์ของตัวเอง
    ที่ยังไม่ถึงวันรับชุด และสถานะยังเป็น paid
    """
    order = get_object_or_404(RentalOrder, id=order_id, user=request.user)
    today = timezone.localdate()

    # เงื่อนไขไม่ให้ยกเลิกถ้าเริ่มเช่าแล้วหรือยกเลิกไปแล้ว
    if order.status != "paid" or order.pickup_date <= today:
        messages.error(request, "ไม่สามารถยกเลิกการเช่านี้ได้")
        return redirect("dress:rental_list")

    if request.method == "POST":
        order.status = "cancelled"
        order.save()
        messages.success(request, "ยกเลิกการเช่าสำเร็จแล้ว")
        return redirect("dress:rental_list")

    # ถ้าอยากให้ยืนยันก่อนยกเลิก สามารถทำหน้า template แยกได้
    # ตอนนี้จะยกเลิกทันทีจากปุ่มในหน้า my-rentals
    return redirect("dress:rental_list")

# โปรไฟล์ผู้ใช้
@login_required(login_url='dress:login')
def profile_page(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(request, 'dress/profile.html', {'profile': profile})

# บันทึกการแก้ไขโปรไฟล์
@login_required(login_url='dress:login')
def update_profile(request):
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    if request.method == "POST":
        user.username = request.POST.get("username", user.username)#อัปเดตข้อมูลในตาราง User (ของ Django auth ปกติ)
        user.email = request.POST.get("email", user.email)
        user.save()

        profile.gender = request.POST.get("gender", profile.gender)#อัปเดตข้อมูลในตาราง UserProfile
        profile.birth_date = request.POST.get("birth_date") or profile.birth_date
        profile.phone = request.POST.get("phone", profile.phone)
        profile.address = request.POST.get("address", profile.address)

        if request.FILES.get("profile_image"):#อัปโหลดรูปโปรไฟล์ (ถ้ามี)
            profile.profile_image = request.FILES["profile_image"]

        profile.save()
        messages.success(request, "อัปเดตโปรไฟล์เรียบร้อยแล้ว")
        return redirect("dress:profile_page")

    return redirect("dress:profile_page")

#วิธีการเช่า
def how_to_rent(request):
    return render(request, "dress/how_to_rent.html")


#==============================================================================================
# หน้าควบคุมหลังร้าน
#==============================================================================================
@login_required(login_url='dress:login')
def back_office(request, store_id):
    store = get_object_or_404(Shop, id=store_id, owner=request.user)

    active_dresses = store.dresses.filter(is_archived=False)
    archived_dresses = store.dresses.filter(is_archived=True)

    orders_qs = RentalOrder.objects.filter(rental_shop=store)

    # 1) คำเช่าใหม่ / รอจัดการ
    new_count = orders_qs.filter(
        status__in=[
            RentalOrder.STATUS_NEW,
            RentalOrder.STATUS_WAITING_PAY,
            RentalOrder.STATUS_PAID,
        ]
    ).count()

    # 2) เตรียมจัดส่งและจัดส่ง
    shipping_count = orders_qs.filter(
        status__in=[
            RentalOrder.STATUS_PREPARING,
            RentalOrder.STATUS_SHIPPING,
        ]
    ).count()

    # 3) เช่าสำเร็จ / คืนชุดแล้ว
    completed_count = orders_qs.filter(
        status__in=[
            RentalOrder.STATUS_IN_RENTAL,
            RentalOrder.STATUS_WAITING_RETURN,
            RentalOrder.STATUS_RETURNED,
        ]
    ).count()

    # 4) ออเดอร์ยกเลิก / มีปัญหา
    cancelled_count = orders_qs.filter(
        status__in=[
            RentalOrder.STATUS_CANCELLED,
            RentalOrder.STATUS_DAMAGED,
            "cancelled",
            "damaged",
        ]
    ).count()

    # 5) รีวิวทั้งหมดของร้าน
    reviews_qs = Review.objects.filter(dress__shop=store)
    review_count = reviews_qs.count()

    # 6) ห้องแชทที่มีข้อความล่าสุดมาจากลูกค้า (ถือว่ายังไม่ได้อ่าน)
    threads = (
        ShopChatThread.objects
        .filter(shop=request.user)
        .prefetch_related("messages")
    )

    unread_chat_count = 0
    for t in threads:
        last_msg = t.messages.order_by("-created_at").first()
        if last_msg and last_msg.sender_id != request.user.id:
            unread_chat_count += 1

    context = {
        "store": store,
        "new_count": new_count,
        "shipping_count": shipping_count,
        "cancelled_count": cancelled_count,
        "completed_count": completed_count,
        "review_count": review_count,
        "unread_chat_count": unread_chat_count,
    }
    return render(request, "dress/back_office.html", context)





@login_required(login_url="dress:login")
@require_POST
def back_office_update_order_status(request, store_id, order_id):
    """
    อัปเดตสถานะคำสั่งเช่าจากปุ่มในหน้าหลังร้าน เช่น
    - set_preparing       -> เตรียมจัดส่ง
    - set_shipping        -> จัดส่งเรียบร้อย
    - set_in_rental       -> อยู่ระหว่างการเช่า (ลูกค้ารับชุดแล้ว)
    - set_waiting_return  -> รอคืนชุด
    - set_returned        -> คืนชุดแล้ว
    - set_damaged         -> พบปัญหาชุดชำรุด
    - set_cancelled       -> ออเดอร์ยกเลิก
    """
    #ตรวจสอบสิทธิ์ร้าน + ดึงออเดอร์
    store = get_object_or_404(Shop, id=store_id, owner=request.user)
    order = get_object_or_404(RentalOrder, id=order_id, rental_shop=store)

    action = request.POST.get("action")

    # map ค่าที่มาจากปุ่ม -> สถานะในระบบ
    ACTION_TO_STATUS = {
        "set_preparing":      RentalOrder.STATUS_PREPARING,
        "set_shipping":       RentalOrder.STATUS_SHIPPING,
        "set_in_rental":      RentalOrder.STATUS_IN_RENTAL,     
        "set_waiting_return": RentalOrder.STATUS_WAITING_RETURN,
        "set_returned":       RentalOrder.STATUS_RETURNED,
        "set_damaged":        RentalOrder.STATUS_DAMAGED,
        "set_cancelled":      RentalOrder.STATUS_CANCELLED,
    }

    target_status = ACTION_TO_STATUS.get(action)
    # ถ้า action ไม่ถูกต้อง
    if not target_status:
        messages.error(request, "ไม่พบคำสั่งที่ต้องการเปลี่ยนสถานะ")
        # ถ้าไม่มี HTTP_REFERER ให้กลับไปหลังร้านหลัก
        referer = request.META.get("HTTP_REFERER")
        if referer:
            return redirect(referer)
        return redirect("dress:back_office", store_id=store.id)

    # เปลี่ยนสถานะจริงในฐานข้อมูล
    order.status = target_status
    order.save()

    # ============================
    # แจ้งเตือนลูกค้าเมื่อสถานะเปลี่ยน
    # ============================
    # title สำหรับ Notification
    notif_title_map = {
        RentalOrder.STATUS_PREPARING:      "ร้านกำลังเตรียมชุดของคุณ",
        RentalOrder.STATUS_SHIPPING:       "ร้านได้จัดส่งชุดของคุณแล้ว",
        RentalOrder.STATUS_IN_RENTAL:      "คุณได้รับชุดเรียบร้อยแล้ว",
        RentalOrder.STATUS_WAITING_RETURN: "ใกล้ถึงกำหนดคืนชุด",
        RentalOrder.STATUS_RETURNED:       "ร้านยืนยันการคืนชุดแล้ว",
        RentalOrder.STATUS_DAMAGED:        "พบปัญหาชุดเช่าของคุณ",
        RentalOrder.STATUS_CANCELLED:      "คำสั่งเช่าถูกยกเลิก",
    }

    # message สำหรับ Notification
    notif_message_map = {
    RentalOrder.STATUS_PREPARING: (
        f"ร้าน {store.name} ได้ยืนยันการเช่าและกำลังเตรียมชุดให้คุณ "
        "เมื่อจัดส่งแล้วคุณจะได้รับการแจ้งเตือนอีกครั้ง"
    ),
    RentalOrder.STATUS_SHIPPING: (
        f"ร้าน {store.name} ได้จัดส่งชุดหมายเลขคำสั่งเช่า #{order.id} แล้ว "
        "โปรดรอรับพัสดุตามช่องทางที่คุณเลือก"
    ),
    RentalOrder.STATUS_IN_RENTAL: (
        f"ร้าน {store.name} ยืนยันว่าคุณได้รับชุดสำหรับคำสั่งเช่า #{order.id} แล้ว "
        "ระบบเริ่มนับวันเช่าตามช่วงวันที่ที่คุณเลือก"
    ),
    RentalOrder.STATUS_WAITING_RETURN: (
        f"ถึงกำหนดคืนชุดสำหรับคำสั่งเช่า #{order.id} แล้ว "
        f"โปรดเตรียมส่งคืนตามเงื่อนไขของร้าน {store.name}"
    ),
    RentalOrder.STATUS_RETURNED: (
        f"ร้าน {store.name} ยืนยันว่าคุณคืนชุดสำหรับคำสั่งเช่า #{order.id} แล้ว "
        "ขอบคุณที่ใช้บริการ"
    ),
    RentalOrder.STATUS_DAMAGED: (
        f"ร้าน {store.name} แจ้งว่าพบปัญหาชุดชำรุดในคำสั่งเช่า #{order.id} "
        "กรุณาติดต่อร้านเพื่อชี้แจงรายละเอียดเพิ่มเติม"
    ),
    RentalOrder.STATUS_CANCELLED: (
        f"คำสั่งเช่า #{order.id} ถูกยกเลิกแล้ว "
        f"หากมีข้อสงสัยกรุณาติดต่อร้าน {store.name}"
    ),
}


    notif_title = notif_title_map.get(target_status, "อัปเดตสถานะคำสั่งเช่า")
    notif_message = notif_message_map.get(target_status, "ร้านได้อัปเดตสถานะคำสั่งเช่าของคุณแล้ว")

    # สร้าง Notification ให้ลูกค้าคนที่เช่าชุดนี้
    create_notification(
        user=order.user,
        title=notif_title,
        message=notif_message,
        type="order",
        order=order,
        sender_shop=store,
    )
    # ============================ จบส่วนแจ้งเตือน ============================

    # สร้างข้อความแจ้งเตือนสำหรับแถบ messages ของระบบ (ในหลังบ้าน)
    status_text_map = {
        RentalOrder.STATUS_PREPARING: "ยืนยันให้เช่าและย้ายไปสถานะ 'กำลังเตรียมจัดส่ง' แล้ว",
        RentalOrder.STATUS_SHIPPING: "ออเดอร์ถูกย้ายไปสถานะ 'จัดส่งเรียบร้อย' แล้ว",
        RentalOrder.STATUS_IN_RENTAL: "ออเดอร์ถูกย้ายไปสถานะ 'อยู่ระหว่างการเช่า' แล้ว",
        RentalOrder.STATUS_WAITING_RETURN: "ออเดอร์ถูกย้ายไปสถานะ 'รอคืนชุด' แล้ว",
        RentalOrder.STATUS_RETURNED: "ออเดอร์ถูกย้ายไปสถานะ 'คืนชุดแล้ว' แล้ว",
        RentalOrder.STATUS_DAMAGED: "ออเดอร์ถูกย้ายไปสถานะ 'พบปัญหาชุดชำรุด' แล้ว",
        RentalOrder.STATUS_CANCELLED: "ออเดอร์ถูกย้ายไปสถานะ 'ออเดอร์ยกเลิก' แล้ว",
    }

    msg = status_text_map.get(target_status, "อัปเดตสถานะคำสั่งเช่าเรียบร้อยแล้ว")
    messages.success(request, msg)

    # กลับไป "หน้าเดิม" ที่กดปุ่ม (เช่น /my-store/1/orders/paid/)
    referer = request.META.get("HTTP_REFERER")
    if referer:
        return redirect(referer)

    # กันพลาด ถ้าไม่มี referer ให้กลับไปหลังร้าน
    return redirect("dress:back_office", store_id=store.id)




# ฟังก์ชันนี้คือ “หน้าคำเช่าใหม่” ในหลังร้านของเจ้าของร้านเช่าชุด
@login_required(login_url='dress:login')
def back_office_orders_new(request, store_id):
    store = get_object_or_404(Shop, id=store_id, owner=request.user)# ดึงร้านของเจ้าของร้านที่ล็อกอินอยู่
    today = timezone.localdate()#เอาวันปัจจุบัน (ใช้เทียบกับวันรับชุด)
    
    # ดึง “คำเช่าใหม่” ของร้านนี้
    # คำเช่าใหม่: new + waiting_payment + paid ที่ยังไม่ถึงวันรับ
    orders = (
        RentalOrder.objects
        .filter(
            rental_shop=store,
            status__in=[
                RentalOrder.STATUS_NEW,
                RentalOrder.STATUS_WAITING_PAY,
                RentalOrder.STATUS_PAID,
            ],
            pickup_date__gte=today,
        )
        .select_related('user', 'dress')
        .order_by('-pickup_date', '-created_at')
    )

    context = {
        "store": store,
        "page_title": "คำเช่าใหม่",
        "orders": orders,
        "active_tab": "new",
    }
    return render(request, "dress/back_office_orders.html", context)

# ฟังก์ชันนี้คือ “หน้ารอชำระเงิน” หลังร้าน (สำหรับร้านที่ให้ลูกค้าเลือกแบบจ่ายที่หน้าร้าน หรือยังไม่ชำระ)
@login_required(login_url='dress:login')
def back_office_orders_pending_payment(request, store_id):
    """รอชำระเงิน (ลูกค้าเลือกชำระที่หน้าร้าน / ยังไม่จ่าย)"""
    store = get_object_or_404(Shop, id=store_id, owner=request.user)

    # ดึงออเดอร์ที่ “รอชำระเงิน”
    orders = (
        RentalOrder.objects
        .filter(
            rental_shop=store,
            status=RentalOrder.STATUS_WAITING_PAY,
        )
        .select_related('user', 'dress')
        .order_by('-pickup_date', '-created_at')
    )

    context = {
        "store": store,
        "page_title": "รอชำระเงิน",
        "orders": orders,
        "active_tab": "pending_payment",
    }
    return render(request, "dress/back_office_orders.html", context)

# ฟังก์ชันนี้คือ “หน้าหลังร้าน > แท็บออเดอร์ที่ชำระเงินแล้ว
@login_required(login_url='dress:login')
def back_office_orders_paid(request, store_id):
    """ชำระเงินสำเร็จ แต่ยังไม่ได้เริ่มเตรียมจัดส่ง"""
    store = get_object_or_404(Shop, id=store_id, owner=request.user)
    # ดึงออเดอร์ที่ “ชำระเงินแล้ว”
    orders = (
        RentalOrder.objects
        .filter(
            rental_shop=store,
            status=RentalOrder.STATUS_PAID,
        )
        .select_related('user', 'dress')
        .order_by('-pickup_date', '-created_at')
    )
    # ส่งไปให้ template แสดงผล
    context = {
        "store": store,
        "page_title": "ชำระเงินสำเร็จ",
        "orders": orders,
        "active_tab": "paid",
    }
    return render(request, "dress/back_office_orders.html", context)


# ฟังก์ชันนี้คือ “หน้าหลังร้าน > แท็บออเดอร์ที่ร้านกำลังเตรียมจัดส่ง”
@login_required(login_url='dress:login')
def back_office_orders_preparing(request, store_id):
    """กำลังเตรียมจัดส่ง"""
    store = get_object_or_404(Shop, id=store_id, owner=request.user)

    # ดึงออเดอร์ที่กำลังเตรียมจัดส่ง
    orders = (
        RentalOrder.objects
        .filter(
            rental_shop=store,
            status=RentalOrder.STATUS_PREPARING,
        )
        .select_related('user', 'dress')
        .order_by('-pickup_date', '-created_at')
    )

    context = {
        "store": store,
        "page_title": "กำลังเตรียมจัดส่ง",
        "orders": orders,
        "active_tab": "preparing",
    }
    return render(request, "dress/back_office_orders.html", context)

# ฟังก์ชันนี้คือ “หน้าหลังร้าน >แท็บออเดอร์ที่อยู่ระหว่างการเช่า”
@login_required(login_url='dress:login')
def back_office_orders_renting(request, store_id):
    """อยู่ระหว่างการเช่า (ลูกค้ารับชุดไปแล้ว ยังไม่ถึงกำหนดคืน)"""
    store = get_object_or_404(Shop, id=store_id, owner=request.user)

    orders = (
        RentalOrder.objects
        .filter(
            rental_shop=store,
            status=RentalOrder.STATUS_IN_RENTAL,   
        )
        .select_related('user', 'dress')
        .order_by('-pickup_date', '-created_at')
    )

    context = {
        "store": store,
        "page_title": "อยู่ระหว่างการเช่า",
        "orders": orders,
        "active_tab": "renting",
    }
    return render(request, "dress/back_office_orders.html", context)


# ฟังก์ชันนี้คือ “หน้าหลังร้าน > แท็บออเดอร์ที่รอคืนชุด”
@login_required(login_url='dress:login')
def back_office_orders_waiting_return(request, store_id):
    """รอคืนชุด (ถึงกำหนดคืนแล้ว / ใกล้ถึงกำหนด)"""
    store = get_object_or_404(Shop, id=store_id, owner=request.user)

    orders = (
        RentalOrder.objects
        .filter(
            rental_shop=store,
            status=RentalOrder.STATUS_WAITING_RETURN,
        )
        .select_related('user', 'dress')
        .order_by('-pickup_date', '-created_at')
    )

    context = {
        "store": store,
        "page_title": "รอคืนชุด",
        "orders": orders,
        # สำคัญ 2 ตัวนี้ เพื่อให้ template แสดงแท็บกลุ่ม "การเช่า"
        "active_group": "rent",
        "active_tab": "awaiting_return",
    }
    return render(request, "dress/back_office_orders.html", context)


# ฟังก์ชันนี้คือ “หน้าหลังร้าน > แท็บออเดอร์ที่คืนชุดแล้ว”
@login_required(login_url='dress:login')
def back_office_orders_returned(request, store_id):
    """คืนชุดแล้ว (เช่าสำเร็จจริง ๆ)"""
    store = get_object_or_404(Shop, id=store_id, owner=request.user)

    orders = (
        RentalOrder.objects
        .filter(
            rental_shop=store,
            status=RentalOrder.STATUS_RETURNED,
        )
        .select_related('user', 'dress')
        .order_by('-return_date', '-created_at')
    )

    context = {
        "store": store,
        "page_title": "คืนชุดแล้ว",
        "orders": orders,
        "active_tab": "returned",
    }
    return render(request, "dress/back_office_orders.html", context)

# ฟังก์ชันนี้คือ “หน้าหลังร้าน > แท็บออเดอร์ที่พบปัญหาชุดชำรุด”
@login_required(login_url='dress:login')
def back_office_orders_damaged(request, store_id):
    """พบปัญหาชุดชำรุด / มีค่าปรับ"""
    store = get_object_or_404(Shop, id=store_id, owner=request.user)

    orders = (
        RentalOrder.objects
        .filter(
            rental_shop=store,
            status=RentalOrder.STATUS_DAMAGED,
        )
        .select_related('user', 'dress')
        .order_by('-return_date', '-created_at')
    )

    context = {
        "store": store,
        "page_title": "พบปัญหาชุดชำรุด",
        "orders": orders,
        "active_tab": "damaged",
    }
    return render(request, "dress/back_office_orders.html", context)

# ฟังก์ชันนี้คือ “หน้าหลังร้าน > แท็บออเดอร์ที่กำลังจัดส่ง”
@login_required(login_url='dress:login')
def back_office_orders_shipping(request, store_id):
    store = get_object_or_404(Shop, id=store_id, owner=request.user)

    # สถานะการจัดส่ง: เตรียมจัดส่ง + จัดส่งเรียบร้อย
    orders = (
        RentalOrder.objects
        .filter(
            rental_shop=store,
            status__in=[
                RentalOrder.STATUS_PREPARING,
                RentalOrder.STATUS_SHIPPING,
            ],
        )
        .select_related('user', 'dress')
        .order_by('-pickup_date', '-created_at')
    )

    context = {
        "store": store,
        "page_title": "สถานะการจัดส่ง",
        "orders": orders,
        "active_tab": "shipping",
    }
    return render(request, "dress/back_office_orders.html", context)

# ฟังก์ชันนี้คือ “หน้าหลังร้าน > แท็บออเดอร์ที่ถูกยกเลิก”
@login_required(login_url='dress:login')
def back_office_orders_cancelled(request, store_id):
    store = get_object_or_404(Shop, id=store_id, owner=request.user)

    orders = (
        RentalOrder.objects
        .filter(
            rental_shop=store,
            status__in=[
                RentalOrder.STATUS_CANCELLED,  # สถานะใหม่
                "cancelled",                   # ข้อมูลเก่า
            ],
        )
        .select_related('user', 'dress')
        .order_by('-pickup_date', '-created_at')
    )

    context = {
        "store": store,
        "page_title": "ที่ถูกยกเลิก",
        "orders": orders,
        "active_tab": "cancelled",
    }
    return render(request, "dress/back_office_orders.html", context)

# ฟังก์ชันนี้คือ “หน้าหลังร้าน > แท็บออเดอร์ที่เช่าสำเร็จ”
@login_required(login_url='dress:login')
def back_office_orders_completed(request, store_id):
    store = get_object_or_404(Shop, id=store_id, owner=request.user)

    # เช่าสำเร็จ: คืนชุดแล้ว (และเผื่อ status เดิม completed)
    orders = (
        RentalOrder.objects
        .filter(
            rental_shop=store,
            status__in=[
                RentalOrder.STATUS_RETURNED,  # คืนชุดแล้ว
                "completed",                  # สถานะเดิม
            ],
        )
        .select_related('user', 'dress')
        .order_by('-return_date', '-created_at')
    )

    context = {
        "store": store,
        "page_title": "เช่าสำเร็จ",
        "orders": orders,
        "active_tab": "completed",
    }
    return render(request, "dress/back_office_orders.html", context)

# ฟังก์ชันนี้คือ “หน้าควบคุมหลังร้าน > รีวิวจากลูกค้า”
@login_required(login_url='dress:login')
def back_office_reviews(request, store_id):
    # ร้านต้องเป็นของ user คนนี้เท่านั้น
    store = get_object_or_404(Shop, id=store_id, owner=request.user)

    # ถ้ามีการส่งคำตอบเข้ามา (กดปุ่มบันทึก)
    if request.method == "POST":
        review_id = request.POST.get("review_id")
        # ดึงค่าจาก name="reply" ในฟอร์ม
        reply_text = (request.POST.get("reply") or "").strip()

        if review_id:
            # ดึงรีวิวที่เป็นของ "ชุดในร้านนี้" เท่านั้น
            review = get_object_or_404(
                Review,
                id=review_id,
                dress__shop=store,   # ใช้ field shop ให้ตรงกับที่ใช้ที่อื่น
            )

            if reply_text:
                review.shop_reply = reply_text
                review.replied_at = timezone.now()
            else:
                # ถ้าอยากให้ลบคำตอบเมื่อเคลียร์กล่อง ก็เคลียร์ได้
                review.shop_reply = None
                review.replied_at = None

            review.save()
            messages.success(request, "บันทึกคำตอบจากร้านเรียบร้อยแล้ว")

        # ป้องกันการ POST ซ้ำเวลา refresh
        return redirect("dress:back_office_reviews", store_id=store.id)

    # โหลดรีวิวทั้งหมดของร้านนี้
    reviews = (
        Review.objects
        .filter(dress__shop=store)   # ใช้ shop ให้ตรงกับส่วนอื่นของระบบ
        .select_related("dress", "user")
        .order_by("-created_at")
    )

    context = {
        "store": store,
        "reviews": reviews,
    }
    return render(request, "dress/back_office_reviews.html", context)


# การเงินหลังร้าน
COMMISSION_RATE = Decimal("0.10")  # ค่าคอมแพลตฟอร์ม 10% (ปรับได้เอง)

# ฟังก์ชันนี้คือ “หน้าควบคุมหลังร้าน > การเงิน”
@login_required(login_url='dress:login')
def back_office_finance(request, store_id):
    # ร้านต้องเป็นของ user คนนี้
    store = get_object_or_404(Shop, id=store_id, owner=request.user)
    today = timezone.localdate()

    # ออเดอร์ที่ "สร้างรายได้" ของร้านนี้
    # นับทุกสถานะที่ถือว่าจ่ายเงินแล้ว ยกเว้น cancelled
    income_orders_qs = RentalOrder.objects.filter(
        rental_shop=store,
        status__in=[
            RentalOrder.STATUS_PAID,
            RentalOrder.STATUS_PREPARING,
            RentalOrder.STATUS_SHIPPING,
            RentalOrder.STATUS_IN_RENTAL,
            RentalOrder.STATUS_WAITING_RETURN,
            RentalOrder.STATUS_RETURNED,
            RentalOrder.STATUS_DAMAGED,
            "completed",  # กันข้อมูลเก่า
        ],
    )

    # helper คำนวณยอดรวมสุทธิ (หลังหักค่าคอม)
    def net_total(qs):
        gross = qs.aggregate(s=Sum("total_price"))["s"] or Decimal("0.00")
        net = gross * (Decimal("1.00") - COMMISSION_RATE)
        return net.quantize(Decimal("0.01"))

    # 1) รายได้ทั้งหมดตั้งแต่เปิดร้าน
    total_income = net_total(income_orders_qs)

    # 2) รายได้เดือนนี้ (ใช้ pickup_date เป็นเกณฑ์ ถ้าต้องการใช้ field อื่นปรับตรงนี้ได้)
    month_orders = income_orders_qs.filter(
        pickup_date__year=today.year,
        pickup_date__month=today.month,
    )
    income_this_month = net_total(month_orders)

    # 3) รายได้วันนี้
    today_orders = income_orders_qs.filter(pickup_date=today)
    income_today = net_total(today_orders)

    # 4) ประวัติการถอนเงินทั้งหมดของร้านนี้
    withdrawal_history = WithdrawalRequest.objects.filter(
        store=store
    ).order_by("-created_at")

    # ยอดที่ถอนออกไปแล้ว (ถือว่า status = paid หรือ approved คือหักออกจากกระเป๋าแล้ว)
    withdrawn_sum = withdrawal_history.filter(
        status__in=["paid", "approved"]
    ).aggregate(s=Sum("amount"))["s"] or Decimal("0.00")

    # 5) กระเป๋าเงินคงเหลือ = รายได้สุทธิทั้งหมด - ยอดที่ถอนแล้ว
    wallet_balance = total_income - withdrawn_sum
    if wallet_balance < Decimal("0.00"):
        wallet_balance = Decimal("0.00")

    # 6) ถ้ากดปุ่ม "ขอถอนเงิน"
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "withdraw_all":
            if wallet_balance > Decimal("0.00"):
                WithdrawalRequest.objects.create(
                    store=store,
                    amount=wallet_balance,
                    status="pending",
                )
                messages.success(
                    request,
                    f"ส่งคำขอถอนเงินจำนวน {wallet_balance} บาท เรียบร้อยแล้ว",
                )
            else:
                messages.error(request, "ยังไม่มียอดเงินคงเหลือให้ถอน")
            return redirect("dress:back_office_finance", store_id=store.id)

    # 7) ประวัติออเดอร์ที่สร้างรายได้ (แสดงล่าสุดไม่เกิน 10 รายการ)
    income_orders = income_orders_qs.order_by("-pickup_date", "-id")[:10]

    context = {
        "store": store,
        "total_income": total_income,
        "income_this_month": income_this_month,
        "income_today": income_today,
        "wallet_balance": wallet_balance,
        "income_orders": income_orders,
        "withdrawal_history": withdrawal_history,
    }
    return render(request, "dress/back_office_finance.html", context)

# ฟังก์ชันนี้คือ “หน้าควบคุมหลังร้าน > สถิติร้าน”
@login_required(login_url='dress:login')
def back_office_stats(request, store_id):
    store = get_object_or_404(Shop, pk=store_id)

    # ออเดอร์ทั้งหมดของร้าน
    orders = RentalOrder.objects.filter(rental_shop=store)

    total_orders = orders.count()

    # นับ "เช่าสำเร็จ" = คืนชุดแล้ว หรือสถานะเดิม completed
    completed_orders = orders.filter(
        status__in=[
            RentalOrder.STATUS_RETURNED,
            "completed",
        ]
    ).count()

    cancelled_orders = orders.filter(
        status__in=[
            RentalOrder.STATUS_CANCELLED,
            "cancelled",
        ]
    ).count()

    # รายได้รวมจาก StoreTransaction
    transactions = StoreTransaction.objects.filter(store=store)
    total_revenue = (
        transactions.aggregate(total=Sum("net_amount"))["total"] or 0
    )

    # รีวิว
    reviews = Review.objects.filter(dress__shop=store)
    avg_rating = reviews.aggregate(avg=Avg("rating"))["avg"] or 0
    reviews_count = reviews.count()

    # ชุดยอดนิยม: นับออเดอร์ที่มีสถานะจบการเช่าจริง ๆ
    top_dresses = (
        Dress.objects.filter(shop=store)
        .annotate(
            success_count=Count(
                "rental_orders",
                filter=Q(
                    rental_orders__status__in=[
                        RentalOrder.STATUS_RETURNED,
                        RentalOrder.STATUS_PAID,
                        "completed",
                    ]
                ),
            )
        )
        .filter(success_count__gt=0)
        .order_by("-success_count")[:5]
    )

    # ออเดอร์ล่าสุด
    recent_orders = orders.order_by("-created_at")[:10]

    # --------- ข้อมูลสำหรับกราฟรายได้ 30 วันที่ผ่านมา ---------
    today = timezone.now().date()
    start_date = today - timedelta(days=30)

    revenue_qs = (
        transactions
        .filter(created_at__date__gte=start_date)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Sum("net_amount"))
        .order_by("day")
    )

    revenue_labels = [item["day"].strftime("%d/%m") for item in revenue_qs]
    revenue_data = [float(item["total"] or 0) for item in revenue_qs]

    # --------- ข้อมูลสำหรับกราฟออเดอร์ตามสถานะ ---------
    status_qs = (
        orders.values("status")
        .annotate(count=Count("id"))
        .order_by("status")
    )

    status_labels = [item["status"] for item in status_qs]
    status_data = [item["count"] for item in status_qs]

    context = {
        "store": store,
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "cancelled_orders": cancelled_orders,
        "total_revenue": total_revenue,
        "avg_rating": avg_rating,
        "reviews_count": reviews_count,
        "top_dresses": top_dresses,
        "recent_orders": recent_orders,

        # ส่งไปเป็น JSON string เพื่อให้ JS ใช้ตรงๆ
        "revenue_labels": json.dumps(revenue_labels, ensure_ascii=False),
        "revenue_data": json.dumps(revenue_data),
        "status_labels": json.dumps(status_labels, ensure_ascii=False),
        "status_data": json.dumps(status_data),
    }

    return render(request, "dress/back_office_stats.html", context)



# =============================================================================
# ร้านค้าสาธารณะลูกค้าเข้าชมได้ (public_store.html)
#==============================================================================
def public_store(request, store_id):
    store = get_object_or_404(Shop, id=store_id)
    selected_category = request.GET.get('category', 'ทั้งหมด')

    categories = Category.objects.filter(dress__shop=store).distinct()

    if selected_category != "ทั้งหมด":
        dresses = Dress.objects.filter(shop=store, categories__name=selected_category, is_available=True)
    else:
        dresses = Dress.objects.filter(shop=store, is_available=True)

    context = {
        "store": store,
        "categories": categories,
        "dresses": dresses,
        "selected_category": selected_category,
        "total_products": dresses.count(),
        "user_role": getattr(request.user, "role", "guest"),
    }
    return render(request, "dress/public_store.html", context)





# ฟังก์ชันนี้คือ “หน้าร้านของเจ้าของร้าน” (store_store.html)
@login_required(login_url="dress:login")
def store_store(request, store_id: int):
    """
    หน้าร้านมุมมองเจ้าของร้าน (แยกจาก public_store)
    URL: /my-store/<store_id>/store/
    """
    store = get_object_or_404(Shop, id=store_id)

    # กันคนอื่นแอบเข้าร้านคนอื่น (ปรับ field ให้ตรงโปรเจกต์คุณ)
    # ถ้า Shop ของคุณใช้ field owner หรือ user ให้แก้ตรงนี้
    owner = getattr(store, "owner", None) or getattr(store, "user", None)
    if owner and owner != request.user:
        return redirect("dress:public_store", store_id=store.id)

    selected_category = request.GET.get("category", "ทั้งหมด")
    status_filter = request.GET.get("status", "all")  # all | available | unavailable
    q = (request.GET.get("q") or "").strip()

    categories = Category.objects.filter(dress__shop=store).distinct()

    dresses = Dress.objects.filter(shop=store)

    if selected_category != "ทั้งหมด":
        dresses = dresses.filter(categories__name=selected_category)

    if status_filter == "available":
        dresses = dresses.filter(is_available=True)
    elif status_filter == "unavailable":
        dresses = dresses.filter(is_available=False)

    if q:
        dresses = dresses.filter(Q(name__icontains=q))

    # Summary
    total_all = Dress.objects.filter(shop=store).count()
    available_count = Dress.objects.filter(shop=store, is_available=True).count()
    unavailable_count = Dress.objects.filter(shop=store, is_available=False).count()

    context = {
        "store": store,
        "categories": categories,
        "dresses": dresses,
        "selected_category": selected_category,
        "status_filter": status_filter,
        "q": q,

        "total_all": total_all,
        "available_count": available_count,
        "unavailable_count": unavailable_count,
    }
    return render(request, "dress/store_store.html", context)


@login_required(login_url="dress:login")
@require_POST
def toggle_dress_availability(request, store_id: int, dress_id: int):
    """
    เปิด/ปิดให้เช่า (มุมมองร้าน)
    """
    store = get_object_or_404(Shop, id=store_id)

    owner = getattr(store, "owner", None) or getattr(store, "user", None)
    if owner and owner != request.user:
        return redirect("dress:public_store", store_id=store.id)

    dress = get_object_or_404(Dress, id=dress_id, shop=store)
    dress.is_available = not bool(dress.is_available)
    dress.save(update_fields=["is_available"])

    # กลับหน้าร้านแบบคง query เดิมไว้
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or ""
    if next_url:
        return redirect(next_url)

    return redirect("dress:store_store", store_id=store.id)





@login_required(login_url="dress:login")
def store_page(request, store_id: int):
    store = get_object_or_404(Shop, id=store_id)

    # เช็คเจ้าของร้าน
    owner = getattr(store, "owner", None) or getattr(store, "user", None)
    if owner and owner != request.user:
        return redirect("dress:public_store", store_id=store.id)

    selected_category = request.GET.get("category", "ทั้งหมด")
    status_filter = request.GET.get("status", "all")  # all | available | unavailable
    q = request.GET.get("q", "").strip()

    # หมวดหมู่
    categories = Category.objects.filter(dress__shop=store).distinct()

    # base queryset (ของร้านทั้งหมด)
    base_qs = Dress.objects.filter(shop=store)

    # สรุปจำนวน (อิงจากของร้านทั้งหมด ไม่ใช่หลังกรอง)
    total_all = base_qs.count()
    available_count = base_qs.filter(is_available=True).count()
    unavailable_count = base_qs.filter(is_available=False).count()

    # ชุดที่แสดงจริง (เริ่มจาก base แล้วค่อยกรอง)
    dresses = base_qs

    # กรองตามหมวด
    if selected_category != "ทั้งหมด":
        dresses = dresses.filter(categories__name=selected_category)

    # กรองตามสถานะ
    if status_filter == "available":
        dresses = dresses.filter(is_available=True)
    elif status_filter == "unavailable":
        dresses = dresses.filter(is_available=False)

    # ค้นหา (ถ้ามี field อื่นเพิ่มเองได้)
    if q:
        dresses = dresses.filter(name__icontains=q)

    context = {
        "store": store,
        "categories": categories,
        "dresses": dresses,
        "selected_category": selected_category,
        "status_filter": status_filter,   # สำคัญ: ให้ตรงกับ template
        "q": q,

        "total_all": total_all,
        "available_count": available_count,
        "unavailable_count": unavailable_count,
    }
    return render(request, "dress/store_store.html", context)




# ---------- API: เทมเพลตราคาเช่า/ค่าส่ง (สร้างใหม่) ----------
@login_required(login_url="dress:login")
@require_POST
def api_create_price_template(request, store_id: int):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "รูปแบบข้อมูลไม่ถูกต้อง"}, status=400)

    name = (payload.get("name") or "").strip()
    max_days = payload.get("max_days")
    items = payload.get("items") or []

    store = get_object_or_404(Shop, id=store_id)
    if not _assert_store_owner(store, request.user):
        return JsonResponse({"ok": False, "error": "ไม่มีสิทธิ์จัดการร้านนี้"}, status=403)

    if not name:
        return JsonResponse({"ok": False, "error": "กรุณากรอกชื่อเทมเพลต"}, status=400)
    if not isinstance(max_days, int) or max_days < 1:
        return JsonResponse({"ok": False, "error": "จำนวนวันสูงสุดต้องเป็นจำนวนเต็ม ≥ 1"}, status=400)
    if not items:
        return JsonResponse({"ok": False, "error": "กรุณาใส่รายการราคาอย่างน้อย 1 แถว"}, status=400)

    if PriceTemplate.objects.filter(store=store, name=name).exists():
        return JsonResponse({"ok": False, "error": "มีชื่อเทมเพลตนี้ในร้านแล้ว กรุณาใช้ชื่ออื่น"}, status=400)

    normalized = []
    seen = set()
    for row in items:
        day = int(row.get("day_count") or 0)
        price_raw = row.get("total_price")
        try:
            price = Decimal(str(price_raw))
        except Exception:
            return JsonResponse({"ok": False, "error": f"ราคาของ {day} วัน ไม่ถูกต้อง"}, status=400)

        if day < 1 or day > max_days:
            return JsonResponse({"ok": False, "error": f"จำนวนวัน {day} เกิน {max_days}"}, status=400)
        if day in seen:
            return JsonResponse({"ok": False, "error": f"วัน {day} ซ้ำกัน"}, status=400)
        if price < 0:
            return JsonResponse({"ok": False, "error": f"ราคา {day} วัน ต้องไม่ติดลบ"}, status=400)
        seen.add(day)
        normalized.append((day, price))

    try:
        with transaction.atomic():
            tpl = PriceTemplate.objects.create(store=store, name=name, max_days=max_days)
            PriceTemplateItem.objects.bulk_create([
                PriceTemplateItem(template=tpl, day_count=d, total_price=p) for d, p in normalized
            ])
    except IntegrityError:
        return JsonResponse({"ok": False, "error": "สร้างไม่สำเร็จ: ชื่อซ้ำหรือข้อมูลขัดแย้ง"}, status=400)

    return JsonResponse({"ok": True, "template": {
        "id": tpl.id, "name": tpl.name, "max_days": tpl.max_days
    }})

#บันทึกกฎค่าส่งของร้าน
@login_required(login_url="dress:login")
@require_POST
def api_save_shipping_rule(request, store_id: int):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "รูปแบบข้อมูลไม่ถูกต้อง"}, status=400)

    clamp_to_max = bool(payload.get("clamp_to_max", True))
    brackets = payload.get("brackets") or []

    store = get_object_or_404(Shop, id=store_id)
    if not _assert_store_owner(store, request.user):
        return JsonResponse({"ok": False, "error": "ไม่มีสิทธิ์จัดการร้านนี้"}, status=403)

    if not brackets:
        return JsonResponse({"ok": False, "error": "กรุณาเพิ่มช่วงค่าส่งอย่างน้อย 1 ช่วง"}, status=400)

    cleaned = []
    for b in brackets:
        try:
            mn = int(b.get("min_qty") or 0)
            mx = int(b.get("max_qty") or 0)
            fee = Decimal(str(b.get("fee")))
        except Exception:
            return JsonResponse({"ok": False, "error": "ข้อมูลช่วงค่าส่งไม่ถูกต้อง"}, status=400)

        if mn < 1 or mx < mn:
            return JsonResponse({"ok": False, "error": f"ช่วง {mn}-{mx} ไม่ถูกต้อง"}, status=400)
        if fee < 0:
            return JsonResponse({"ok": False, "error": f"ค่าส่งต้องไม่ติดลบ (ช่วง {mn}-{mx})"}, status=400)

        cleaned.append((mn, mx, fee))

    with transaction.atomic():
        rule, _ = ShippingRule.objects.get_or_create(store=store, defaults={"clamp_to_max": clamp_to_max})
        rule.clamp_to_max = clamp_to_max
        rule.save()

        rule.brackets.all().delete()
        ShippingBracket.objects.bulk_create([
            ShippingBracket(rule=rule, min_qty=mn, max_qty=mx, fee=fee) for mn, mx, fee in cleaned
        ])

    return JsonResponse({"ok": True})


# ==============================================================================================
# Helper สำหรับเช็คเอาต์/ชำระเงิน  คำนวณวันที่ และค่าส่งตามจำนวนสินค้าที่เช่า
# ==============================================================================================
def _parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

# คำนวณจำนวนวันแบบรวมวันแรกและวันสุดท้าย
def _days_inclusive(a, b):
    if not a or not b:
        return 0
    return (b - a).days + 1

# คำนวณค่าส่งตามช่วงที่กำหนด
def _calc_shipping_from_tiers(tiers, qty):
    """tiers = [{'min_qty':1,'max_qty':2,'fee':50}, ...]"""
    if not tiers or qty < 1:
        return 0.0
    fee = 0.0
    for b in tiers:
        mn, mx, f = int(b["min_qty"]), int(b["max_qty"]), float(b["fee"])
        if mn <= qty <= mx:
            fee = f
            break
        if qty > mx:
            fee = f  # clamp ไปช่วงบนสุด
    return fee


# ==============================================================================================
# เช็คเอาต์   หน้าสรุปเช็คเอาต์การเช่าชุด” ก่อนจะไปหน้าชำระเงิน โดยคำนวณค่าเช่าตามจำนวนวัน + มัดจำ + ค่าส่ง
# ==============================================================================================
@login_required(login_url="dress:login")
def rent_checkout(request, dress_id):
    dress = get_object_or_404(Dress, pk=dress_id)

    # ---------- เช็คว่าชุดนี้ปิดการเช่าหรือไม่ ----------
    # ถ้าไม่มี field is_available ให้เปลี่ยนชื่อฟิลด์ตรงนี้ให้ตรงกับโมเดลของคุณ
    if not getattr(dress, "is_available", True):
        messages.error(request, "ชุดนี้ถูกปิดการเช่าชั่วคราว ไม่สามารถทำรายการเช่าได้ในขณะนี้")
        return redirect("dress:dress_detail", dress_id=dress.id)
    # ---------------------------------------------------


    start_s = (request.POST.get("start_date") or request.GET.get("start_date")
               or request.GET.get("start") or "").strip()
    end_s   = (request.POST.get("end_date") or request.GET.get("end_date")
               or request.GET.get("end") or "").strip()
    days_s  = (request.POST.get("days") or request.GET.get("days") or "").strip()

    start_date = _parse_date(start_s)
    end_date   = _parse_date(end_s)
    total_days = int(days_s) if days_s.isdigit() else _days_inclusive(start_date, end_date)

    pack_prices = []
    if getattr(dress, "price_template", None):
        for it in dress.price_template.items.order_by("day_count"):
            pack_prices.append({"days": it.day_count, "price": float(it.total_price)})
    else:
        daily = float(getattr(dress, "daily_price", 0) or 0)
        if daily > 0:
            for d in range(1, 9):
                pack_prices.append({"days": d, "price": daily * d})

    deposit = float(getattr(dress, "deposit", 0) or 0)
    rental_fee = 0.0
    if total_days > 0:
        match = next((p for p in pack_prices if int(p["days"]) == total_days), None)
        rental_fee = float(match["price"]) if match else float(getattr(dress, "daily_price", 0) or 0) * total_days

    shipping_tiers = []
    shipping_clamp_note = None
    rule = getattr(dress.shop, "shipping_rule", None)
    if rule and hasattr(rule, "brackets"):
        for b in rule.brackets.all().order_by("min_qty"):
            shipping_tiers.append({"min_qty": b.min_qty, "max_qty": b.max_qty, "fee": float(b.fee)})
        if getattr(rule, "clamp_to_max", False) and rule.brackets.exists():
            top = rule.brackets.order_by("-max_qty").first()
            shipping_clamp_note = f"มากกว่า {top.max_qty} ชุด คิดค่าส่ง {float(top.fee):.2f} บาท"
    else:
        shipping_tiers = [
            {"min_qty": 1, "max_qty": 2, "fee": 50},
            {"min_qty": 3, "max_qty": 5, "fee": 65},
        ]
        shipping_clamp_note = "มากกว่า 5 ชุด คิดค่าส่ง 65.00 บาท"

    preview_shipping = _calc_shipping_from_tiers(shipping_tiers, 1)

    if request.method == "POST":
        receive_method = (request.POST.get("receive_method") or "pickup").strip()
        address        = (request.POST.get("address") or "").strip()
        pickup_slot    = (request.POST.get("pickup_slot") or "").strip()
        return_slot    = (request.POST.get("return_slot") or "").strip()
        delivery_slot  = (request.POST.get("delivery_slot") or "").strip()
        renter_name    = (request.POST.get("renter_name") or "").strip()
        renter_phone   = (request.POST.get("renter_phone") or "").strip()

        shipping_fee = _calc_shipping_from_tiers(shipping_tiers, 1) if receive_method == "delivery" else 0.0
        amount_baht  = float(rental_fee) + float(deposit) + float(shipping_fee)

        request.session["checkout"] = {
            "dress_id": dress.id,
            "start_date": start_date.strftime("%Y-%m-%d") if start_date else "",
            "end_date":   end_date.strftime("%Y-%m-%d")   if end_date else "",
            "days": total_days,

            "receive_method": receive_method,
            "address": address,
            "pickup_slot": pickup_slot,
            "return_slot": return_slot,
            "delivery_slot": delivery_slot,

            "renter_name": renter_name,
            "renter_phone": renter_phone,

            "rental_fee": f"{rental_fee:.2f}",
            "deposit":    f"{deposit:.2f}",
            "shipping":   f"{shipping_fee:.2f}",
            "amount_baht": f"{amount_baht:.2f}",
        }
        request.session.modified = True
        return redirect("dress:rent_payment", dress_id=dress.id)

    ctx = {
        "dress": dress,
        "start_date": start_date,
        "end_date": end_date,
        "total_days": total_days,
        "rental_fee": rental_fee,
        "deposit": deposit,
        "pack_prices": pack_prices,
        "shipping_tiers": shipping_tiers,
        "shipping_clamp_note": shipping_clamp_note,
        "preview_shipping_fee": preview_shipping,
    }
    return render(request, "dress/rent_checkout.html", ctx)


# คำนวณราคาเช่าสำหรับ 1 ชุด
def _quote_for(dress, start_date, end_date, method="pickup"):
    days = _days_inclusive(start_date, end_date)

    pack_prices = []
    if getattr(dress, "price_template", None):
        for it in dress.price_template.items.order_by("day_count"):
            pack_prices.append({"days": int(it.day_count), "price": float(it.total_price)})
    else:
        daily = float(getattr(dress, "daily_price", 0) or 0)
        if daily > 0:
            for d in range(1, 9):
                pack_prices.append({"days": d, "price": daily * d})

    rental_fee = 0.0
    if days > 0:
        match = next((p for p in pack_prices if p["days"] == days), None)
        rental_fee = float(match["price"]) if match else float(getattr(dress, "daily_price", 0) or 0) * days

    deposit = float(getattr(dress, "deposit", 0) or 0)

    shipping = 0.0
    if (method or "").strip() == "delivery":
        rule = getattr(dress.shop, "shipping_rule", None)
        tiers = []
        if rule and hasattr(rule, "brackets"):
            for b in rule.brackets.all().order_by("min_qty"):
                tiers.append({"min_qty": b.min_qty, "max_qty": b.max_qty, "fee": float(b.fee)})
        else:
            tiers = [
                {"min_qty": 1, "max_qty": 2, "fee": 50},
                {"min_qty": 3, "max_qty": 5, "fee": 65},
            ]
        shipping = _calc_shipping_from_tiers(tiers, 1)

    amount = rental_fee + deposit + shipping
    return {
        "days": days,
        "rental_fee": round(rental_fee, 2),
        "deposit": round(deposit, 2),
        "shipping": round(shipping, 2),
        "amount_baht": round(amount, 2),
    }


# =========================
# ชำระเงิน
# =========================
@login_required(login_url="dress:login")
def rent_payment(request, dress_id):
    dress = get_object_or_404(Dress, pk=dress_id)

    def _norm_method(val: str) -> str:
        return "delivery" if (val or "").strip() == "delivery" else "pickup"

    def _norm_pay(val: str) -> str:
        return "pay_at_store" if (val or "").strip() == "pay_at_store" else "promptpay"

    def _to_money(x) -> float:
        try:
            return float(Decimal(str(x)))
        except Exception:
            return 0.0

    sess = request.session.get("checkout") or {}
    pay_method_qs = _norm_pay(request.GET.get("pay_method") or "")

    if sess and int(sess.get("dress_id", 0)) == dress.id:
        start_date    = _parse_date(sess.get("start_date") or "")
        end_date      = _parse_date(sess.get("end_date") or "")
        method        = _norm_method(sess.get("receive_method") or "pickup")

        rental_fee    = _to_money(sess.get("rental_fee"))
        deposit       = _to_money(sess.get("deposit"))
        shipping      = _to_money(sess.get("shipping"))
        amount        = _to_money(sess.get("amount_baht"))
        days          = int(sess.get("days") or 0)

        address       = sess.get("address")
        pickup_slot   = sess.get("pickup_slot")
        return_slot   = sess.get("return_slot")
        delivery_slot = sess.get("delivery_slot")

        pay_method    = pay_method_qs or _norm_pay(sess.get("pay_method") or "promptpay")
    else:
        start_date = _parse_date((request.GET.get("start_date") or request.GET.get("start") or "").strip())
        end_date   = _parse_date((request.GET.get("end_date")   or request.GET.get("end")   or "").strip())
        method     = _norm_method(request.GET.get("method") or "pickup")

        q = _quote_for(dress, start_date, end_date, method)
        days, rental_fee, deposit, shipping, amount = (
            int(q["days"]),
            _to_money(q["rental_fee"]),
            _to_money(q["deposit"]),
            _to_money(q["shipping"]),
            _to_money(q["amount_baht"]),
        )

        address       = request.GET.get("address")
        pickup_slot   = request.GET.get("pickup_slot")
        return_slot   = request.GET.get("return_slot")
        delivery_slot = request.GET.get("delivery_slot")

        pay_method    = pay_method_qs or "promptpay"

    if method == "pickup" and pay_method == "pay_at_store":
        shipping = 0.0
        amount   = float(rental_fee) + float(deposit) + float(shipping)

    ctx = {
        "dress": dress,
        "start_date": start_date,
        "end_date": end_date,
        "days": days,
        "method": method,
        "pay_method": pay_method,
        "rental_fee": rental_fee,
        "deposit": deposit,
        "shipping": shipping,
        "amount_baht": amount,
        "address": address,
        "pickup_slot": pickup_slot,
        "return_slot": return_slot,
        "delivery_slot": delivery_slot,
    }
    return render(request, "dress/rent_payment.html", ctx)


# ---------------------------------------------------------------------
# 1) สร้าง Omise PromptPay Charge (SANDBOX) + fallback
# ---------------------------------------------------------------------
@require_POST
@csrf_exempt  # ถ้าเปิด CSRF ที่ frontend ต้องส่ง csrftoken มากับ fetch แล้วเอาบรรทัดนี้ออก
def create_promptpay_charge(request, dress_id):
    amount_str = request.POST.get("amount")
    method = (request.POST.get("method") or "").strip()

    if not amount_str:
        return HttpResponseBadRequest("Missing amount")

    try:
        amount_baht = float(amount_str)
        if amount_baht <= 0:
            return HttpResponseBadRequest("Invalid amount")
    except ValueError:
        return HttpResponseBadRequest("Invalid amount")

    # ตั้งค่า key ก่อนเรียก Omise
    omise.api_public = settings.OMISE_PUBLIC_KEY or ""
    omise.api_secret = settings.OMISE_SECRET_KEY or ""
    currency = settings.OMISE_CURRENCY or "thb"

    if not (omise.api_public and omise.api_secret):
        data = {
            "order_no": f"ORD-{dress_id}-{int(time.time())}",
            "status": "pending",
            "qr_image": FALLBACK_QR_URL,
            "charge_id": "chrg_mock_" + str(int(time.time())),
            "expires_at": int(time.time()) + 10 * 60,
            "method": method,
            "amount": int(round(amount_baht)),
        }
        return JsonResponse(data)

    try:
        amount_satang = int(round(amount_baht * 100))

        source = omise.Source.create(
            type="promptpay",
            amount=amount_satang,
            currency=currency,
        )

        charge = omise.Charge.create(
            amount=amount_satang,
            currency=currency,
            source=source.id,
            metadata={
                "dress_id": dress_id,
                "user_id": request.user.id if request.user.is_authenticated else None,
                "receive_method": method,
            },
        )

        try:
            qr_url = charge.source.scannable_code.image.download_uri
        except Exception:
            qr_url = None

        try:
            exp_unix = charge.source.references.expires_at
        except Exception:
            exp_unix = None

        data = {
            "order_no": charge.id,
            "status": charge.status or "pending",
            "qr_image": qr_url or FALLBACK_QR_URL,
            "charge_id": charge.id,
            "expires_at": exp_unix or (int(time.time()) + 10 * 60),
            "method": method,
            "amount": int(round(amount_baht)),
        }
        return JsonResponse(data)

    except omise.errors.BaseError as e:
        data = {
            "order_no": f"ORD-{dress_id}-{int(time.time())}",
            "status": "pending",
            "qr_image": FALLBACK_QR_URL,
            "charge_id": "chrg_fallback_" + str(int(time.time())),
            "expires_at": int(time.time()) + 10 * 60,
            "method": method,
            "amount": int(round(amount_baht)),
            "note": f"omise_error:{str(e)}",
        }
        return JsonResponse(data, status=200)
    except Exception as e:
        return JsonResponse({"error": "unexpected: " + str(e)}, status=500)


# ---------------------------------------------------------------------
# 2) หน้าสำเร็จ (รองรับ charge_id จาก Sandbox) + สร้าง RentalOrder
# ---------------------------------------------------------------------
@login_required(login_url="dress:login")
def rent_success(request, dress_id):
    dress = get_object_or_404(Dress, pk=dress_id)

    # ดึงข้อมูลจาก session หรือ query string
    sess = request.session.get("checkout") or {}
    if sess and int(sess.get("dress_id", 0)) == dress.id:
        start_date = _parse_date(sess.get("start_date") or "")
        end_date   = _parse_date(sess.get("end_date") or "")
        days       = int(sess.get("days") or 0)
        method     = (sess.get("receive_method") or request.GET.get("method") or "pickup").strip()
        rental_fee = float(sess.get("rental_fee") or 0)
        deposit    = float(sess.get("deposit") or 0)
        shipping   = float(sess.get("shipping") or 0)
        amount     = float(sess.get("amount_baht") or 0)
        pickup_slot = sess.get("pickup_slot")
        return_slot = sess.get("return_slot")
        order_ref   = request.GET.get("order_ref") or f"ORD-{dress_id}-{timezone.now().strftime('%m-%d')}"
    else:
        start_date = _parse_date(request.GET.get("start_date") or request.GET.get("start") or "")
        end_date   = _parse_date(request.GET.get("end_date")   or request.GET.get("end")   or "")
        days       = int(request.GET.get("days") or 0)
        method     = (request.GET.get("method") or "pickup").strip()
        rental_fee = float(request.GET.get("rental_fee") or 0)
        deposit    = float(request.GET.get("deposit") or 0)
        shipping   = float(request.GET.get("shipping") or 0)
        amount     = float(request.GET.get("amount_baht") or 0)
        pickup_slot = request.GET.get("pickup_slot")
        return_slot = request.GET.get("return_slot")
        order_ref   = request.GET.get("order_ref") or f"ORD-{dress_id}-{timezone.now().strftime('%m-%d')}"

    charge_id  = request.GET.get("charge_id")
    pay_method = request.GET.get("pay_method") or ("promptpay" if charge_id else "pay_at_store")

    # เคลียร์ session checkout ทิ้ง
    if "checkout" in request.session:
        try:
            del request.session["checkout"]
            request.session.modified = True
        except Exception:
            pass

    # -----------------------------
    # สร้าง RentalOrder (ถ้ายังไม่มี)
    # -----------------------------
    order = None
    if start_date and end_date:
        # กันเคส refresh หน้า success ด้วย charge_id เดิม
        if charge_id:
            order = RentalOrder.objects.filter(omise_charge_id=charge_id).first()

        if order is None:
            total_price = Decimal(str(amount or (rental_fee + deposit + shipping)))

            # กำหนดสถานะเริ่มต้นตามวิธีการชำระเงิน
            # - pay_at_store  → รอชำระเงิน
            # - อื่น ๆ (promptpay) → ชำระเงินสำเร็จ
            if pay_method == "pay_at_store":
                initial_status = RentalOrder.STATUS_WAITING_PAY
            else:
                initial_status = RentalOrder.STATUS_PAID

            order = RentalOrder.objects.create(
                user=request.user,
                dress=dress,
                rental_shop=dress.shop,
                pickup_date=start_date,
                return_date=end_date,
                total_price=total_price,
                status=initial_status,
                omise_charge_id=charge_id or None,
            )

    ctx = {
        "dress": dress,
        "start_date": start_date,
        "end_date": end_date,
        "days": days,
        "method": method,
        "pay_method": pay_method,
        "rental_fee": rental_fee,
        "deposit": deposit,
        "shipping": shipping,
        "amount_baht": amount,
        "pickup_slot": pickup_slot,
        "return_slot": return_slot,
        "order_ref": order_ref or charge_id or "",
        "charge_id": charge_id or "",
        "order": order,
    }
    return render(request, "dress/rent_success.html", ctx)





# ฟังก์ชันนี้คือ “จุดรับ Webhook จาก Omise” ค่ะ
# ใช้ตอนที่ Omise ยิงข้อมูลกลับมาหลังจากมีเหตุการณ์เกี่ยวกับการชำระเงิน

@csrf_exempt
def omise_webhook(request):
    """
    รับ Webhook จาก Omise (Sandbox / Live)
    ใน dev/staging เราเพียงแค่รับไว้และตอบ 200 กลับ เพื่อให้ Omise ไม่ส่งซ้ำ
    คุณสามารถต่อยอด: อัปเดตสถานะคำสั่งซื้อ/บันทึก charge_id ลงฐานข้อมูล ฯลฯ
    """
    # อนุญาตเฉพาะ POST
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    # แปลง raw body → JSON
    try:
        raw = request.body.decode("utf-8") if request.body else "{}"
        payload = json.loads(raw) # ดึงข้อมูลที่สำคัญจาก payload
    except json.JSONDecodeError:
        return HttpResponseBadRequest("invalid json")

    event_key = payload.get("key") or payload.get("type")
    data = payload.get("data") or {}
    charge_id = (data.get("id") or "") if isinstance(data, dict) else ""

    # TODO: map charge_id -> ออเดอร์ แล้วอัปเดตสถานะใน DB ตาม event_key
    # เช่น ถ้า event_key == "charge.complete" และสถานะเป็น paid
    # ก็ไปค้น RentalOrder ที่ผูกกับ charge_id แล้วตั้ง status = 'paid'

    return JsonResponse({"ok": True, "event": event_key, "charge_id": charge_id})


# ---- Poll API: เช็กสถานะชำระเงินจาก charge_id ---------------------
@require_GET
def payment_status_api(request):
    """
    โพลล์เช็กสถานะชำระเงินด้วย charge_id
    GET /dress/payments/status/?charge_id=chrg_xxx
    คืนค่า: {"ok": True, "status": "paid|pending|failed|expired", "charge_id": "..."}
    """
    charge_id = (request.GET.get("charge_id") or "").strip()
    if not charge_id:
        return JsonResponse({"ok": False, "error": "missing charge_id"}, status=400)

    # ตั้งค่า key
    omise.api_public = settings.OMISE_PUBLIC_KEY or ""
    omise.api_secret = settings.OMISE_SECRET_KEY or ""

    # ถ้ายังไม่ได้ตั้งค่า key (เช่น dev ที่ไม่อยากยิง Omise จริง)
    # ให้ถือว่า "จ่ายสำเร็จ" ทันทีเป็นโหมด mock
    if not (omise.api_public and omise.api_secret):
        return JsonResponse({"ok": True, "status": "paid", "charge_id": charge_id})

    try:
        ch = omise.Charge.retrieve(charge_id)
        status = getattr(ch, "status", "pending") or "pending"
        return JsonResponse({"ok": True, "status": status, "charge_id": charge_id})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)
    


# ============================================================
# Helper: สร้าง Notification ให้ผู้ใช้
# ============================================================
def create_notification(user, title, message, type="order", order=None, sender_shop=None):
    """
    helper สร้าง Notification
    - type: order / payment / reminder / shop_message / system
    """
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        type=type,
        related_order=order,
        sender_shop=sender_shop,
    )


# ============================================================
# Chat  (ฝั่งลูกค้า)
# ============================================================

@login_required
def shop_chat_view(request, shop_id):
    """
    หน้าแชทหลักสำหรับลูกค้าที่ต้องการสอบถามร้านก่อนเช่า
    - shop_id = id ของโมเดล Shop
    - customer = request.user
    1 คู่ (customer, shop_user) ใช้ห้องแชทเดียวกัน
    """
    customer = request.user

    # ดึงร้านและเจ้าของร้าน
    shop_obj = get_object_or_404(Shop, pk=shop_id)
    shop_user = shop_obj.owner

    # ถ้ากดมาจากหน้ารายละเอียดชุด จะมี dress_id ติดมาด้วย
    dress_obj = None
    dress_id = request.GET.get("dress_id")
    if dress_id:
        try:
            from .models import Dress
            dress_obj = Dress.objects.get(pk=dress_id, shop=shop_obj)
        except Dress.DoesNotExist:
            dress_obj = None

    # สร้างหรือดึงห้องเดิม
    thread, created = ShopChatThread.objects.get_or_create(
        customer=customer,
        shop=shop_user,
    )

    messages_qs = thread.messages.select_related("sender").all()

    context = {
        "thread": thread,
        "shop_obj": shop_obj,
        "shop_user": shop_user,
        "messages": messages_qs,
        "dress_obj": dress_obj,
    }
    return render(request, "dress/shop_chat.html", context)

# ฟังก์ชันนี้คือ “ฝั่งลูกค้ากดส่งข้อความ” ในหน้าแชทร้าน
@login_required
@require_POST
def shop_chat_send_message(request, shop_id):
    """
    ส่งข้อความจากฝั่งลูกค้า (หน้าร้าน)
    shop_id = id ของโมเดล Shop

    รองรับทั้ง:
    - ข้อความอย่างเดียว
    - รูปอย่างเดียว
    - ข้อความ + รูป
    """
    #ระบุคนที่ส่ง = ลูกค้า
    customer = request.user

    # หา Shop และ user เจ้าของร้าน
    shop_obj = get_object_or_404(Shop, pk=shop_id)
    shop_user = shop_obj.owner

    # หา/สร้างห้องแชท
    thread, created = ShopChatThread.objects.get_or_create(
        customer=customer,
        shop=shop_user,
    )

    # ดึงข้อมูลจากฟอร์ม
    message_text = request.POST.get("message", "").strip()
    image_file = request.FILES.get("image")  # ชื่อ field ใน <input type="file" name="image">

    # ถ้าไม่มีทั้งข้อความและรูป → error
    if not message_text and not image_file:
        return JsonResponse({"error": "empty_message"}, status=400)

    # สร้าง message (ข้อความอาจว่างได้)
    msg = ShopChatMessage.objects.create(
        thread=thread,
        sender=customer,
        message=message_text or "",
        image=image_file,
        created_at=timezone.now(),
    )

    return JsonResponse(
        {
            "id": msg.id,
            "sender": customer.get_full_name() or customer.username,
            "message": msg.message,
            "created_at": msg.created_at.strftime("%Y-%m-%d %H:%M"),
            "image_url": msg.image.url if msg.image else "",
            "is_me": True,
        }
    )


# ฟังก์ชันนี้คือ API สำหรับ “ดึงข้อความทั้งหมดในห้องแชท (ฝั่งลูกค้า)”
@login_required
@require_GET
def shop_chat_messages_api(request, shop_id):
    """
    ดึงข้อความทั้งหมดในห้องแชททั่วไป (ใช้กับ AJAX ถ้าต้องการ)
    เวอร์ชันนี้รองรับฝั่งลูกค้าเป็นหลัก
    - รองรับทั้งข้อความและรูปภาพ (image)
    """
    user = request.user

    # หา Shop และ user เจ้าของร้านจาก shop_id
    shop_obj = get_object_or_404(Shop, pk=shop_id)
    shop_user = shop_obj.owner

    # หา thread ของคู่ (customer, shop)
    try:
        thread = ShopChatThread.objects.get(customer=user, shop=shop_user)
    except ShopChatThread.DoesNotExist:
        return JsonResponse({"messages": []})

    messages_qs = thread.messages.select_related("sender").all()

    data = []
    for m in messages_qs:
        data.append(
            {
                "id": m.id,
                "sender": m.sender.get_full_name() or m.sender.username,
                "is_me": m.sender_id == user.id,
                "message": m.message,
                "created_at": m.created_at.strftime("%Y-%m-%d %H:%M"),
                "image_url": m.image.url if getattr(m, "image", None) else "",
            }
        )

    return JsonResponse({"messages": data})




# ============================================================
# Chat Inbox: กล่องข้อความของร้าน (Pre-Order Chat) (ฝั่งร้านเช่า)
# ============================================================
# ฟังก์ชันนี้คือ “กล่องข้อความฝั่งร้าน” เอาไว้ให้เจ้าของร้าน
@login_required
def shop_chat_inbox(request):
    """
    กล่องข้อความของร้าน
    แสดงห้องแชททั้งหมดที่ shop = request.user
    พร้อมแนบข้อความล่าสุดและสถานะยังไม่ได้อ่าน
    """
    user = request.user

    threads = (
        ShopChatThread.objects
        .filter(shop=user)
        .select_related("customer")
        .prefetch_related("messages")
        .order_by("-created_at")
    )

    # ใส่ attribute ชั่วคราวให้แต่ละ thread
    for t in threads:
        last_msg = t.messages.order_by("-created_at").first()
        if last_msg:
            t.last_message = last_msg.message
            t.last_message_time = last_msg.created_at
            t.has_unread = last_msg.sender_id != user.id
        else:
            t.last_message = ""
            t.last_message_time = None
            t.has_unread = False

    shop_obj = Shop.objects.filter(owner=user).first()

    context = {
        "threads": threads,
        "shop_obj": shop_obj,
    }
    return render(request, "dress/shop_chat_inbox.html", context)

# ฟังก์ชันนี้คือ “หน้าจอแชทแบบเต็ม” ฝั่งร้าน ที่เข้าไปคุยกับลูกค้าในห้องหนึ่งห้องโดยเฉพาะ
# เวลาอยู่ในหน้าอินบ็อกซ์แล้วกดเข้าไปที่ห้องแชท จะมาลงฟังก์ชันนี้
@login_required
def shop_chat_thread_view(request, thread_id):
    """
    ร้านเปิดห้องแชทคุยกับลูกค้า (หลังร้าน)
    ตรวจสอบสิทธิ์: ต้องเป็น shop หรือ customer ใน thread นี้เท่านั้น
    """
    user = request.user
    thread = get_object_or_404(ShopChatThread, id=thread_id)

    if user != thread.shop and user != thread.customer:
        return HttpResponseBadRequest("คุณไม่มีสิทธิ์ในห้องแชทนี้")

    messages_qs = thread.messages.select_related("sender").all()

    context = {
        "thread": thread,
        "customer": thread.customer,
        "shop_user": thread.shop,
        "messages": messages_qs,
    }
    return render(request, "dress/shop_chat_shop.html", context)


# ฟังก์ชันนี้คือ “ฝั่งร้านกดส่งข้อความ” ในหน้าแชทหลังร้าน
@login_required
@require_POST
def shop_chat_thread_send(request, thread_id):
    """
    ส่งข้อความในห้องแชทฝั่งหลังร้าน (ใช้ได้ทั้งลูกค้าและร้าน)
    """
    user = request.user
    thread = get_object_or_404(ShopChatThread, id=thread_id)

    # ตรวจสิทธิ์ ว่าต้องเป็นคนหนึ่งในห้องเท่านั้น
    if user != thread.shop and user != thread.customer:
        return JsonResponse({"error": "permission_denied"}, status=403)

    message_text = request.POST.get("message", "").strip()
    image_file = request.FILES.get('image')

    # ถ้าไม่มีทั้งข้อความและรูป ให้ error
    if not message_text and not image_file:
        return JsonResponse({"error": "empty_message"}, status=400)

    # บันทึกข้อความ
    msg = ShopChatMessage.objects.create(
        thread=thread,
        sender=user,
        message=message_text or "",
        image=image_file,
        created_at=timezone.now(),
    )

    # ==========================
    # สร้าง Notification ให้ "อีกฝ่าย"
    # ==========================

    # หา Shop object จาก owner = thread.shop (User ของฝั่งร้าน)
    shop_obj = Shop.objects.filter(owner=thread.shop).first()

    if user == thread.shop:
        # คนส่งคือ "ร้าน"  -> แจ้งเตือน "ลูกค้า"
        notify_user = thread.customer
        title = f"ร้าน {shop_obj.name if shop_obj else 'ร้านของคุณ'} ส่งข้อความถึงคุณ"
        preview = message_text or "ร้านส่งรูปภาพใหม่ให้คุณ"
    else:
        # คนส่งคือ "ลูกค้า" -> แจ้งเตือน "ร้าน"
        notify_user = thread.shop
        title = f"ลูกค้า {user.username} ส่งข้อความใหม่ถึงร้านคุณ"
        preview = message_text or "ลูกค้าส่งรูปภาพใหม่ถึงร้านคุณ"

    Notification.objects.create(
        user=notify_user,      # คนที่ได้รับแจ้งเตือน
        title=title,
        message=preview,
        type="shop_message",
        sender_shop=shop_obj,  # ร้านที่เกี่ยวข้องกับแชทนี้
    )

    return JsonResponse(
        {
            "id": msg.id,
            "sender": user.get_full_name() or user.username,
            "message": msg.message,
            "created_at": msg.created_at.strftime("%Y-%m-%d %H:%M"),
            "image_url": msg.image.url if msg.image else "",
            "is_me": True,
        }
    )



# ฟังก์ชันนี้คือ API สำหรับ “ดึงข้อความทั้งหมดในห้องแชทฝั่งหลังร้าน”
@login_required
@require_GET
def shop_chat_thread_messages(request, thread_id):
    """
    ดึงข้อความทั้งหมดในห้องแชทฝั่งหลังร้าน (สำหรับ refresh แบบ AJAX)
    """
    user = request.user
    thread = get_object_or_404(ShopChatThread, id=thread_id)

    if user != thread.shop and user != thread.customer:
        return JsonResponse({"error": "permission_denied"}, status=403)

    messages_qs = thread.messages.select_related("sender").all()

    data = []
    for m in messages_qs:
        data.append(
            {
                "id": m.id,
                "sender": m.sender.get_full_name() or m.sender.username,
                "is_me": m.sender_id == user.id,
                "message": m.message,
                "created_at": m.created_at.strftime("%Y-%m-%d %H:%M"),
                'image_url': m.image.url if m.image else "",
            }
        )

    return JsonResponse({"messages": data})


# หน้าการตั้งค่าร้าน (หลังร้าน)
@login_required(login_url='dress:login')
def store_settings(request, store_id):
    # ดึงร้านของ user คนนี้ เหมือนกับ back_office
    store = get_object_or_404(Shop, id=store_id, owner=request.user)

    days = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]

    context = {
        "store": store,
        "store_id": store_id,
        "days": days,
    }
    return render(request, "dress/store_settings.html", context)



# โปรไฟล์ร้าน (หน้าร้าน)
@login_required(login_url="dress:login")
def store_profile(request, store_id):
    store = get_object_or_404(Shop, id=store_id, owner=request.user)

    # สถิติพื้นฐานของร้าน
    orders_qs = RentalOrder.objects.filter(rental_shop=store)
    reviews_qs = Review.objects.filter(dress__shop=store)

    # ใช้ is_available ตามโมเดลของคุณ
    dresses_qs = Dress.objects.filter(shop=store, is_available=True)

    total_orders = orders_qs.count()
    total_reviews = reviews_qs.count()
    total_dresses = dresses_qs.count()

    # ถ้าไม่มีฟิลด์ created_at ให้เปลี่ยนเป็น order_by("-id") แทน
    latest_dresses = dresses_qs.order_by("-id")[:6]

    context = {
        "store": store,
        "store_id": store_id,
        "total_orders": total_orders,
        "total_reviews": total_reviews,
        "total_dresses": total_dresses,
        "latest_dresses": latest_dresses,
    }
    return render(request, "dress/store_profile.html", context)




# ย้ายชุดลงคลัง / นำชุดกลับมาแสดง
@login_required(login_url="dress:login")
def archive_dress(request, store_id, dress_id):
    """
    ย้ายชุดลงคลัง (ซ่อนจากลูกค้า แต่ไม่ลบข้อมูล)
    """
    store = get_object_or_404(Shop, id=store_id, owner=request.user)
    dress = get_object_or_404(Dress, id=dress_id, shop=store)

    dress.is_archived = True
    dress.save()

    messages.success(request, f"ย้ายชุด '{dress.name}' ลงคลังเรียบร้อยแล้ว")
    return redirect("dress:store_dress", store_id=store.id)


@login_required(login_url="dress:login")
def unarchive_dress(request, store_id, dress_id):
    """
    นำชุดกลับมาแสดงบนหน้าร้าน
    """
    store = get_object_or_404(Shop, id=store_id, owner=request.user)
    dress = get_object_or_404(Dress, id=dress_id, shop=store)

    dress.is_archived = False
    dress.save()

    messages.success(request, f"นำชุด '{dress.name}' กลับมาแสดงหน้าร้านแล้ว")
    return redirect("dress:store_dress", store_id=store.id)




# ตัวช่วยคำนวณราคาตามจำนวนวันสำหรับหน้าชำระเงิน (cart checkout)
def _calc_days_cart(start_date: date, end_date: date) -> int:
    # ให้ตรงกับ JS: end - start (14 -> 16 = 2)
    if end_date <= start_date:
        return 0
    return (end_date - start_date).days


def _get_pack_price_for_days(dress, days: int):
    """
    คืนค่า (price, source)
    source: override/template/daily_fallback/none
    """
    # 1) override รายชุด
    ov = dress.override_prices.filter(day_count=days).first()
    if ov:
        return Decimal(ov.total_price), "override"

    # 2) template ของชุด
    if getattr(dress, "price_template_id", None):
        it = dress.price_template.items.filter(day_count=days).first()
        if it:
            return Decimal(it.total_price), "template"

    # 3) fallback รายวัน
    if dress.daily_price and Decimal(dress.daily_price) > 0 and days > 0:
        return Decimal(dress.daily_price) * Decimal(days), "daily_fallback"

    return None, "none"


@login_required
def cart_checkout(request):
    ids = request.GET.getlist("ids")
    if not ids:
        return HttpResponseBadRequest("no items selected")

    items = (
        CartItem.objects
        .select_related("dress", "dress__shop")
        .filter(id__in=ids, user=request.user)
    )
    if not items.exists():
        return HttpResponseBadRequest("items not found")

    shop_ids = set(items.values_list("dress__shop_id", flat=True))
    if len(shop_ids) != 1:
        return HttpResponseBadRequest("must be same shop")

    shop = items.first().dress.shop
    total_qty = sum(int(getattr(it, "quantity", 1) or 1) for it in items)

    shipping_fee = shop.outbound_shipping_fee_for_qty(total_qty) if shop else Decimal("0.00")

    deposit_total = Decimal("0.00")
    for it in items:
        qty = int(getattr(it, "quantity", 1) or 1)
        deposit = getattr(it.dress, "deposit", Decimal("0.00")) or Decimal("0.00")
        deposit_total += Decimal(str(deposit)) * qty

    # ส่งแพ็คราคาไปให้หน้า checkout คำนวณตามจำนวนวัน
    # { "<cart_item_id>": { "1": "120.00", "2": "140.00", ... } }
    item_packages = {}
    for it in items:
        pkg = {}
        # ดึง override ของชุด
        for ov in it.dress.override_prices.all():
            pkg[int(ov.day_count)] = Decimal(ov.total_price)

        # ดึง template ของชุด
        if it.dress.price_template_id:
            for pit in it.dress.price_template.items.all():
                pkg[int(pit.day_count)] = Decimal(pit.total_price)

        # แปลงเป็น str
        item_packages[str(it.id)] = {str(k): str(v) for k, v in pkg.items()}

    return render(request, "dress/cart_checkout.html", {
        "items": items,
        "store": shop,
        "total_qty": total_qty,
        "shipping_fee": shipping_fee,
        "deposit_total": deposit_total,
        "item_packages": item_packages,
    })


@login_required
@require_POST
def cart_checkout_confirm(request):
    ids = request.POST.getlist("ids")
    if not ids:
        return HttpResponseBadRequest("no items selected")

    start_date_raw = request.POST.get("start_date")
    end_date_raw = request.POST.get("end_date")
    if not start_date_raw or not end_date_raw:
        return HttpResponseBadRequest("missing dates")

    try:
        start_date = date.fromisoformat(start_date_raw)
        end_date = date.fromisoformat(end_date_raw)
    except ValueError:
        return HttpResponseBadRequest("invalid date format")

    days = _calc_days_cart(start_date, end_date)
    if days <= 0:
        return HttpResponseBadRequest("end_date must be greater than start_date")

    items = (
        CartItem.objects
        .select_related("dress", "dress__shop", "dress__price_template")
        .filter(id__in=ids, user=request.user)
    )
    if not items.exists():
        return HttpResponseBadRequest("items not found")

    shop_ids = set(items.values_list("dress__shop_id", flat=True))
    if len(shop_ids) != 1:
        return HttpResponseBadRequest("must be same shop")

    shop = items.first().dress.shop
    total_qty = sum(int(getattr(it, "quantity", 1) or 1) for it in items)
    shipping_fee = shop.outbound_shipping_fee_for_qty(total_qty) if shop else Decimal("0.00")

    deposit_total = Decimal("0.00")
    rental_total = Decimal("0.00")

    lines = []
    for it in items:
        qty = int(getattr(it, "quantity", 1) or 1)
        deposit = Decimal(str(getattr(it.dress, "deposit", "0.00") or "0.00")) * qty
        deposit_total += deposit

        pack_price, source = _get_pack_price_for_days(it.dress, days)
        if pack_price is None:
            return HttpResponseBadRequest(f"no price for {days} days: {it.dress.name}")

        line_rent = Decimal(pack_price) * qty
        rental_total += line_rent

        lines.append({
            "item": it,
            "qty": qty,
            "pricing_source": source,
            "pack_price_per_unit": Decimal(pack_price),
            "line_rent": line_rent,
            "line_deposit": deposit,
        })

    grand_total = rental_total + deposit_total + Decimal(shipping_fee)

    # ไปหน้า Step 3 (สรุปก่อนชำระเงินจริง)
    return render(request, "dress/cart_checkout_confirm.html", {
        "store": shop,
        "items": items,
        "lines": lines,
        "days": days,
        "start_date": start_date,
        "end_date": end_date,
        "total_qty": total_qty,
        "shipping_fee": shipping_fee,
        "deposit_total": deposit_total,
        "rental_total": rental_total,
        "grand_total": grand_total,
    })


# จัดการเริ่มต้นการชำระเงินจากตะกร้า (สร้าง Order และ OrderItems)
@login_required
@require_POST
def cart_payment_start(request):
    ids = request.POST.getlist("ids")
    start_date = parse_date(request.POST.get("start_date") or "")
    end_date   = parse_date(request.POST.get("end_date") or "")

    if not ids or not start_date or not end_date:
        return render(request, "dress/error.html", {"message": "ข้อมูลไม่ครบ"})

    items = (
        CartItem.objects
        .select_related("dress", "dress__shop")
        .filter(id__in=ids, user=request.user)
    )
    if not items.exists():
        return render(request, "dress/error.html", {"message": "ไม่พบสินค้าในตะกร้า"})

    shop_ids = set(items.values_list("dress__shop_id", flat=True))
    if len(shop_ids) != 1:
        return render(request, "dress/error.html", {"message": "ตะกร้าต้องเป็นร้านเดียวกัน"})

    days = (end_date - start_date).days  # 14->16 = 2
    if days <= 0:
        return render(request, "dress/error.html", {"message": "วันคืนต้องมากกว่าวันเริ่ม"})

    shop = items.first().dress.shop

    rental_total = Decimal("0.00")
    deposit_total = Decimal("0.00")
    total_qty = 0

    # คำนวณจากแพ็กจริงของแต่ละชุด (ต้องอยู่ในลูป)
    for it in items:
        qty = int(getattr(it, "quantity", 1) or 1)
        total_qty += qty

        pack_price, source = _get_pack_price_for_days(it.dress, days)
        if pack_price is None:
            return render(request, "dress/error.html", {"message": f"ไม่พบราคาสำหรับ {days} วัน: {it.dress.name}"})

        rental_total += Decimal(pack_price) * Decimal(qty)
        deposit_total += Decimal(str(it.dress.deposit or 0)) * Decimal(qty)

    shipping_fee = shop.outbound_shipping_fee_for_qty(total_qty) if shop else Decimal("0.00")
    grand_total = rental_total + deposit_total + shipping_fee

    order = Order.objects.create(
        user=request.user,
        shop=shop,
        start_date=start_date,
        end_date=end_date,
        days=days,
        rental_total=rental_total,
        deposit_total=deposit_total,
        shipping_fee=shipping_fee,
        grand_total=grand_total,
        status="pending_payment",
    )

    bulk = []
    for it in items:
        qty = int(getattr(it, "quantity", 1) or 1)

        pack_price, source = _get_pack_price_for_days(it.dress, days)
        bulk.append(OrderItem(
            order=order,
            dress=it.dress,
            qty=qty,
            unit_price=Decimal(pack_price),
            line_total=Decimal(pack_price) * Decimal(qty),
            pricing_source=source,
        ))
    OrderItem.objects.bulk_create(bulk)

    return redirect("dress:payment_by_order", order_id=order.id)



@login_required(login_url="dress:login")
def payment_page_by_order(request, order_id: int):
    """
    หน้าชำระเงินของ Order (รองรับ Cart หลายชุด)
    ต้องมี Order model ของคุณอยู่แล้ว และมี field เก็บ omise_charge_id/charge_id (ถ้ามี)
    """

    # ปรับชื่อ Model/Field ให้ตรงโปรเจกต์คุณ
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # ถ้าคุณเก็บ charge id ไว้คนละชื่อ ให้แก้ตรงนี้
    charge_id = getattr(order, "omise_charge_id", None) or getattr(order, "charge_id", None)

    # ยอดเงินรวม (Decimal) ของ Order
    grand_total = getattr(order, "grand_total", None) or getattr(order, "total_amount", None)
    if grand_total is None:
        # ถ้าโปรเจกต์คุณใช้ชื่ออื่น ให้แก้ให้ตรง
        return render(request, "dress/error.html", {"message": "ไม่พบยอดชำระของออเดอร์นี้"})

    # สร้าง/ดึง Charge และ QR
    # ถ้าคุณมีไฟล์/โค้ด Omise เดิมอยู่แล้ว ให้ย้าย logic จากของเดิมมาไว้ตรงนี้ได้
    import omise
    omise.api_secret = settings.OMISE_SECRET_KEY

    if not charge_id:
        charge = omise.Charge.create(
            amount=int(grand_total * 100),  # บาท -> สตางค์
            currency="thb",
            source={"type": "promptpay"},
            description=f"Order #{order.id}"
        )

        # บันทึก charge id กลับไปที่ order (ปรับ field ให้ตรงโปรเจกต์คุณ)
        if hasattr(order, "omise_charge_id"):
            order.omise_charge_id = charge.id
            order.save(update_fields=["omise_charge_id"])
        elif hasattr(order, "charge_id"):
            order.charge_id = charge.id
            order.save(update_fields=["charge_id"])
    else:
        charge = omise.Charge.retrieve(charge_id)

    qr_url = None
    expires_at = None
    try:
        qr_url = charge.source.scannable_code.image.download_uri
        expires_at = charge.expires_at
    except Exception:
        qr_url = None

    return render(request, "dress/payment_by_order.html", {
        "order": order,
        "charge": charge,
        "qr_url": qr_url,
        "expires_at": expires_at,
    })








@login_required
@require_POST
def payment_mark_paid_test(request, order_id: int):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    with transaction.atomic():
        # 1) mark paid
        if hasattr(order, "status"):
            order.status = "paid"
            order.save(update_fields=["status"])

        # 2) create RentalOrder(s)
        _create_rental_orders_from_order(order)

        # 3) เคลียร์ตะกร้าร้านนี้ออก (ไม่งั้นเหมือนยังไม่ได้เช่า)
        CartItem.objects.filter(user=order.user, dress__shop=order.shop).delete()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return HttpResponse("OK")

    return redirect("dress:payment_success", order_id=order.id)




@login_required
def payment_success(request, order_id: int):
    """
    หน้าแสดงผลชำระเงินสำเร็จแบบละเอียด (สำหรับ Order จาก Cart)
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)

    items = (
        OrderItem.objects
        .select_related("dress")
        .filter(order=order)
        .order_by("id")
    )

    # ถ้ามี charge id เก็บไว้ใน order
    charge_id = getattr(order, "omise_charge_id", None) or getattr(order, "charge_id", None)

    # ไม่บังคับ retrieve ก็ได้ แต่ถ้าอยากโชว์ข้อมูลเพิ่ม
    charge = None
    try:
        if charge_id:
            import omise
            omise.api_secret = settings.OMISE_SECRET_KEY
            charge = omise.Charge.retrieve(charge_id)
    except Exception:
        charge = None

    return render(request, "dress/payment_success_by_order.html", {
        "order": order,
        "items": items,
        "charge": charge,
    })









def _create_rental_orders_from_order(order: Order):
    """
    สร้าง RentalOrder จาก Order/OrderItem (ตะกร้า)
    1 Order -> หลาย RentalOrder (ตามจำนวนรายการชุดในออเดอร์)
    """

    # กันสร้างซ้ำ (ถ้ากดซ้ำ / รีเฟรช)
    already = RentalOrder.objects.filter(
        user=order.user,
        rental_shop=order.shop,
        pickup_date=order.start_date,
        return_date=order.end_date,
        omise_charge_id=getattr(order, "omise_charge_id", None) or getattr(order, "charge_id", None),
    )
    if already.exists():
        return list(already)

    created = []
    items = OrderItem.objects.select_related("dress").filter(order=order)

    # ถ้าคุณอยาก “รวมค่าส่ง” เข้า RentalOrder ด้วย ให้ใส่ให้เฉพาะตัวแรก (กันบวกซ้ำหลายรอบ)
    shipping_fee = Decimal(str(getattr(order, "shipping_fee", 0) or 0))
    first = True

    for it in items:
        qty = int(getattr(it, "qty", 1) or 1)

        # ค่าเช่ารวมของรายการนี้
        if getattr(it, "line_total", None) is not None:
            line_rent = Decimal(str(it.line_total))
        else:
            unit_price = Decimal(str(getattr(it, "unit_price", 0) or 0))
            line_rent = unit_price * Decimal(qty)

        # มัดจำ: ใช้จาก dress.deposit * qty (เพราะ OrderItem ไม่มี line_deposit)
        deposit_per_unit = Decimal(str(getattr(it.dress, "deposit", 0) or 0))
        line_deposit = deposit_per_unit * Decimal(qty)

        # รวมเป็น total_price ของ RentalOrder
        total_price = line_rent + line_deposit
        if first and shipping_fee > 0:
            total_price += shipping_fee
            first = False

        ro = RentalOrder.objects.create(
            user=order.user,
            dress=it.dress,
            rental_shop=order.shop,
            pickup_date=order.start_date,
            return_date=order.end_date,
            total_price=total_price,
            status=RentalOrder.STATUS_PAID,
            omise_charge_id=getattr(order, "omise_charge_id", None) or getattr(order, "charge_id", None),
        )
        created.append(ro)

    return created







@login_required
def order_detail(request, order_id: int):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # ดึงรายการสินค้าในออเดอร์ (รองรับทั้งมี related_name และไม่มี)
    items = None

    # กรณีคุณตั้ง related_name ไว้ เช่น related_name="items"
    if hasattr(order, "items"):
        try:
            items = order.items.select_related("dress")
        except Exception:
            items = None

    # fallback: ดึงจาก OrderItem ตรง ๆ
    if items is None:
        items = OrderItem.objects.filter(order=order).select_related("dress")

    return render(request, "dress/order_detail.html", {
        "order": order,
        "items": items,
    })




@login_required
def shop_pending_notice(request):
    return render(request, "dress/shop_pending_notice.html")


def handler403(request, exception=None):
    return render(request, "403.html", status=403)
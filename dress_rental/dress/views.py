from decimal import Decimal
import json

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError
from django.db.models import Q, Avg
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import (
    Shop, Dress, Category, Review, Favorite, CartItem, Rental, UserProfile,
    PriceTemplate, PriceTemplateItem, ShippingRule, ShippingBracket
)


# -------------------------
# หน้าแรก
# -------------------------
def home(request):
    q = str(request.GET.get("q", "")).strip()
    category = str(request.GET.get("category", "")).strip()

    dresses = Dress.objects.filter(is_available=True)
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


# -------------------------
# Auth
# -------------------------
def signup_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password != confirm_password:
            messages.error(request, "รหัสผ่านไม่ตรงกัน")
            return redirect("signup")

        if User.objects.filter(username=username).exists():
            messages.error(request, "ชื่อผู้ใช้นี้ถูกใช้งานแล้ว")
            return redirect("signup")

        if User.objects.filter(email=email).exists():
            messages.error(request, "อีเมลนี้ถูกใช้งานแล้ว")
            return redirect("signup")

        User.objects.create_user(username=username, email=email, password=password)
        messages.success(request, "สมัครสมาชิกสำเร็จ กรุณาเข้าสู่ระบบ")
        return redirect("login")

    return render(request, "dress/signup.html")


def login_view(request):
    if request.method == "POST":
        username_or_email = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        try:
            user_obj = User.objects.get(Q(username=username_or_email) | Q(email=username_or_email))
            username = user_obj.username
        except User.DoesNotExist:
            messages.error(request, "ไม่พบบัญชีผู้ใช้งานนี้")
            return redirect("login")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("login_redirect")
        messages.error(request, "รหัสผ่านไม่ถูกต้อง")
        return redirect("login")

    return render(request, "dress/login.html")


def logout_view(request):
    logout(request)
    messages.info(request, "ออกจากระบบเรียบร้อยแล้ว")
    return redirect("login")


@login_required(login_url="login")
def login_redirect(request):
    shop = Shop.objects.filter(owner=request.user).first()
    if shop:
        return redirect("my_store", store_id=shop.id)
    return redirect("member_home")


@login_required(login_url="login")
def member_home(request):
    q = request.GET.get("q")
    category = request.GET.get("category")

    dresses = Dress.objects.all()
    if q:
        dresses = dresses.filter(name__icontains=q)
    if category:
        dresses = dresses.filter(categories__name=category)

    categories = Category.objects.all()
    return render(request, "dress/member_home.html", {
        "dresses": dresses,
        "categories": categories,
        "selected_category": category,
    })


# -------------------------
# ร้านค้า
# -------------------------
@login_required(login_url="login")
def open_store(request):
    if request.method == "POST":
        shop_name = request.POST.get("shop_name", "").strip()
        province = request.POST.get("province", "").strip()
        phone = request.POST.get("phone", "").strip()
        fee = request.POST.get("fee", "").strip()
        shop_logo = request.FILES.get("shop_logo")

        if not shop_name or not province:
            messages.error(request, "กรุณากรอกข้อมูลร้านให้ครบถ้วน")
            return redirect("open_store")

        shop = Shop.objects.create(
            owner=request.user,
            name=shop_name,
            province=province,
            phone=phone,
            fee=fee,
            shop_logo=shop_logo,
        )
        messages.success(request, "เปิดร้านสำเร็จ")
        return redirect("my_store", store_id=shop.id)

    return render(request, "dress/open_store.html")


@login_required(login_url="login")
def my_store(request, store_id):
    shop = get_object_or_404(Shop, id=store_id, owner=request.user)
    products = Dress.objects.filter(shop=shop)
    return render(request, "dress/my_store.html", {"store": shop, "products": products})


@login_required(login_url="login")
def store_dress(request, store_id):
    shop = get_object_or_404(Shop, id=store_id, owner=request.user)
    dresses = Dress.objects.filter(shop=shop)

    category = request.GET.get("category")
    if category and category != "ทั้งหมด":
        dresses = dresses.filter(categories__name=category)

    categories = Category.objects.filter(dress__shop=shop).distinct()
    total_dresses = Dress.objects.filter(shop=shop).count()

    return render(request, "dress/store_dress.html", {
        "store": shop,
        "dresses": dresses,
        "categories": categories,
        "selected_category": category,
        "total_dresses": total_dresses,
    })


# -------------------------
# สินค้าในร้าน
# -------------------------
@login_required(login_url="login")
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

        # หมวดหมู่
        category_ids = request.POST.get("categories", "").split(",")
        category_ids = [int(cid) for cid in category_ids if cid.strip().isdigit()]
        if category_ids:
            dress.categories.set(category_ids)

        # ฟิลด์แพ็ก/วันสูงสุด
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
        return redirect("store_dress", store_id=store_id)

    # GET: ส่งข้อมูลให้เทมเพลตใช้เติม UI
    categories = Category.objects.all()
    price_templates = shop.price_templates.order_by("name")

    # shipping init -> ใช้เติมตารางค่าส่งในหน้า
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


@login_required(login_url="login")
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

        # หมวดหมู่ (multi-select)
        selected_cats = request.POST.getlist("categories")
        if selected_cats:
            cats = [int(cid) for cid in selected_cats if str(cid).isdigit()]
            dress.categories.set(cats)

        # รูปภาพ
        if request.POST.get("remove_image") == "1":
            if dress.image:
                dress.image.delete(save=False)
            dress.image = None
        elif request.FILES.get("image"):
            dress.image = request.FILES.get("image")

        # ราคาแพ็ก: เลือกเทมเพลต/วันสูงสุดเฉพาะชุด
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
        return redirect("store_dress", store_id=store_id)

    # GET
    categories = Category.objects.all()
    price_templates = shop.price_templates.order_by("name")

    # ใช้สำหรับ “แสดงรายการราคา” ของเทมเพลตที่ถูกเลือกตอนเปิดหน้า
    tpl_preview_items = []
    if dress.price_template:
        tpl_preview_items = list(
            dress.price_template.items.order_by("day_count").values("day_count", "total_price")
        )

    # shipping init (โชว์/แก้ของร้าน)
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
            "tpl_preview_items": tpl_preview_items,  # <-- เพิ่มส่งเข้า template
            "shipping_init_json": json.dumps(shipping_init, ensure_ascii=False),
        },
    )


# ============ API: อ่านรายละเอียดเทมเพลต (ใช้เติมตาราง/เปิด modal แก้ไข) ============
@login_required
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


# ============ API: อัปเดตเทมเพลตราคาเช่า ============
@login_required
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
        # ชื่อ/จำนวนวันสูงสุด
        tpl.name = name
        tpl.max_days = max_days
        tpl.save()

        # ลบรายการเดิมแล้วสร้างใหม่จาก input
        tpl.items.all().delete()
        PriceTemplateItem.objects.bulk_create([
            PriceTemplateItem(template=tpl, day_count=d, total_price=p) for d, p in normalized
        ])

    return JsonResponse({
        "ok": True,
        "template": {"id": tpl.id, "name": tpl.name, "max_days": tpl.max_days}
    })




@login_required(login_url="login")
def delete_dress(request, store_id, dress_id):
    shop = get_object_or_404(Shop, id=store_id, owner=request.user)
    dress = get_object_or_404(Dress, id=dress_id, shop=shop)
    if request.method == "POST":
        if dress.image:
            dress.image.delete(save=False)
        dress.delete()
        messages.success(request, "ลบชุดเรียบร้อยแล้ว")
        return redirect("store_dress", store_id=store_id)
    return render(request, "dress/delete_dress.html", {"store": shop, "dress": dress})


@login_required(login_url="login")
def toggle_availability(request, store_id, dress_id):
    shop = get_object_or_404(Shop, id=store_id, owner=request.user)
    dress = get_object_or_404(Dress, id=dress_id, shop=shop)
    dress.is_available = not dress.is_available
    dress.save()
    if dress.is_available:
        messages.success(request, f"{dress.name} เปิดให้เช่าแล้ว")
    else:
        messages.warning(request, f"{dress.name} ปิดการเช่าชั่วคราว")
    return redirect("store_dress", store_id=store_id)


# -------------------------
# รายละเอียดสินค้า + รีวิว
# -------------------------
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


def dress_detail(request, dress_id):
    dress = get_object_or_404(Dress, pk=dress_id)

    reviews = Review.objects.filter(dress=dress)
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    latest_reviews = reviews.order_by('-created_at')[:2]

    is_favorite = False
    if request.user.is_authenticated:
        is_favorite = Favorite.objects.filter(user=request.user, dress=dress).exists()

    related_dresses = Dress.objects.filter(shop=dress.shop).exclude(id=dress.id)[:4]

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

    shipping_tiers = []
    shipping_clamp_note = None
    rule = getattr(dress.shop, "shipping_rule", None)
    if rule:
        for b in rule.brackets.all().order_by("min_qty"):
            shipping_tiers.append({"min_qty": b.min_qty, "max_qty": b.max_qty, "fee": b.fee})
        if rule.clamp_to_max and rule.brackets.exists():
            top = rule.brackets.order_by("-max_qty").first()
            shipping_clamp_note = f"มากกว่า {top.max_qty} ชุด คิดค่าส่ง {top.fee} บาท"

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
    })


@login_required
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
            return redirect('review_list', dress_id=dress.id)

    return render(request, 'dress/review_form.html', {'dress': dress})


@login_required
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
        return redirect('review_list', dress_id=dress.id)

    return render(request, 'dress/review_edit.html', {'dress': dress, 'review': review})


@login_required
def review_delete(request, dress_id, review_id):
    dress = get_object_or_404(Dress, pk=dress_id)
    review = get_object_or_404(Review, pk=review_id, user=request.user)

    if request.method == 'POST':
        review.delete()
        messages.success(request, "ลบรีวิวเรียบร้อยแล้ว")
        return redirect('review_list', dress_id=dress.id)

    return redirect('review_list', dress_id=dress.id)


# -------------------------
# Favorite
# -------------------------
@login_required
def add_to_favorite(request, dress_id):
    dress = get_object_or_404(Dress, pk=dress_id)
    Favorite.objects.get_or_create(user=request.user, dress=dress)
    messages.success(request, "บันทึกชุดนี้ไว้ในรายการโปรดแล้ว")
    return redirect('dress_detail', dress_id=dress.id)


@login_required
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

    return redirect('dress_detail', dress_id=dress.id)


@login_required
def favorite_list(request):
    favorites = Favorite.objects.filter(user=request.user).select_related("dress")
    return render(request, "dress/favorite_list.html", {"favorites": favorites})


@login_required
def favorite_count_api(request):
    count = Favorite.objects.filter(user=request.user).count()
    return JsonResponse({'count': count})


# -------------------------
# ตะกร้า
# -------------------------
@login_required
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


@login_required(login_url="login")
def add_to_cart(request, dress_id):
    dress = get_object_or_404(Dress, pk=dress_id)
    cart_item, created = CartItem.objects.get_or_create(user=request.user, dress=dress)
    if not created:
        cart_item.quantity += 1
        cart_item.save()
        messages.info(request, "เพิ่มจำนวนสินค้าในตะกร้าแล้ว")
    else:
        messages.success(request, "เพิ่มสินค้าในตะกร้าสำเร็จ")
    return redirect('dress_detail', dress_id=dress.id)


def cart_item_count(request):
    count = CartItem.objects.filter(user=request.user).count() if request.user.is_authenticated else 0
    return JsonResponse({'count': count})


@csrf_exempt
@login_required
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


@csrf_exempt
@login_required
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


@csrf_exempt
@login_required
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

        except CartItem.DoesNotExist:
            return JsonResponse({"status": "error", "message": "ไม่พบสินค้า"}, status=404)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    return JsonResponse({"status": "error", "message": "Invalid request"}, status=405)


# -------------------------
# ประวัติ/โปรไฟล์
# -------------------------
@login_required(login_url="login")
def rental_history_view(request):
    rentals = Rental.objects.filter(user=request.user).select_related("dress", "dress__shop")
    return render(request, "dress/rental_history.html", {"rentals": rentals})


@login_required(login_url="login")
def notification_page(request):
    notifications = []
    return render(request, "dress/notification.html", {"notifications": notifications})


@login_required(login_url="login")
def rental_list_view(request):
    context = {"current_rentals": [], "upcoming_rentals": [], "completed_rentals": []}
    return render(request, "dress/rental_list.html", context)


@login_required(login_url='login')
def profile_page(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(request, 'dress/profile.html', {'profile': profile})


@login_required(login_url='login')
def update_profile(request):
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    if request.method == "POST":
        user.username = request.POST.get("username", user.username)
        user.email = request.POST.get("email", user.email)
        user.save()

        profile.gender = request.POST.get("gender", profile.gender)
        profile.birth_date = request.POST.get("birth_date") or profile.birth_date
        profile.phone = request.POST.get("phone", profile.phone)
        profile.address = request.POST.get("address", profile.address)

        if request.FILES.get("profile_image"):
            profile.profile_image = request.FILES["profile_image"]

        profile.save()
        messages.success(request, "อัปเดตโปรไฟล์เรียบร้อยแล้ว")
        return redirect("profile_page")

    return redirect("profile_page")


def how_to_rent(request):
    return render(request, "dress/how_to_rent.html")


@login_required(login_url='login')
def back_office(request, store_id):
    store = get_object_or_404(Shop, id=store_id, owner=request.user)
    return render(request, 'dress/back_office.html', {'store': store})


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


# -------------------------
# API ภายในร้าน: เทมเพลตราคาเช่า / ค่าส่ง
# -------------------------
def _assert_store_owner(store: Shop, user):
    return (store.owner_id == getattr(user, "id", None)) or getattr(user, "is_superuser", False)


@login_required
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

    # ป้องกันชื่อซ้ำในร้านเดียวกัน
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


@login_required
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


# -------------------------
# เช่า: หน้าเช็คเอาต์
# -------------------------
def _parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

def _days_inclusive(a, b):
    if not a or not b:
        return 0
    return (b - a).days + 1

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

@login_required(login_url="login")
def rent_checkout(request, dress_id):
    dress = get_object_or_404(Dress, pk=dress_id)

    # --- รับค่าจากหน้า detail ---
    start_s = (request.GET.get("start_date") or request.GET.get("start") or "").strip()
    end_s   = (request.GET.get("end_date")   or request.GET.get("end")   or "").strip()
    days_s  = (request.GET.get("days") or "").strip()

    start_date = _parse_date(start_s)
    end_date   = _parse_date(end_s)
    total_days = int(days_s) if days_s.isdigit() else _days_inclusive(start_date, end_date)

    # --- ตารางแพ็ก ---
    pack_prices = []
    if getattr(dress, "price_template", None):
        for it in dress.price_template.items.order_by("day_count"):
            pack_prices.append({"days": it.day_count, "price": float(it.total_price)})
    else:
        daily = float(getattr(dress, "daily_price", 0) or 0)
        if daily > 0:
            for d in range(1, 8+1):
                pack_prices.append({"days": d, "price": daily * d})

    # --- ค่ามัดจำ & ค่าเช่า ---
    deposit = float(getattr(dress, "deposit", 0) or 0)
    rental_fee = 0.0
    if total_days > 0:
        match = next((p for p in pack_prices if int(p["days"]) == total_days), None)
        rental_fee = float(match["price"]) if match else float(getattr(dress, "daily_price", 0) or 0) * total_days

    # --- ค่าส่ง: เอาจากกฎของร้าน ถ้าไม่มี → ตั้งค่า default ---
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

    # ปริยาย: ออเดอร์ 'เช่าทันที' = 1 ชุด → ถ้า POST ค่อยคิดจริงก่อนบันทึก
    preview_qty = 1
    preview_shipping = _calc_shipping_from_tiers(shipping_tiers, preview_qty)

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

        # ส่งไว้เผื่ออยากแสดงค่าส่งตัวอย่างสำหรับ 1 ชุด
        "preview_shipping_fee": preview_shipping,
    }
    return render(request, "dress/rent_checkout.html", ctx)
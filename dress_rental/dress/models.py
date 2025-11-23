from decimal import Decimal
from datetime import date
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


# ============================================================
# Model: PlatformSettings
# ตั้งค่าระดับแพลตฟอร์ม เช่น อัตราค่าคอมมิชชั่นหลัก
# ============================================================
class PlatformSettings(models.Model):
    name = models.CharField(max_length=100, default="Default")
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.10"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("1.00")),
        ],
        help_text="อัตราค่าคอมมิชชั่นเริ่มต้นของแพลตฟอร์ม เช่น 0.10 = 10%",
    )
    commission_min_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="ค่าคอมขั้นต่ำต่อออเดอร์ (บาท)",
    )
    commission_vat_rate = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("1.00")),
        ],
        help_text="VAT บนค่าคอมฯ (ทศนิยม) เช่น 0.07 = 7%",
    )
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return f"Settings: {self.name} (active={self.is_active})"

    @classmethod
    def current(cls):
        """ดึง config แพลตฟอร์มที่ active ล่าสุด"""
        obj = cls.objects.filter(is_active=True).order_by("-updated_at", "-id").first()
        return obj


# ============================================================
# Model: WithdrawalRequest
# คำขอถอนเงินจากร้าน รอแอดมินตรวจสอบ/อนุมัติ
# ============================================================
class WithdrawalRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "รอดำเนินการ"),
        ("approved", "อนุมัติแล้ว"),
        ("rejected", "ปฏิเสธ"),
        ("paid", "โอนเงินแล้ว"),
    ]

    store = models.ForeignKey(
        "Shop",
        on_delete=models.CASCADE,
        related_name="withdraw_requests",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    note = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.store.name} ขอถอน {self.amount} ({self.status})"


# ============================================================
# Model: StoreTransaction
# บันทึกธุรกรรมระหว่างระบบกับร้าน (ยอดรวม / ค่าคอม / ยอดสุทธิ)
# ============================================================
class StoreTransaction(models.Model):
    store = models.ForeignKey("Shop", on_delete=models.CASCADE)
    order = models.ForeignKey(
        "RentalOrder",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    gross_amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.store.name} - {self.net_amount} ฿"


# ============================================================
# Model: Shop
# ร้านเช่าชุดในระบบ
# ============================================================
class Shop(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shops",
    )
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True)
    province = models.CharField(max_length=200, blank=True, null=True)
    shop_logo = models.ImageField(upload_to="img_shop_logos/", blank=True, null=True)
    fee = models.TextField(blank=True, null=True)  # ข้อความกติกา/โน้ต (ไม่ใช้คำนวณ)
    created_at = models.DateTimeField(auto_now_add=True)

    # จำนวนวันเช่าสูงสุดค่าเริ่มต้นระดับร้าน (สินค้า override ได้)
    max_rental_days = models.PositiveIntegerField(
        default=8,
        validators=[MinValueValidator(1)],
    )

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.name

    # คำนวณค่าส่งขาไปตามจำนวนชิ้นจากกติกาของร้าน
    def outbound_shipping_fee_for_qty(self, qty: int) -> Decimal:
        rule = getattr(self, "shipping_rule", None)  # reverse ของ OneToOne ShippingRule
        if not rule:
            return Decimal("0.00")
        b = rule.brackets.filter(min_qty__lte=qty, max_qty__gte=qty).first()
        if b:
            return Decimal(b.fee)
        if rule.clamp_to_max:
            top = rule.brackets.order_by("-max_qty").first()
            if top:
                return Decimal(top.fee)
        return Decimal("0.00")

    # ค่าคอมฯ ที่ใช้กับร้านนี้ (ถ้ามี ShopCommission จะ override ค่าดีฟอลต์)
    def commission_params(self):
        """
        ลำดับการใช้:
        1) ShopCommission (ถ้ามีและ enabled)
        2) PlatformSettings.current()
        3) ค่า fallback 10% / min 0 / vat 0
        """
        sc = getattr(self, "commission", None)  # reverse ของ OneToOne ShopCommission
        if sc and sc.enabled:
            return (sc.commission_rate, sc.commission_min_fee, sc.commission_vat_rate)

        ps = PlatformSettings.current()
        if ps:
            return (ps.commission_rate, ps.commission_min_fee, ps.commission_vat_rate)

        return (Decimal("0.10"), Decimal("0.00"), Decimal("0.00"))


# ============================================================
# Model: RentalOrder
# คำสั่งเช่าแบบง่าย ผูกกับผู้ใช้-ชุด-ร้าน
# (ใช้กับ Omise charge เบื้องต้น)
# ============================================================
class RentalOrder(models.Model):
    # ---- สถานะคำเช่า ตาม flow ใหม่ -----------------------
    STATUS_NEW            = "new"              # คำเช่าใหม่
    STATUS_WAITING_PAY    = "waiting_payment"  # รอชำระเงิน
    STATUS_PAID           = "paid"             # ชำระเงินสำเร็จ
    STATUS_PREPARING      = "preparing"        # กำลังเตรียมจัดส่ง
    STATUS_SHIPPING       = "shipping"         # จัดส่งเรียบร้อย
    STATUS_IN_RENTAL      = "in_rental"        # อยู่ระหว่างการเช่า
    STATUS_WAITING_RETURN = "waiting_return"   # รอคืนชุด
    STATUS_RETURNED       = "returned"         # คืนชุดแล้ว
    STATUS_DAMAGED        = "damaged"          # พบปัญหาชุดชำรุด
    STATUS_CANCELLED      = "cancelled"        # ออเดอร์ยกเลิก

    STATUS_CHOICES = [
        (STATUS_NEW,            "คำเช่าใหม่"),
        (STATUS_WAITING_PAY,    "รอชำระเงิน"),
        (STATUS_PAID,           "ชำระเงินสำเร็จ"),
        (STATUS_PREPARING,      "กำลังเตรียมจัดส่ง"),
        (STATUS_SHIPPING,       "จัดส่งเรียบร้อย"),
        (STATUS_IN_RENTAL,      "อยู่ระหว่างการเช่า"),
        (STATUS_WAITING_RETURN, "รอคืนชุด"),
        (STATUS_RETURNED,       "คืนชุดแล้ว"),
        (STATUS_DAMAGED,        "พบปัญหาชุดชำรุด"),
        (STATUS_CANCELLED,      "ออเดอร์ยกเลิก"),

        # ตัวเลือกเก่า (กันข้อมูลเดิม error / ใช้ transition ช่วงเปลี่ยนระบบ)
        ("pending",   "รอดำเนินการ (เดิม)"),
        ("completed", "เช่าเสร็จแล้ว (เดิม)"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rental_orders",
    )

    dress = models.ForeignKey(
        "Dress",
        on_delete=models.CASCADE,
        related_name="rental_orders",
    )

    rental_shop = models.ForeignKey(
        "Shop",
        on_delete=models.CASCADE,
        related_name="orders",
    )

    pickup_date = models.DateField()
    return_date = models.DateField()

    total_price = models.DecimalField(max_digits=8, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(
        max_length=30,              # ขยายจาก 20 → 30 ให้พอใส่ waiting_payment
        choices=STATUS_CHOICES,
        default=STATUS_NEW,         # เดิมคือ "pending"
    )

    omise_charge_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"ORD-{self.id} ({self.user})"



# ============================================================
# Model: ShopCommission
# ค่าคอมมิชชั่นเฉพาะร้าน (override จากค่า default แพลตฟอร์ม)
# ============================================================
class ShopCommission(models.Model):
    shop = models.OneToOneField(
        Shop,
        on_delete=models.CASCADE,
        related_name="commission",
    )
    enabled = models.BooleanField(default=False)
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.10"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("1.00")),
        ],
    )
    commission_min_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    commission_vat_rate = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("1.00")),
        ],
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Commission[{self.shop.name}] enabled={self.enabled}"


# ============================================================
# Model: Category
# หมวดหมู่ของชุด เช่น ชุดเดรส ชุดคาเฟ่ ฯลฯ
# ============================================================
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


# ============================================================
# Model: PriceTemplate / PriceTemplateItem
# เทมเพลตราคาแพ็กตามจำนวนวัน (ระดับร้าน)
# เช่น 1วัน=200, 2วัน=250, ... สูงสุด max_days
# ============================================================
class PriceTemplate(models.Model):
    store = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="price_templates",
    )
    name = models.CharField(max_length=100)
    max_days = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ("store", "name")
        constraints = [
            models.UniqueConstraint(
                fields=["store", "name"],
                name="uniq_price_template_store_name",
            ),
        ]

    def __str__(self):
        return f"{self.store.name} · {self.name}"


class PriceTemplateItem(models.Model):
    template = models.ForeignKey(
        PriceTemplate,
        on_delete=models.CASCADE,
        related_name="items",
    )
    day_count = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        ordering = ("day_count",)
        constraints = [
            models.UniqueConstraint(
                fields=["template", "day_count"],
                name="uniq_price_template_item_day",
            ),
        ]

    def clean(self):
        if self.template and self.day_count and self.template.max_days:
            if self.day_count > self.template.max_days:
                from django.core.exceptions import ValidationError

                raise ValidationError("จำนวนวันของรายการเกินค่า max_days ของเทมเพลต")

    def __str__(self):
        return f"{self.day_count} วัน = {self.total_price}"


# ============================================================
# Model: Dress
# รายการชุดที่ปล่อยเช่า
# ============================================================
class Dress(models.Model):
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="dresses",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    size = models.TextField(blank=True, null=True, verbose_name="ขนาด")

    # ราคา/วัน (fallback หากไม่ใช้ราคาแพ็ก)
    daily_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    # มัดจำต่อชิ้น
    deposit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="ค่ามัดจำ",
    )

    # fallback ค่าส่ง ถ้าร้านยังไม่ตั้ง ShippingRule
    shipping_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="ค่าจัดส่ง",
    )

    is_available = models.BooleanField(default=True, verbose_name="สถานะการเช่า")
    stock = models.PositiveIntegerField(
        default=1,
        verbose_name="จำนวนสินค้า",
        validators=[MinValueValidator(0)],
    )

    categories = models.ManyToManyField(Category, blank=True)
    image = models.ImageField(upload_to="dresses/", blank=True, null=True)

    # ใช้ราคาแพ็กของร้าน หรือ override รายชิ้น
    price_template = models.ForeignKey(
        PriceTemplate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products",
    )
    max_rental_days_override = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["shop", "name"])]

    def __str__(self):
        return self.name

    # ===== Helpers สำหรับคำนวณราคาแบบแพ็ก =====
    def allowed_max_days(self) -> int:
        if self.max_rental_days_override:
            return self.max_rental_days_override
        if self.price_template:
            return self.price_template.max_days
        return self.shop.max_rental_days

    def find_pack_price(self, days: int) -> (Decimal, str):
        """หาแพ็คเกจราคาตามจำนวนวัน"""
        ov = self.override_prices.filter(day_count=days).first()
        if ov:
            return Decimal(ov.total_price), "override"
        if self.price_template:
            item = self.price_template.items.filter(day_count=days).first()
            if item:
                return Decimal(item.total_price), "template"
        if self.daily_price and self.daily_price > 0:
            return Decimal(self.daily_price) * Decimal(days), "daily_fallback"
        raise ValueError("ยังไม่พบราคาที่ตั้งไว้สำหรับจำนวนวันนี้")

    @staticmethod
    def _days_inclusive(start_date: date, end_date: date) -> int:
        if end_date < start_date:
            raise ValueError("วันที่สิ้นสุดต้องไม่ก่อนวันเริ่ม")
        return (end_date - start_date).days + 1

    def quote(self, start_date: date, end_date: date, qty: int = 1, include_shipping=True):
        """
        คำนวณราคาโดยรวม: ค่าเช่ารวม + มัดจำรวม + ค่าส่งขาไป (ประมาณการ)
        การนับวัน: รวมวันเริ่มและสิ้นสุด
        """
        qty = int(qty or 1)
        d = self._days_inclusive(start_date, end_date)
        if d < 1 or d > self.allowed_max_days():
            raise ValueError(
                f"จำนวนวัน {d} เกินจากที่อนุญาต (สูงสุด {self.allowed_max_days()} วัน)"
            )

        pack_price, source = self.find_pack_price(d)  # ราคาแพ็ก/ชิ้น
        rent_total = pack_price * Decimal(qty)
        deposit_total = Decimal(self.deposit) * Decimal(qty)

        if include_shipping:
            shipping_est = self.shop.outbound_shipping_fee_for_qty(qty)
            if shipping_est == 0 and self.shipping_fee:
                shipping_est = Decimal(self.shipping_fee)
        else:
            shipping_est = Decimal("0.00")

        grand_est = rent_total + deposit_total + shipping_est
        return {
            "days": d,
            "pricing_source": source,
            "rent_total": rent_total,
            "deposit_total": deposit_total,
            "shipping_estimated": shipping_est,
            "grand_total_estimated": grand_est,
        }


# ============================================================
# Model: DressPriceOverride
# ราคาแพ็ก override รายชิ้น (หากไม่ใช้ template ของร้าน)
# ============================================================
class DressPriceOverride(models.Model):
    product = models.ForeignKey(
        Dress,
        on_delete=models.CASCADE,
        related_name="override_prices",
    )
    day_count = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        ordering = ("day_count",)
        constraints = [
            models.UniqueConstraint(
                fields=["product", "day_count"],
                name="uniq_dress_override_day",
            ),
        ]

    def __str__(self):
        return f"{self.product.name} · {self.day_count} วัน = {self.total_price}"


# ============================================================
# Model: DressImage
# รูปภาพเพิ่มเติมของชุด
# ============================================================
class DressImage(models.Model):
    dress = models.ForeignKey(
        Dress,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="dresses/more_images/")
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-uploaded_at",)


# ============================================================
# Model: Review
# รีวิวจากลูกค้า พร้อมคะแนนและรูปภาพ
# ============================================================
class Review(models.Model):
    dress = models.ForeignKey(
        Dress,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="review_images/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    shop_reply = models.TextField(blank=True, null=True)
    replied_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user.username} - {self.dress.name} ({self.rating}⭐)"


# ============================================================
# Model: Favorite
# รายการชุดโปรดของผู้ใช้แต่ละคน
# ============================================================
class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    dress = models.ForeignKey(Dress, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "dress")
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user.username} favorite {self.dress.name}"


# ============================================================
# Model: CartItem
# ตะกร้าสินค้า เก็บชุดที่ผู้ใช้กดเพิ่มไว้ก่อนชำระเงิน
# ============================================================
class CartItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    dress = models.ForeignKey(Dress, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-added_at",)

    def __str__(self):
        return f"{self.user.username} - {self.dress.name} ({self.quantity})"


# ============================================================
# Model: ShippingRule / ShippingBracket
# นโยบายค่าส่งขาไปแบบเป็นขั้น (ต่อร้าน)
# เช่น 1 ชิ้น=50, 2 ชิ้น=60, 3+ ชิ้น=65
# ============================================================
class ShippingRule(models.Model):
    store = models.OneToOneField(
        Shop,
        on_delete=models.CASCADE,
        related_name="shipping_rule",
    )
    clamp_to_max = models.BooleanField(
        default=True,
        help_text="ถ้าเกินช่วงบนให้ใช้ค่าสูงสุด",
    )

    def __str__(self):
        return f"Shipping · {self.store.name}"


class ShippingBracket(models.Model):
    rule = models.ForeignKey(
        ShippingRule,
        on_delete=models.CASCADE,
        related_name="brackets",
    )
    min_qty = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    max_qty = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        ordering = ("min_qty",)

    def clean(self):
        if self.max_qty < self.min_qty:
            from django.core.exceptions import ValidationError

            raise ValidationError("max_qty ต้องมากกว่าหรือเท่ากับ min_qty")

    def __str__(self):
        return f"{self.min_qty}-{self.max_qty} ชิ้น = {self.fee} บาท"


# ============================================================
# Model: Rental
# การเช่าจริง 1 เรคอร์ด = 1 ชุด (มีคำนวณค่าคอมฯ และยอดที่ต้องโอนให้ร้าน)
# ============================================================
class Rental(models.Model):
    class Status(models.TextChoices):
        CREATED = "CREATED", "สร้างแล้ว"
        PAID = "PAID", "ชำระเงินแล้ว"
        RETURNED = "RETURNED", "คืนชุดแล้ว"
        SETTLED = "SETTLED", "ปิดโอนให้ร้านแล้ว"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rentals",
    )
    dress = models.ForeignKey(
        Dress,
        on_delete=models.CASCADE,
        related_name="rentals",
    )
    start_date = models.DateField()
    end_date = models.DateField()

    # จำนวนวัน (รวมวันเริ่มและสิ้นสุด)
    days = models.PositiveIntegerField(default=1)

    # ยอดคำนวณตอนยืนยันเช่า
    rent_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    deposit_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    shipping_out = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    grand_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    # คอมมิชชั่นและยอดสุทธิที่ต้องโอนให้ร้าน
    commission_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    commission_vat = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    seller_payout = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CREATED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.dress.name} - {self.user.username}"

    # ---------- Helper ----------
    @staticmethod
    def _days_inclusive(start_date: date, end_date: date) -> int:
        if end_date < start_date:
            raise ValueError("วันที่สิ้นสุดต้องไม่ก่อนวันเริ่ม")
        return (end_date - start_date).days + 1

    def compute_totals(self):
        """
        คำนวณยอดต่าง ๆ จาก Dress.quote()
        และใช้เรตค่าคอมมิชชั่นที่แอดมินตั้งใน Shop/Platform
        """
        q = self.dress.quote(
            self.start_date,
            self.end_date,
            qty=1,
            include_shipping=True,
        )
        self.days = q["days"]
        self.rent_total = q["rent_total"]
        self.deposit_total = q["deposit_total"]
        self.shipping_out = q["shipping_estimated"]
        self.grand_total = q["grand_total_estimated"]

        # --- ค่าคอมฯ แอดมินตั้ง ---
        rate, min_fee, vat_rate = self.dress.shop.commission_params()

        commission = self.rent_total * rate
        if commission < min_fee:
            commission = min_fee
        commission_vat = commission * vat_rate

        self.commission_amount = commission.quantize(Decimal("0.01"))
        self.commission_vat = commission_vat.quantize(Decimal("0.01"))
        self.seller_payout = (
            self.rent_total
            + self.shipping_out
            - self.commission_amount
            - self.commission_vat
        ).quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        if not self.rent_total or not self.grand_total:
            self.compute_totals()
        super().save(*args, **kwargs)


# ============================================================
# Model: Notification
# การแจ้งเตือนต่าง ๆ ให้ผู้ใช้
# ============================================================
class Notification(models.Model):
    TYPE_CHOICES = [
        ("order", "คำสั่งเช่า"),
        ("payment", "การชำระเงิน"),
        ("reminder", "เตือนเวลา"),
        ("shop_message", "ข้อความจากร้าน"),
        ("system", "ระบบ"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=200)
    message = models.TextField()

    type = models.CharField(
        max_length=50,
        choices=TYPE_CHOICES,
        default="order",
    )

    related_order = models.ForeignKey(
        "RentalOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )

    sender_shop = models.ForeignKey(
        "Shop",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sent_notifications",
        help_text="ถ้าเป็นข้อความจากร้าน ระบุร้านที่ส่ง",
    )

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} -> {self.user}"


# ============================================================
# Model: Payment
# การชำระเงินผ่าน Omise (ผูกกับ charge_id)
# ============================================================
class Payment(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("expired", "Expired"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    dress_id = models.IntegerField(null=True, blank=True)

    charge_id = models.CharField(max_length=64, unique=True)

    # จำนวนเงินเป็น "สตางค์" (integer) ตามรูปแบบของ Omise
    amount = models.IntegerField(default=0)

    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default="pending",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["charge_id"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.charge_id} ({self.status})"


# ============================================================
# Model: UserProfile
# โปรไฟล์เพิ่มเติมของผู้ใช้
# ============================================================
class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    gender = models.CharField(max_length=10, blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    profile_image = models.ImageField(
        upload_to="profile_images/",
        blank=True,
        null=True,
    )

    def __str__(self):
        return self.user.username
    


# ============================================================
# Chat: General (Pre-Order) Member ↔ Shop
# แชททั่วไปสำหรับสอบถามก่อนเช่า (ไม่ผูกกับออเดอร์)
# ============================================================

class ShopChatThread(models.Model):
    """
    ห้องแชททั่วไประหว่าง ลูกค้า ↔ ร้าน
    ใช้สำหรับสอบถามข้อมูลก่อนตัดสินใจเช่า
    1 customer + 1 shop = 1 ห้องแชท
    """
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shop_chat_customer_threads'
    )
    shop = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shop_chat_shop_threads'
    )

    # ผูกห้องแชทกับชุดที่ลูกค้าถาม (optional)
    related_dress = models.ForeignKey(
        'Dress',                      # ใช้ชื่อโมเดลเป็นสตริง เลี่ยงปัญหา import
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='chat_threads'
    )

    created_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        # ถ้าลูกค้าคุยกับร้านเดิม ใช้ห้องเดิม (ไม่สนว่าเกี่ยวกับชุดไหน)
        unique_together = ('customer', 'shop')

    def __str__(self):
        return f"General chat {self.customer} ↔ {self.shop}"


class ShopChatMessage(models.Model):
    """
    ข้อความในห้องแชททั่วไป
    - รองรับทั้งข้อความอย่างเดียว หรือรูปอย่างเดียว หรือทั้งคู่
    """
    thread = models.ForeignKey(
        ShopChatThread,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shop_chat_sent_messages'
    )

    # ข้อความ ให้เว้นว่างได้ เพราะบางครั้งอาจส่งแต่รูป
    message = models.TextField(blank=True, default="")

    # ไฟล์รูปภาพที่แนบมากับข้อความ (optional)
    image = models.ImageField(
        upload_to='chat_images/',
        null=True,
        blank=True,
        help_text="ไฟล์ภาพที่แนบมากับข้อความแชท"
    )

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        base = self.message[:30] if self.message else "[image]"
        return f"{self.sender} : {base}"

    @property
    def has_image(self):
        return bool(self.image)


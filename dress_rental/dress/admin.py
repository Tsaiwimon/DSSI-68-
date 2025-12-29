from django.contrib import admin
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import Shop, Category, Dress

User = get_user_model()


@admin.action(description="อนุมัติร้านที่เลือก")
def approve_selected_shops(modeladmin, request, queryset):
    # อนุมัติแบบเลือกหลายรายการ
    queryset.update(
        status=Shop.STATUS_APPROVED,
        approved_by=request.user,
        approved_at=timezone.now(),
        reject_reason="",
    )


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "status", "approved_by", "approved_at", "created_at")
    list_filter = ("status",)
    actions = [approve_selected_shops]

    # กันแก้มั่ว ให้ระบบเป็นคนใส่
    readonly_fields = ("approved_by", "approved_at", "created_at")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # owner: ให้เลือกเฉพาะ user ที่ไม่ใช่ staff/superuser (กัน admin โผล่มา)
        if db_field.name == "owner":
            kwargs["queryset"] = User.objects.filter(is_staff=False, is_superuser=False)

        # approved_by: ให้เลือกเฉพาะ staff
        if db_field.name == "approved_by":
            kwargs["queryset"] = User.objects.filter(is_staff=True)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        """
        ถ้าเซ็ตสถานะเป็น approved:
        - ใส่ approved_by เป็นแอดมินที่กดบันทึก
        - ใส่ approved_at เป็นเวลาปัจจุบัน
        - ล้าง reject_reason
        """
        # สถานะเดิม (ตอนแก้ไข record เดิม)
        old_status = None
        if change:
            try:
                old_status = Shop.objects.get(pk=obj.pk).status
            except Shop.DoesNotExist:
                old_status = None

        super().save_model(request, obj, form, change)

        if obj.status == Shop.STATUS_APPROVED:
            need_set = (old_status != Shop.STATUS_APPROVED) or (obj.approved_by_id is None)
            if need_set:
                obj.approved_by = request.user
                if obj.approved_at is None:
                    obj.approved_at = timezone.now()
                obj.reject_reason = ""
                obj.save(update_fields=["approved_by", "approved_at", "reject_reason"])


admin.site.register(Category)
admin.site.register(Dress)

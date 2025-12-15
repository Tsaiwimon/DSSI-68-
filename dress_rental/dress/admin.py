from django.contrib import admin
from django.utils import timezone
from .models import Shop, Category, Dress


@admin.action(description="อนุมัติร้านที่เลือก")
def approve_selected_shops(modeladmin, request, queryset):
    queryset.update(
        status=Shop.STATUS_APPROVED,
        approved_by=request.user,
        approved_at=timezone.now(),
        reject_reason="",
    )


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "status", "created_at")
    list_filter = ("status",)
    actions = [approve_selected_shops]


admin.site.register(Category)
admin.site.register(Dress)

from django.conf import settings
from django.db import models
from django.utils import timezone

class DamageReport(models.Model):
    TYPE_DAMAGED = "damaged"
    TYPE_NOT_RETURNED = "not_returned"
    TYPE_CHOICES = [
        (TYPE_DAMAGED, "ชุดชำรุด"),
        (TYPE_NOT_RETURNED, "ไม่คืนชุด"),
    ]

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "รอตรวจสอบ"),
        (STATUS_APPROVED, "อนุมัติ"),
        (STATUS_REJECTED, "ปฏิเสธ"),
    ]

    shop = models.ForeignKey("dress.Shop", on_delete=models.CASCADE, related_name="damage_reports")
    order = models.ForeignKey("dress.Order", on_delete=models.CASCADE, related_name="damage_reports")  # ปรับ app/model ให้ตรง
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer_damage_reports")

    report_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.TextField(blank=True, default="")
    evidence_image = models.ImageField(upload_to="damage_reports/", null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    admin_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Order #{self.order_id} | {self.get_report_type_display()} | {self.get_status_display()}"

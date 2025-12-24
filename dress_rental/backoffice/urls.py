from django.urls import path
from . import views

app_name = "backoffice"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    # อนุมัติร้านค้า
    path("shops/pending/", views.shop_pending_list, name="shop_pending_list"),
    path("shops/<int:shop_id>/approve/", views.shop_approve, name="shop_approve"),
    path("shops/<int:shop_id>/reject/", views.shop_reject, name="shop_reject"),

    # จัดการผู้ใช้งาน
    path("users/", views.users_page, name="users"),
    path("users/<int:user_id>/suspend/", views.user_suspend, name="user_suspend"),
    path("users/<int:user_id>/activate/", views.user_activate, name="user_activate"),
    path("users/<int:user_id>/delete/", views.user_delete, name="user_delete"),

    # เมนูอื่น ๆ
    path("reports/", views.reports_page, name="reports"),
    path("bookings/", views.bookings_page, name="bookings"),
    path("reviews/", views.reviews_page, name="reviews"),
    path("reviews/<int:review_id>/reply/", views.review_reply, name="review_reply"),
    path("reviews/<int:review_id>/toggle-hidden/", views.review_toggle_hidden, name="review_toggle_hidden"),
    path("reviews/<int:review_id>/delete/", views.review_delete, name="review_delete"),
    path("settings/", views.settings_page, name="settings"),
    path("bookings/<int:order_id>/mark-returned/", views.booking_mark_returned, name="booking_mark_returned"),
]

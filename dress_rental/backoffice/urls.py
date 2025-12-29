from django.urls import path
from . import views

app_name = "backoffice"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path("shops/pending/", views.shop_pending_list, name="shop_pending_list"),
    path("shops/<int:shop_id>/approve/", views.shop_approve, name="shop_approve"),
    path("shops/<int:shop_id>/reject/", views.shop_reject, name="shop_reject"),

    path("users/", views.users_page, name="users"),
    path("users/<int:user_id>/suspend/", views.user_suspend, name="user_suspend"),
    path("users/<int:user_id>/activate/", views.user_activate, name="user_activate"),
    path("users/<int:user_id>/delete/", views.user_delete, name="user_delete"),

    # Reports
    path("reports/", views.reports_page, name="reports"),
    path("reports/<int:report_id>/", views.report_detail, name="report_detail"),
    path("reports/<int:report_id>/update/", views.report_update, name="report_update"),

    path("bookings/", views.bookings_page, name="bookings"),
    path("reviews/", views.reviews_page, name="reviews"),
    path("settings/", views.settings_page, name="settings"),
]

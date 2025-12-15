from django.urls import path
from . import views

app_name = "backoffice"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("shops/pending/", views.shop_pending_list, name="shop_pending_list"),
    path("shops/<int:shop_id>/approve/", views.shop_approve, name="shop_approve"),
    path("shops/<int:shop_id>/reject/", views.shop_reject, name="shop_reject"),
]

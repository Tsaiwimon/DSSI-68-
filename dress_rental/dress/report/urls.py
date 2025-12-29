from django.urls import path
from .views_store import create_report

urlpatterns = [
    path("my-store/<int:store_id>/orders/<int:order_id>/report/", create_report, name="store_create_report"),
]

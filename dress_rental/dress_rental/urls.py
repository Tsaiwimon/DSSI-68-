from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    # ใช้อันเดียวพอ และมี namespace ชัดเจน
    path("", include(("dress.urls", "dress"), namespace="dress")),


    path("backoffice/", include("backoffice.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

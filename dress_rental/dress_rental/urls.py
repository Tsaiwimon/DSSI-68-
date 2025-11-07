from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path("admin/", admin.site.urls),  # ✅ เส้นทางสมัคร/ล็อกอิน
    path("", include("dress.urls")),      
    path("", include(("dress.urls", "dress"), namespace="dress")),        
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    
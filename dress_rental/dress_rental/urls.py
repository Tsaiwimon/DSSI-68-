from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # front site
    path("", include(("dress.urls", "dress"), namespace="dress")),

    # backoffice (custom admin)
    path("backoffice/", include(("backoffice.urls", "backoffice"), namespace="backoffice")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

from django.shortcuts import get_object_or_404, render
from .models import Shop

def get_store_or_403(request, store_id):
    store = get_object_or_404(Shop, id=store_id)

    if store.owner != request.user:
        # ใช้เทมเพลต 403 ที่คุณทำไว้
        return render(request, "dress/403.html", status=403)

    return store

from django.urls import path
from . import views

app_name = "dress"

urlpatterns = [
    # Home
    path("", views.home, name="home"),

    # Auth
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    path("redirect/", views.login_redirect, name="login_redirect"),

    # Member
    path("member/", views.member_home, name="member_home"),

    # Store (เจ้าของร้าน)
    path("open-store/", views.open_store, name="open_store"),
    path("my-store/<int:store_id>/", views.my_store, name="my_store"),
    path("my-store/<int:store_id>/dresses/", views.store_dress, name="store_dress"),
    path("my-store/<int:store_id>/add-dress/", views.add_dress, name="add_dress"),
    path("my-store/<int:store_id>/edit-dress/<int:dress_id>/", views.edit_dress, name="edit_dress"),
    path("my-store/<int:store_id>/delete-dress/<int:dress_id>/", views.delete_dress, name="delete_dress"),
    path("my-store/<int:store_id>/toggle/<int:dress_id>/", views.toggle_availability, name="toggle_availability"),
    path("my-store/<int:store_id>/back-office/", views.back_office, name="back_office"),

    # หน้าร้านสาธารณะ
    path("store/<int:store_id>/", views.public_store, name="public_store"),

    # รายละเอียดชุด + เช็คเอาต์
    path("dress/<int:dress_id>/", views.dress_detail, name="dress_detail"),
    path("dress/<int:dress_id>/checkout/", views.rent_checkout, name="rent_checkout"),

    # Reviews
    path("dress/<int:dress_id>/reviews/", views.review_list, name="review_list"),
    path("dress/<int:dress_id>/reviews/create/", views.review_create, name="review_create"),
    path("dress/<int:dress_id>/reviews/<int:review_id>/edit/", views.review_edit, name="review_edit"),
    path("dress/<int:dress_id>/reviews/<int:review_id>/delete/", views.review_delete, name="review_delete"),

    # Favorites
    path("dress/<int:dress_id>/favorite/", views.add_to_favorite, name="add_to_favorite"),
    path("dress/<int:dress_id>/favorite/toggle/", views.toggle_favorite, name="toggle_favorite"),
    path("favorites/", views.favorite_list, name="favorite_list"),
    path("favorites/count/", views.favorite_count_api, name="favorite_count_api"),

    # Cart
    path("cart/", views.cart_view, name="cart_view"),
    path("cart/add/<int:dress_id>/", views.add_to_cart, name="add_to_cart"),
    path("cart/count/", views.cart_item_count, name="cart_item_count"),
    path("cart/remove_bulk/", views.remove_bulk, name="remove_bulk"),
    path("cart/move_to_favorite/", views.move_to_favorite, name="move_to_favorite"),
    path("cart/update_quantity/", views.update_quantity, name="update_quantity"),

    # Profile / Rentals
    path("rental-history/", views.rental_history_view, name="rental_history"),
    path("notifications/", views.notification_page, name="notification"),
    path("my-rentals/", views.rental_list_view, name="rental_list"),
    path("profile/", views.profile_page, name="profile_page"),
    path("profile/update/", views.update_profile, name="update_profile"),
    path("how-to-rent/", views.how_to_rent, name="how_to_rent"),

    # Price Template APIs (canonical ภายใต้ /stores/)
    path("stores/<int:store_id>/price-templates/create/", views.api_create_price_template, name="api_create_price_template"),
    path("stores/<int:store_id>/price-templates/<int:tpl_id>/detail/", views.api_get_price_template, name="api_get_price_template"),
    path("stores/<int:store_id>/price-templates/<int:tpl_id>/update/", views.api_update_price_template, name="api_update_price_template"),
    # alias ใช้ path เดิมในหน้า my-store โดย **ไม่ตั้ง name** เพื่อเลี่ยงชื่อซ้ำ
    path("my-store/<int:store_id>/price-templates/create/", views.api_create_price_template),

    # Shipping Rule APIs
    path("stores/<int:store_id>/shipping-rule/save/", views.api_save_shipping_rule, name="api_save_shipping_rule"),
    path("my-store/<int:store_id>/shipping-rule/save/", views.api_save_shipping_rule),


    path("dress/<int:dress_id>/payment/", views.rent_payment, name="rent_payment"),
    path("dress/<int:dress_id>/payment/create-charge/", views.create_promptpay_charge, name="create_promptpay_charge"),
    path("dress/<int:dress_id>/success/",  views.rent_success,  name="rent_success"),


    # Webhook (ตั้งใน Omise Dashboard ให้ยิงมาที่นี่)
    path("omise/webhook/", views.omise_webhook, name="omise_webhook"),
]

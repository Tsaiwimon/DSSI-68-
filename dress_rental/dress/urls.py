from django.urls import path, reverse_lazy
from . import views
from django.contrib.auth import views as auth_views



app_name = "dress"

urlpatterns = [
    # Home
    path("", views.home, name="home"),

    # Auth
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    path("redirect/", views.login_redirect, name="login_redirect"),

    path("password-reset/",
         auth_views.PasswordResetView.as_view(
             template_name="dress/password_reset.html",
             success_url=reverse_lazy("dress:password_reset_done"),
         ),
         name="password_reset"),

    path("password-reset/done/",
         auth_views.PasswordResetDoneView.as_view(
             template_name="dress/password_reset_done.html",
         ),
         name="password_reset_done"),

    path("reset/<uidb64>/<token>/",
         auth_views.PasswordResetConfirmView.as_view(
             template_name="dress/password_reset_confirm.html",
             success_url=reverse_lazy("dress:password_reset_complete"),
         ),
         name="password_reset_confirm"),

    path("reset/done/",
         auth_views.PasswordResetCompleteView.as_view(
             template_name="dress/password_reset_complete.html",
         ),
         name="password_reset_complete"),



    # Member
    path("member/", views.member_home, name="member_home"),

    # Store (เจ้าของร้าน)
    path("open-store/", views.open_store, name="open_store"),
    path("my-store/<int:store_id>/", views.my_store, name="my_store"),
    path("my-store/<int:store_id>/dresses/", views.store_dress, name="store_dress"),
    path("my-store/<int:store_id>/dresses/archive/",views.store_dress_archive,name="store_dress_archive",),
    path("my-store/<int:store_id>/add-dress/", views.add_dress, name="add_dress"),
    path("my-store/<int:store_id>/edit-dress/<int:dress_id>/", views.edit_dress, name="edit_dress"),
    path("my-store/<int:store_id>/delete-dress/<int:dress_id>/", views.delete_dress, name="delete_dress"),
    path("my-store/<int:store_id>/toggle/<int:dress_id>/", views.toggle_availability, name="toggle_availability"),
    # Chat กับลูกค้า
    path('chat/shop/<int:shop_id>/', views.shop_chat_view, name='shop_chat'),
    path('chat/shop/<int:shop_id>/send/', views.shop_chat_send_message, name='shop_chat_send'),
    path('chat/shop/<int:shop_id>/messages/', views.shop_chat_messages_api, name='shop_chat_messages'),
    #แชทของร้าน (หลังร้าน)
    path('shop/inbox/', views.shop_chat_inbox, name='shop_chat_inbox'),
    path('shop/inbox/thread/<int:thread_id>/', views.shop_chat_thread_view, name='shop_chat_thread'),
    path('shop/inbox/thread/<int:thread_id>/send/', views.shop_chat_thread_send, name='shop_chat_thread_send'),
    path('shop/inbox/thread/<int:thread_id>/messages/', views.shop_chat_thread_messages, name='shop_chat_thread_messages'),

    path('my-store/<int:store_id>/settings/', views.store_settings, name='store_settings'),

    path("my-store/<int:store_id>/profile/", views.store_profile, name="store_profile"),

    path("my-store/<int:store_id>/back-office/", views.back_office, name="back_office"),



path(
    "my-store/<int:store_id>/back-office/finance/",
    views.back_office_finance,
    name="back_office_finance",
),
path(
    "my-store/<int:store_id>/back-office/stats/",
    views.back_office_stats,
    name="back_office_stats",
),

path(
    "my-store/<int:store_id>/orders/<int:order_id>/update-status/",
    views.back_office_update_order_status,
    name="back_office_update_order_status",
),

# ================================
# รายการคำสั่งเช่าตามสถานะ (หลังร้าน)
# ================================
path(
    "my-store/<int:store_id>/orders/new/",
    views.back_office_orders_new,
    name="back_office_orders_new",
),

path(
    "my-store/<int:store_id>/orders/pending-payment/",
    views.back_office_orders_pending_payment,
    name="back_office_orders_pending_payment",
),

path(
    "my-store/<int:store_id>/orders/paid/",
    views.back_office_orders_paid,
    name="back_office_orders_paid",
),

path(
    "my-store/<int:store_id>/orders/preparing/",
    views.back_office_orders_preparing,
    name="back_office_orders_preparing",
),

path(
    "my-store/<int:store_id>/orders/shipping/",
    views.back_office_orders_shipping,
    name="back_office_orders_shipping",
),

path(
    "my-store/<int:store_id>/orders/renting/",
    views.back_office_orders_renting,
    name="back_office_orders_renting",
),

path(
    "my-store/<int:store_id>/orders/waiting-return/",
    views.back_office_orders_waiting_return,
    name="back_office_orders_waiting_return",
),

path(
    "my-store/<int:store_id>/orders/returned/",
    views.back_office_orders_returned,
    name="back_office_orders_returned",
),

path(
    "my-store/<int:store_id>/orders/damaged/",
    views.back_office_orders_damaged,
    name="back_office_orders_damaged",
),

path(
    "my-store/<int:store_id>/orders/completed/",
    views.back_office_orders_completed,
    name="back_office_orders_completed",
),

path(
    "my-store/<int:store_id>/orders/cancelled/",
    views.back_office_orders_cancelled,
    name="back_office_orders_cancelled",
),

path(
    "my-store/<int:store_id>/reviews/",
    views.back_office_reviews,
    name="back_office_reviews",
),

    
# ย้ายชุดเข้า/ออกจากคลัง (archive/unarchive)
path(
    "my-store/<int:store_id>/dress/<int:dress_id>/archive/",
    views.archive_dress,
    name="archive_dress",
),
path(
    "my-store/<int:store_id>/dress/<int:dress_id>/unarchive/",
    views.unarchive_dress,
    name="unarchive_dress",
),




# toggle เปิด/ปิดให้เช่า (มุมมองร้าน)
    path(
        "my-store/<int:store_id>/store/dress/<int:dress_id>/toggle/",
        views.toggle_dress_availability,
        name="toggle_dress_availability",
    ),



  

    #การแจ้งเตือน
    path("notifications/", views.notification_page, name="notifications"),
    path("orders/<int:order_id>/send-message/", views.send_shop_message, name="send_shop_message"),
    

    # ฝั่งลูกค้า (สาธารณะ)
    path("store/<int:store_id>/", views.public_store, name="public_store"),

    # ฝั่งร้าน (เจ้าของร้าน)
    path("my-store/<int:store_id>/store/", views.store_page, name="store_store"),
    

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
    path("rental/<int:order_id>/cancel/", views.cancel_rental, name="cancel_rental"),
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

    # การชำระเงิน (Payment)
    path("dress/<int:dress_id>/payment/", views.rent_payment, name="rent_payment"),
    path("dress/<int:dress_id>/payment/create-charge/", views.create_promptpay_charge, name="create_promptpay_charge"),
    path("dress/<int:dress_id>/success/",  views.rent_success,  name="rent_success"),


    # Webhook (ตั้งใน Omise Dashboard ให้ยิงมาที่นี่)
    path("omise/webhook/", views.omise_webhook, name="omise_webhook"),
    # ตรวจสอบสถานะการชำระเงิน (Payment Status API)
    path("payments/status/", views.payment_status_api, name="payment_status_api"),

path(
    "dress/<int:dress_id>/review/",
    views.review_edit,          
    name="review_form",         
),

    # Cart Checkout
    path("checkout/", views.cart_checkout, name="cart_checkout"),
    path("checkout/confirm/", views.cart_checkout_confirm, name="checkout_confirm"),
    path("checkout/pay/", views.cart_payment_start, name="cart_payment_start"),
    path("payment/order/<int:order_id>/", views.payment_page_by_order, name="payment_by_order"),

    path("payment/order/<int:order_id>/paid-test/", views.payment_mark_paid_test, name="payment_mark_paid_test"),
    path("payment/success/<int:order_id>/", views.payment_success, name="payment_success"),


    path("orders/<int:order_id>/", views.order_detail, name="order_detail"),



    path("shop/pending/", views.shop_pending_notice, name="shop_pending_notice"),


    
]


handler403 = "dress.views.handler403"

from django.urls import path
from . import views

urlpatterns = [
    # ══════════ XARIDOR SAYTI ══════════
    path('', views.marketplace, name='marketplace'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('home/', views.role_home, name='role_home'),

    # Auth (faqat xaridorlar)
    path('register/', views.register, name='register'),
    path('login/', views.BuyerLoginView.as_view(), name='login'),
    path('logout/', views.BuyerLogoutView.as_view(), name='logout'),

    # Profil
    path('profile/', views.profile, name='profile'),
    path('profile/buyer/', views.buyer_profile, name='buyer_profile'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('notification/read/<int:pk>/', views.mark_notification_read, name='mark_notification_read'),

    # Savat
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:pk>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update/<int:item_id>/', views.update_cart, name='update_cart'),

    # Buyurtmalar
    path('checkout/', views.checkout, name='checkout'),
    path('orders/', views.orders, name='orders'),
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('order/<int:order_id>/cancel/', views.cancel_order, name='cancel_order'),
    path('order/item/<int:item_id>/cancel/', views.cancel_order_item, name='cancel_order_item'),
    path('order/confirm/<int:order_id>/<int:store_id>/', views.confirm_store_receipt, name='confirm_store_receipt'),

    # Sharhlar
    path('product/<int:pk>/review/', views.add_review, name='add_review'),

    # ══════════ SOTUVCHI PORTALI  (/seller/) ══════════
    path('seller/login/', views.SellerLoginView.as_view(), name='seller_login'),
    path('seller/register/', views.seller_register, name='seller_register'),
    path('seller/logout/', views.SellerLogoutView.as_view(), name='seller_logout'),
    path('seller/', views.seller_dashboard, name='seller_dashboard'),
    path('seller/create-store/', views.create_store, name='create_store'),
    path('seller/profile/', views.seller_profile, name='seller_profile'),
    path('seller/products/add/', views.add_product, name='add_product'),
    path('seller/products/<int:pk>/edit/', views.edit_product, name='edit_product'),
    path('seller/products/<int:pk>/delete/', views.delete_product, name='delete_product'),
    path('seller/orders/', views.seller_orders, name='seller_orders'),
    path('seller/item/update/<int:item_id>/', views.update_order_item_status, name='update_order_item_status'),
    path('seller/reviews/', views.seller_reviews, name='seller_reviews'),
    path('seller/review/reply/<int:review_id>/', views.add_review_reply, name='add_review_reply'),
    path('seller/statistics/', views.seller_statistics, name='seller_statistics'),
    path('seller/notifications/', views.notifications_view, name='seller_notifications'),

    # ══════════ ADMIN PORTALI  (/panel/) ══════════
    path('panel/login/', views.AdminLoginView.as_view(), name='admin_login'),
    path('panel/logout/', views.AdminLogoutView.as_view(), name='admin_logout'),
    path('panel/', views.admin_dashboard, name='admin_dashboard'),
    path('panel/notifications/', views.notifications_view, name='admin_notifications'),
    path('panel/toggle-top/<int:product_id>/', views.admin_toggle_top, name='admin_toggle_top'),
    path('panel/store-status/<int:store_id>/<str:status>/', views.admin_store_status, name='admin_store_status'),
    path('panel/m/<str:model_name>/', views.admin_model_list, name='admin_model_list'),
    path('panel/m/<str:model_name>/add/', views.admin_model_edit, name='admin_model_add'),
    path('panel/m/<str:model_name>/edit/<int:pk>/', views.admin_model_edit, name='admin_model_edit'),
    path('panel/m/<str:model_name>/delete/<int:pk>/', views.admin_model_delete, name='admin_model_delete'),

    # ══════════ Anora AI (hamma rol uchun) ══════════
    path('api/ai/chat/', views.ai_chat, name='ai_chat'),
    path('api/ai/project/estimate/', views.ai_project_estimate, name='ai_project_estimate'),
    path('api/ai/project/add-to-cart/', views.ai_project_add_cart, name='ai_project_add_cart'),
]

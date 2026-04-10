from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # ── Marketplace ──
    path('', views.marketplace, name='marketplace'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),

    # ── Auth ──
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(
        template_name='main/login.html', redirect_authenticated_user=True
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # ── Profile ──
    path('profile/', views.profile, name='profile'),
    path('profile/buyer/', views.buyer_profile, name='buyer_profile'),
    path('profile/seller/', views.seller_profile, name='seller_profile'),

    # ── Seller ──
    path('dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('create-store/', views.create_store, name='create_store'),
    path('add-product/', views.add_product, name='add_product'),
    path('seller/orders/', views.seller_orders, name='seller_orders'),
    path('seller/item/update/<int:item_id>/', views.update_order_item_status, name='update_order_item_status'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('notification/read/<int:pk>/', views.mark_notification_read, name='mark_notification_read'),

    # ── Cart ──
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:pk>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update/<int:item_id>/', views.update_cart, name='update_cart'),

    # ── Checkout & Orders ──
    path('checkout/', views.checkout, name='checkout'),
    path('orders/', views.orders, name='orders'),
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),

    # ── Reviews ──
    path('product/<int:pk>/review/', views.add_review, name='add_review'),
    path('review/reply/<int:review_id>/', views.add_review_reply, name='add_review_reply'),
    path('seller/reviews/', views.seller_reviews, name='seller_reviews'),
    path('seller/statistics/', views.seller_statistics, name='seller_statistics'),
    # ── Admin Dashboard ──
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/toggle-top/<int:product_id>/', views.admin_toggle_top, name='admin_toggle_top'),
    path('admin-dashboard/store-status/<int:store_id>/<str:status>/', views.admin_store_status, name='admin_store_status'),
    path('admin-dashboard/m/<str:model_name>/', views.admin_model_list, name='admin_model_list'),
    path('admin-dashboard/m/<str:model_name>/add/', views.admin_model_edit, name='admin_model_add'),
    path('admin-dashboard/m/<str:model_name>/edit/<int:pk>/', views.admin_model_edit, name='admin_model_edit'),
    path('admin-dashboard/m/<str:model_name>/delete/<int:pk>/', views.admin_model_delete, name='admin_model_delete'),
    path('order/confirm/<int:order_id>/<int:store_id>/', views.confirm_store_receipt, name='confirm_store_receipt'),
]

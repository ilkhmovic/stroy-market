"""Portallarni bir-biridan ajratish.

1. PortalHostMiddleware (ixtiyoriy): SELLER_HOST / ADMIN_HOST berilsa (masalan
   seller.example.uz, admin.example.uz) o'sha domenga kirgan odam to'g'ridan-to'g'ri
   sotuvchi / admin portalini ko'radi (Uzum Market'dagi seller.uzum.uz kabi).
2. RoleSeparationMiddleware: sotuvchi va admin xaridor sahifalariga
   (bozor, savat, buyurtmalar...) kira olmaydi, o'z paneliga qaytariladi.
"""
from django.conf import settings
from django.shortcuts import redirect
from django.urls import resolve, Resolver404

from .roles import get_role, home_url, SELLER, ADMIN

BUYER_ONLY_URL_NAMES = {
    'marketplace', 'product_detail', 'cart', 'add_to_cart', 'remove_from_cart',
    'update_cart', 'checkout', 'orders', 'order_detail', 'cancel_order',
    'cancel_order_item', 'confirm_store_receipt', 'add_review', 'buyer_profile',
    'notifications',
}

# Domen rejimida prefiks qo'shilmaydigan yo'llar
_SHARED_PREFIXES = ('/static/', '/media/', '/i18n/', '/api/ai/', '/notification/read/')


class PortalHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        seller_host = getattr(settings, 'SELLER_HOST', '')
        admin_host = getattr(settings, 'ADMIN_HOST', '')
        if seller_host or admin_host:
            host = request.get_host().split(':')[0].lower()
            prefix = None
            if seller_host and host == seller_host.lower():
                prefix = '/seller'
            elif admin_host and host == admin_host.lower():
                prefix = '/panel'
            if prefix:
                path = request.path_info
                already = path == prefix or path.startswith(prefix + '/')
                if not already and not path.startswith(_SHARED_PREFIXES):
                    request.path_info = prefix + path
        return self.get_response(request)


class RoleSeparationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            role = get_role(user)
            if role in (SELLER, ADMIN):
                try:
                    match = resolve(request.path_info)
                except Resolver404:
                    match = None
                if match and match.url_name in BUYER_ONLY_URL_NAMES:
                    return redirect(home_url(user))
        return self.get_response(request)

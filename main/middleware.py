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

from .hosts import host_url, portal_of, routing_enabled
from .roles import get_role, home_url, SELLER, ADMIN

BUYER_ONLY_URL_NAMES = {
    'marketplace', 'product_detail', 'cart', 'add_to_cart', 'remove_from_cart',
    'update_cart', 'checkout', 'orders', 'order_detail', 'cancel_order',
    'cancel_order_item', 'confirm_store_receipt', 'add_review', 'buyer_profile',
    'notifications',
}

def _shared_prefixes():
    """Domen rejimida portal prefiksi QO'SHILMAYDIGAN yo'llar (hamma domenda bir xil ishlaydi)."""
    return ('/static/', '/media/', '/i18n/', '/api/ai/', '/notification/read/',
            '/accounts/', '/p/', '/home/', '/' + settings.ADMIN_URL)


class PortalHostMiddleware:
    """seller.<domen> -> /seller/..., admin.<domen> -> /panel/... Asosiy domendagi /seller va /panel
    yo'llari tegishli subdomenga yo'naltiriladi. Javobga X-Portal sarlavhasi qo'shiladi (diagnostika uchun)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not routing_enabled():
            return self.get_response(request)
        portal = portal_of(request)
        request.portal = portal
        path = request.path_info
        shared = path.startswith(_shared_prefixes())
        prefix = {'seller': '/seller', 'admin': '/panel'}.get(portal)
        if prefix:
            if not shared and not (path == prefix or path.startswith(prefix + '/')):
                request.path_info = prefix + path
        elif request.method in ('GET', 'HEAD') and not shared:
            for pfx, target in (('/seller', settings.SELLER_HOST), ('/panel', settings.ADMIN_HOST)):
                if target and (path == pfx or path.startswith(pfx + '/')):
                    url = host_url(request, target, path[len(pfx):] or '/')
                    qs = request.META.get('QUERY_STRING')
                    return redirect(url + ('?' + qs if qs else ''))
        response = self.get_response(request)
        response['X-Portal'] = portal
        return response


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

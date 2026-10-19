"""Rollar: xaridor (asosiy sayt), sotuvchi (/seller/ portali), admin (/panel/ portali).

Har bir rol o'z portaliga, o'z kirish sahifasiga va o'z dizayniga ega.
"""
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext

BUYER, SELLER, ADMIN = 'buyer', 'seller', 'admin'

LOGIN_URL_NAME = {BUYER: 'login', SELLER: 'seller_login', ADMIN: 'admin_login'}


def get_role(user):
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return ADMIN
    if user.is_seller:
        return SELLER
    return BUYER


def home_url(user):
    """Foydalanuvchi o'z roliga mos bosh sahifasi."""
    role = get_role(user)
    if role == ADMIN:
        return reverse('admin_dashboard')
    if role == SELLER:
        return reverse('seller_dashboard')
    return reverse('marketplace')


def role_required(role):
    """Faqat berilgan rol kira oladi.

    - Kirmagan foydalanuvchi shu rolning KIRISH sahifasiga yuboriladi.
    - Admin paneliga boshqa rol kirsa 404 (panel borligi ham sezilmaydi).
    - Sotuvchi/xaridor boshqa portalga kirsa o'z bosh sahifasiga qaytariladi.
    """
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path(), reverse(LOGIN_URL_NAME[role]))
            if get_role(request.user) != role:
                if role == ADMIN:
                    raise Http404
                messages.error(request, gettext("Bu sahifa sizning rolingiz uchun emas."))
                return redirect(home_url(request.user))
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


buyer_required = role_required(BUYER)
seller_required = role_required(SELLER)
admin_required = role_required(ADMIN)


def role_context(request):
    """Shablonlar uchun: `user_role` va umumiy sahifalar uchun `base_template`."""
    role = get_role(request.user)
    base = {
        SELLER: 'main/seller/seller_base.html',
        ADMIN: 'main/admin/admin_base.html',
    }.get(role, 'main/base.html')
    return {'user_role': role, 'base_template': base, 'ADMIN_URL': settings.ADMIN_URL}

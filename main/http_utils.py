"""Xavfsiz redirect va so'rov yordamchilari."""
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme


def safe_redirect(request, default):
    """HTTP_REFERER faqat shu hostga tegishli bo'lsa yo'naltiradi."""
    referer = request.META.get('HTTP_REFERER')
    if referer and url_has_allowed_host_and_scheme(
        referer,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(referer)
    return redirect(default)


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or 'unknown'

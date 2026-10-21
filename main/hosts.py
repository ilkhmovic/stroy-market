"""Subdomenli portallar (matbaza.uz, seller.matbaza.uz, admin.matbaza.uz) uchun yordamchilar."""
from django.conf import settings


def routing_enabled():
    return bool(settings.SELLER_HOST or settings.ADMIN_HOST)


def portal_of(request):
    host = request.get_host().split(':')[0].lower()
    if settings.SELLER_HOST and host == settings.SELLER_HOST.lower():
        return 'seller'
    if settings.ADMIN_HOST and host == settings.ADMIN_HOST.lower():
        return 'admin'
    return 'buyer'


def host_url(request, host, path='/'):
    port = request.get_port()
    suffix = '' if port in ('80', '443', '') else ':%s' % port
    return '%s://%s%s%s' % (request.scheme, host, suffix, path)

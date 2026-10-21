from django.conf import settings

from .models import Page


def site_info(request):
    from django.urls import reverse
    from .hosts import host_url, routing_enabled
    on = routing_enabled()
    return {
        'seller_login_url': host_url(request, settings.SELLER_HOST, '/login/') if on and settings.SELLER_HOST else reverse('seller_login'),
        'main_site_url': host_url(request, settings.MAIN_HOST, '/') if on and settings.MAIN_HOST else '',
        'portal': getattr(request, 'portal', 'buyer'),
        'support_phone': getattr(settings, 'SUPPORT_PHONE', ''),
        'support_email': getattr(settings, 'SUPPORT_EMAIL', ''),
        'footer_pages': list(Page.objects.filter(is_published=True)),
    }

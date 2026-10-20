from django.conf import settings

from .models import Page


def site_info(request):
    return {
        'support_phone': getattr(settings, 'SUPPORT_PHONE', ''),
        'support_email': getattr(settings, 'SUPPORT_EMAIL', ''),
        'footer_pages': list(Page.objects.filter(is_published=True)),
    }

from django.apps import AppConfig
from django.db.models.signals import post_migrate


def set_site_domain(sender, **kwargs):
    """Email tasdiqlash/parol tiklash havolalari to'g'ri domenga (example.com ga emas) ketishi uchun."""
    from django.conf import settings
    domain = getattr(settings, 'SITE_DOMAIN', '')
    if not domain or sender.name != 'main':
        return
    try:
        from django.contrib.sites.models import Site
        Site.objects.update_or_create(pk=settings.SITE_ID, defaults={'domain': domain, 'name': 'ArzonMaterial'})
    except Exception:       # sites jadvali hali yo'q bo'lsa e'tiborsiz qoldiriladi
        pass


class MainConfig(AppConfig):
    name = 'main'

    def ready(self):
        post_migrate.connect(set_site_domain, sender=self)

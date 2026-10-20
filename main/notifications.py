"""Bildirishnomalar: matn kodi va parametrlari saqlanadi, ko'rsatishda tilga qarab tarjima qilinadi."""
from django.utils.translation import gettext, override

from .models import Notification


def uz(lazy_text):
    """Lazy matnning o'zbekcha (manba) ko'rinishi: parametr sifatida saqlash uchun."""
    with override('uz'):
        return str(lazy_text)


def notify(user=None, msgid='', params=None, target_url=None, user_id=None):
    params = params or {}
    kwargs = {'user_id': user_id} if user_id is not None else {'user': user}
    return Notification.objects.create(
        message=gettext(msgid) % params if params else gettext(msgid),
        code=msgid, params=params, target_url=target_url, **kwargs
    )

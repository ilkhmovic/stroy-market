"""Nasiya arizalarini menejerga yetkazish.

Ikki kanal bor:
1. Sayt ichidagi bildirishnoma, barcha superuser/staff foydalanuvchilarga (doim ishlaydi).
2. Telegram (ixtiyoriy), agar TELEGRAM_BOT_TOKEN va TELEGRAM_MANAGER_CHAT_ID berilgan bo'lsa.

Xatolik (masalan Telegram ishlamasa) buyurtma jarayonini to'xtatmaydi.
"""
import logging

import requests
from django.conf import settings
from django.db.models import Q

from .models import Notification, User

logger = logging.getLogger(__name__)


def _managers():
    return User.objects.filter(is_active=True).filter(Q(is_superuser=True) | Q(is_staff=True))


def _format_message(application):
    order = application.order
    lines = [
        f"Yangi NASIYA arizasi (buyurtma #{order.pk})",
        f"Ism: {application.full_name}",
        f"Telefon: {application.phone}",
        f"Muddat: {application.get_term_months_display()}",
        f"Jami summa: {order.get_total_price():,.0f} so'm".replace(',', ' '),
        f"Taxminiy oylik: {application.monthly_payment:,.0f} so'm".replace(',', ' '),
    ]
    if application.monthly_income:
        lines.append(f"Oylik daromad: {application.monthly_income:,.0f} so'm".replace(',', ' '))
    if application.workplace:
        lines.append(f"Ish joyi: {application.workplace}")
    lines.append("Mahsulotlar:")
    for item in order.items.all():
        lines.append(f"  - {item.product_name} x{item.quantity}")
    lines.append(f"Manzil: {order.address}")
    return "\n".join(lines)


def _send_telegram(text):
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    chat_id = getattr(settings, 'TELEGRAM_MANAGER_CHAT_ID', '')
    if not token or not chat_id:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={'chat_id': chat_id, 'text': text},  # parse_mode yo'q: oddiy matn
            timeout=3,
        )
        resp.raise_for_status()
        return True
    except Exception:
        # Tokenni logga chiqarmaslik uchun faqat xabar turi yoziladi
        logger.exception("Nasiya: Telegramga yuborib bo'lmadi")
        return False


def notify_managers(application):
    """Arizani menejerlarga yuboradi. Telegram yuborilganini qaytaradi (True/False)."""
    order = application.order
    message = (
        f"Yangi nasiya arizasi! Buyurtma #{order.pk}, {application.full_name}, "
        f"{application.phone}, {application.get_term_months_display()}."
    )
    admin_prefix = getattr(settings, 'ADMIN_URL', 'admin/').strip('/')
    target = f"/{admin_prefix}/main/nasiyaapplication/{application.pk}/change/"
    Notification.objects.bulk_create([
        Notification(user=m, message=message, target_url=target) for m in _managers()
    ])
    return _send_telegram(_format_message(application))

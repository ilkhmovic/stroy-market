"""Anora so'rovlarini cheklash va suhbat tarixini tozalash."""
from django.core.cache import cache

from .http_utils import client_ip

AUTH_LIMIT = 10
GUEST_LIMIT = 3
WINDOW_SECONDS = 60
HISTORY_MAX = 10
TEXT_MAX = 1000
ALLOWED_ROLES = frozenset({'user', 'assistant'})


def sanitize_history(raw):
    if not isinstance(raw, list):
        return []
    cleaned = []
    for msg in raw:
        if not isinstance(msg, dict):
            continue
        role = msg.get('role')
        if role == 'model':
            role = 'assistant'
        if role not in ALLOWED_ROLES:
            continue
        text = msg.get('text', '')
        if not isinstance(text, str):
            continue
        text = text.strip()[:TEXT_MAX]
        if not text:
            continue
        cleaned.append({'role': role, 'text': text})
    return cleaned[-HISTORY_MAX:]


def rate_limited(request):
    """Limitga yetgan bo'lsa True. Hisoblagichni oshiradi."""
    if request.user.is_authenticated:
        key = f'anora_rl_u_{request.user.pk}'
        limit = AUTH_LIMIT
    else:
        key = f'anora_rl_ip_{client_ip(request)}'
        limit = GUEST_LIMIT
    count = cache.get(key, 0)
    if count >= limit:
        return True
    cache.set(key, count + 1, WINDOW_SECONDS)
    return False

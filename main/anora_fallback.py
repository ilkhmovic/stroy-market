"""Anora (Gemini) javob bera olmaganda, admin yozgan javoblardan mosini topadi."""
from .models import AnoraFallback


def find_fallback(message, lang='uz'):
    text = (message or '').lower()
    best, best_hits = None, 0
    for item in AnoraFallback.objects.filter(is_active=True):
        words = [w.strip().lower() for w in item.keywords.replace('\n', ',').split(',') if w.strip()]
        hits = sum(1 for w in words if w in text)
        if hits > best_hits:
            best, best_hits = item, hits
    return best.answer_for(lang) if best else None

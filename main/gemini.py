"""Gemini chaqiruvlari uchun umumiy yordamchi: vaqt chegarasi, "thinking" sozlamasi, zaxira modellar.

Gemini 3 modellari standart holatda uzoq "o'ylaydi" (thinking_level=medium/high): bu javobni sekinlashtiradi
va max_output_tokens ichidan joy olib, JSON ni kesib tashlashi mumkin. Shu sababli thinking pasaytiriladi.
Gemini 3 da thinking_level, Gemini 2.5 da thinking_budget ishlatiladi (aralashtirib bo'lmaydi).
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def thinking_config(model, level='low'):
    from google.genai import types
    name = (model or '').lower()
    if name.startswith('gemini-3'):
        return types.ThinkingConfig(thinking_level=types.ThinkingLevel[level.upper()])
    if name.startswith('gemini-2.5') and 'pro' not in name:
        return types.ThinkingConfig(thinking_budget=0)
    return None


def call(model, contents, config, timeout=45, level='low'):
    """Bitta model bilan chaqiruv (vaqt chegarasi va thinking sozlamasi bilan)."""
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=settings.GEMINI_API_KEY, http_options=types.HttpOptions(timeout=int(timeout * 1000)))
    cfg = dict(config)
    tc = thinking_config(model, level)
    if tc:
        cfg['thinking_config'] = tc
    return client.models.generate_content(model=model, contents=contents, config=cfg)


def models_for(primary_setting, fallback_setting):
    seen, out = set(), []
    for m in (getattr(settings, primary_setting, ''), getattr(settings, fallback_setting, '')):
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out

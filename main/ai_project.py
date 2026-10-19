"""Gemini-based construction estimate parsing and catalog matching."""
import json
import logging
import re
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db.models import Q

logger = logging.getLogger(__name__)
MAX_ITEMS = 30

PROJECT_PROMPT = """Analyze this construction bill of quantities, photo/PDF, or project description.
It may describe ANY project: a house, concrete flooring/slab, a swimming pool,
retaining wall, fence, renovation, or another structure. Do not assume it is a house.
Return ONLY JSON in this schema:
{"project_type":"short project type","assumptions":["..."],"items":[{"query":"catalog search phrase in Uzbek or Russian","quantity":1,"unit":"kg|dona|m2|m3|qop|metr|...","reason":"brief calculation/estimate note"}]}
Use explicit quantities from a bill when legible. Otherwise estimate only when dimensions/material specs are sufficient, show important assumptions, and do not invent dimensions. If information is insufficient, return an empty items array and state what dimensions/specifications are needed in assumptions. Quantities must be positive numeric values. Return at most 30 distinct material lines; no prices or fabricated products."""


def analyze_project(message, upload=None):
    """Ask Gemini to extract materials from text and an optional image/PDF."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    prompt = PROJECT_PROMPT + "\n\nUser's project notes/dimensions:\n" + (message or "No extra notes.")
    parts = [types.Part.from_text(text=prompt)]
    if upload:
        parts.insert(0, types.Part.from_bytes(data=upload.read(), mime_type=upload.content_type))
    response = client.models.generate_content(
        model=getattr(settings, 'GEMINI_PROJECT_MODEL', 'gemini-3.8-flash'),
        contents=[types.Content(role='user', parts=parts)],
        config={"response_mime_type": "application/json", "temperature": 0.1, "max_output_tokens": 4096},
    )
    raw = response.text or '{}'
    raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.I)
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get('items', []), list):
        raise ValueError('Gemini returned an invalid project estimate.')
    return {
        'project_type': str(data.get('project_type', 'Loyiha'))[:160],
        'assumptions': [str(x)[:500] for x in (data.get('assumptions') if isinstance(data.get('assumptions'), list) else [])[:12]],
        'items': [x for x in data['items'][:MAX_ITEMS] if isinstance(x, dict)],
    }


def catalog_matches(query):
    """Find active marketplace listings for a material phrase."""
    from .models import Product
    terms = [term for term in re.findall(r"[\w-]+", str(query).lower()) if len(term) > 1][:8]
    if not terms:
        return []
    condition = Q()
    for term in terms:
        condition |= Q(name__icontains=term) | Q(name_ru__icontains=term) | Q(name_en__icontains=term) | Q(description__icontains=term)
    products = Product.objects.filter(store__status='active', stock__gt=0).filter(condition).select_related('store')[:80]
    ranked = []
    for product in products:
        searchable = ' '.join((product.name, product.name_ru, product.name_en, product.description)).lower()
        score = sum(1 for term in terms if term in searchable)
        ranked.append((score, product))
    ranked.sort(key=lambda pair: (-pair[0], pair[1].price))
    return [product for score, product in ranked[:3] if score]


def normalize_quantity(value):
    try:
        quantity = Decimal(str(value).replace(',', '.'))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not quantity.is_finite() or quantity <= 0 or quantity > 10000:
        return None
    return quantity.quantize(Decimal('0.001')).normalize()

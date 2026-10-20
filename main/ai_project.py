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
Use explicit quantities from a bill when legible. Otherwise estimate only when dimensions/material specs are sufficient, show important assumptions, and do not invent dimensions. If information is insufficient, return an empty items array and state what dimensions/specifications are needed in assumptions. Quantities must be positive numeric values. Return at most 30 distinct material lines; no prices or fabricated products.

DIMENSION-BASED WORK (important): when the project gives only dimensions/descriptions and no material quantities,
DO NOT calculate quantities yourself. Instead add a "works" array; the server calculates quantities with exact formulas:
"works":[{"type":"slab|pool|wall|plaster|paint|tile|flooring|foundation|roof|fence","title":"short label","params":{...}}]
All lengths in METERS (convert cm/mm yourself), areas in m2. Params by type (use only keys you actually know, never invent):
slab: length_m,width_m (or area_m2), thickness_cm | pool: length_m,width_m,depth_m,wall_thickness_cm,floor_thickness_cm |
wall: length_m,height_m (or area_m2), openings_m2, wall_type(brick|block), brick_layers(0.5|1|1.5|2), block_face_m2, thickness_cm |
plaster: length_m,height_m (or area_m2), openings_m2, thickness_mm, plaster_type(gypsum|cement) | paint: length_m,height_m (or area_m2), openings_m2, coats |
tile: length_m,width_m (or area_m2) | flooring: length_m,width_m (or area_m2) | foundation: length_m,width_cm,height_cm |
roof: area_m2 (roof surface) or length_m,width_m | fence: length_m,height_m,post_spacing_m.
Anything that does not fit these types (e.g. other structures) goes to "items" with your best-effort quantities and a clear assumption.
If a needed dimension is missing, add a question to "assumptions" instead of guessing. Write "assumptions", "title" and "reason" in the language: {language}."""


def sniff_mime(head):
    """Faylning haqiqiy turi (birinchi baytlar bo'yicha); mijoz yuborgan content-type'ga ishonmaymiz."""
    if head.startswith(b'%PDF-'):
        return 'application/pdf'
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if head.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'image/webp'
    return None


def analyze_project(message, upload=None, language='uz'):
    """Ask Gemini to extract materials from text and an optional image/PDF."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    lang_name = {'ru': 'Russian', 'en': 'English'}.get(language, 'Uzbek')
    prompt = PROJECT_PROMPT.replace('{language}', lang_name) + "\n\nUser's project notes/dimensions:\n" + (message or "No extra notes.")
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
        'works': [x for x in (data.get('works') if isinstance(data.get('works'), list) else [])[:12] if isinstance(x, dict)],
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
    if not quantity.is_finite() or quantity <= 0 or quantity > 1000000:
        return None
    return quantity.quantize(Decimal('0.001')).normalize()

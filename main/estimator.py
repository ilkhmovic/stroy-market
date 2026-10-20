"""Qurilish hisob-kitobi.

Muhim tamoyil: AI (Gemini) faqat matn/rasm/PDF dan ish turi va O'LCHAMLARNI ajratib beradi,
miqdorlarni esa shu yerdagi aniq formulalar hisoblaydi (AI arifmetikada adashishi mumkin).
Formulalar taxminiy qurilish me'yorlari; natija doim "tekshiring" deb ko'rsatiladi.
"""
import math
import re

from django.utils.translation import gettext as _

# Katalogdan qidirish uchun so'rovlar (o'zbekcha, ruscha, inglizcha so'zlar birga)
MAT = {
    'cement': 'sement цемент cement', 'sand': 'qum песок sand', 'gravel': 'shag щебень gravel',
    'mesh': 'armatura to\'ri сетка mesh', 'film': 'plyonka пленка polyethylene',
    'rebar': 'armatura арматура rebar', 'waterproof': 'gidroizolyatsiya гидроизоляция waterproofing',
    'tile': 'plitka плитка tile', 'tile_glue': 'plitka yelimi клей плиточный adhesive',
    'grout': 'fuga затирка grout', 'brick': 'g\'isht кирпич brick', 'block': 'blok блок block',
    'block_glue': 'blok yelimi клей блок', 'gypsum': 'gips shtukaturka штукатурка plaster',
    'primer': 'grunt грунтовка primer', 'paint': 'bo\'yoq краска paint',
    'laminate': 'laminat ламинат laminate', 'underlay': 'podlojka подложка underlay',
    'rubberoid': 'ruberoid рубероид', 'roof': 'tom metall profnastil металлочерепица roofing',
    'screws': 'samorez саморез screws', 'post': 'ustun stolb столб post',
    'profile_pipe': 'profil quvur профильная труба', 'profnastil': 'profnastil профнастил',
}

UNIT_ALIASES = {
    'kg': 'kg', 'кг': 'kg', 'kilogramm': 'kg', 'kilo': 'kg',
    't': 'tonna', 'т': 'tonna', 'tn': 'tonna', 'tonna': 'tonna', 'тонна': 'tonna',
    'm2': 'm2', 'm²': 'm2', 'м2': 'm2', 'м²': 'm2', 'kv.m': 'm2', 'kvm': 'm2', 'sqm': 'm2',
    'l': 'litr', 'litr': 'litr', 'л': 'litr', 'литр': 'litr',
    'm': 'metr', 'metr': 'metr', 'м': 'metr', 'pm': 'metr',
    'qop': 'qop', 'мешок': 'qop', 'm3': 'm3', 'm³': 'm3', 'м3': 'm3', 'м³': 'm3', 'kub': 'm3',
    'dona': 'dona', 'шт': 'dona', 'sht': 'dona', 'pcs': 'dona', 'ta': 'dona',
}


def normalize_unit(value):
    key = re.sub(r'[\s.]', '', str(value or '').lower())
    return UNIT_ALIASES.get(key, 'dona')


def pack_size(name, kind):
    """Mahsulot nomidagi qadoq o'lchami: 'Sement M400, 50 kg' -> 50 (kg). Topilmasa None."""
    text = str(name or '')
    if kind == 'kg':
        m = re.search(r'(\d+(?:[.,]\d+)?)\s*(kg|кг)(?![a-zа-я])', text, re.I)
        if m:
            return float(m.group(1).replace(',', '.'))
        m = re.search(r'(\d+(?:[.,]\d+)?)\s*(tonna|тонн\w*)', text, re.I)
        return float(m.group(1).replace(',', '.')) * 1000 if m else None
    pat = {'litr': r'(l|litr|л|литр\w*)(?![a-zа-я])', 'm2': r'(m2|m²|м2|м²)'}[kind]
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*' + pat, text, re.I)
    return float(m.group(1).replace(',', '.')) if m else None


def cart_quantity(need_qty, need_unit, product):
    """Kerakli miqdorni mahsulot birligidagi butun songa aylantiradi.

    Qaytaradi: (soni, aylantirildimi, birlik_mosmi). Masalan 630 kg sement va "Sement 50 kg" (qop)
    uchun -> (13, True, True). Birlikni aniqlab bo'lmasa soni o'zgarishsiz va birlik_mosmi=False.
    """
    need = float(need_qty)
    unit = normalize_unit(need_unit)
    if unit == 'm3':               # qum/shag'al: taxminan 1,5 t/m3
        need, unit = need * 1.5, 'tonna'
    if unit == 'tonna':
        need, unit = need * 1000, 'kg'
    pu = product.unit
    names = ' '.join(filter(None, (product.name, product.name_ru, product.name_en)))
    per = None
    if unit == 'kg':
        per = {'kg': 1, 'tonna': 1000}.get(pu) or (pack_size(names, 'kg') if pu in ('qop', 'dona') else None)
    elif unit == 'litr':
        per = 1 if pu == 'litr' else (pack_size(names, 'litr') if pu in ('qop', 'dona') else None)
    elif unit == 'm2':
        per = 1 if pu == 'm2' else (pack_size(names, 'm2') if pu in ('qop', 'dona') else None)
    elif unit == 'metr':
        per = 1 if pu == 'metr' else None
    elif unit in ('dona', 'qop'):
        per = 1 if pu in ('dona', 'qop') else None
    if per:
        return max(1, math.ceil(round(need / per, 6))), per != 1, True
    return max(1, math.ceil(need)), False, False


# ───────── Ish turlari bo'yicha formulalar ─────────

def _num(params, key, hi=100000.0):
    try:
        v = float(str(params.get(key)).replace(',', '.'))
    except (TypeError, ValueError):
        return None
    return v if 0 < v <= hi else None


def _area(params, a='length_m', b='width_m'):
    area = _num(params, 'area_m2')
    if area:
        return area
    x, y = _num(params, a), _num(params, b)
    return x * y if x and y else None


def _it(mat, qty, unit, reason):
    return {'query': MAT[mat], 'quantity': round(qty, 3), 'unit': unit, 'reason': reason}


def _fmt(x):
    return ('%.2f' % x).rstrip('0').rstrip('.')


def _concrete(volume):
    r = _("Beton M200 (%(v)s m³): 1 m³ ga taxminan 300 kg sement, 0,8 t qum va 1,2 t shag'al, zaxira 5 foiz.") % {'v': _fmt(volume)}
    return [_it('cement', volume * 300 * 1.05, 'kg', r), _it('sand', volume * 0.8 * 1.05, 'tonna', r),
            _it('gravel', volume * 1.2 * 1.05, 'tonna', r)]


def _slab(p):
    area = _area(p)
    if not area:
        return None
    th = _num(p, 'thickness_cm', 200) or 10
    items = _concrete(area * th / 100)
    items.append(_it('mesh', area * 1.1, 'm2', _("Armatura to'ri: maydon %(a)s m² (+10 foiz ustma-ust qo'yish).") % {'a': _fmt(area)}))
    items.append(_it('film', area * 1.15, 'm2', _("Polietilen plyonka: maydon %(a)s m² (+15 foiz).") % {'a': _fmt(area)}))
    return items


def _pool(p):
    L, W = _num(p, 'length_m'), _num(p, 'width_m')
    if not (L and W):
        return None
    D = _num(p, 'depth_m', 10) or 1.5
    w = (_num(p, 'wall_thickness_cm', 100) or 20) / 100
    f = (_num(p, 'floor_thickness_cm', 100) or 20) / 100
    vol = (L + 2 * w) * (W + 2 * w) * f + D * (2 * w * (L + W) + 4 * w * w)
    surface = L * W + 2 * (L + W) * D
    items = _concrete(vol)
    items.append(_it('rebar', vol * 90, 'kg', _("Armatura: 1 m³ betonga taxminan %(k)s kg (hajm %(v)s m³).") % {'k': 90, 'v': _fmt(vol)}))
    items.append(_it('waterproof', surface * 3, 'kg', _("Gidroizolyatsiya: ichki sirt %(s)s m², 3 kg/m² (2 qatlam).") % {'s': _fmt(surface)}))
    items.append(_it('tile', surface * 1.1, 'm2', _("Plitka: sirt %(a)s m² + 10 foiz zaxira.") % {'a': _fmt(surface)}))
    items.append(_it('tile_glue', surface * 5, 'kg', _("Plitka yelimi: 5 kg/m², sirt %(a)s m².") % {'a': _fmt(surface)}))
    items.append(_it('grout', surface * 0.5, 'kg', _("Fuga: 0,5 kg/m², sirt %(a)s m².") % {'a': _fmt(surface)}))
    return items


_BRICKS_PER_M2 = {0.5: 51, 1: 102, 1.5: 153, 2: 204}
_BRICK_T = {0.5: 0.12, 1: 0.25, 1.5: 0.38, 2: 0.51}


def _wall(p):
    area = _area(p, 'length_m', 'height_m')
    if not area:
        return None
    area = max(area - (_num(p, 'openings_m2') or 0), 0.0)
    if not area:
        return None
    if str(p.get('wall_type', 'brick')).lower() == 'block':
        face = _num(p, 'block_face_m2', 2) or 0.15
        th = (_num(p, 'thickness_cm', 100) or 20) / 100
        vol = area * th
        return [
            _it('block', area / face * 1.05, 'dona', _("Blok: devor %(a)s m², blok yuzasi %(f)s m² + 5 foiz zaxira.") % {'a': _fmt(area), 'f': _fmt(face)}),
            _it('block_glue', vol * 25, 'kg', _("Blok yelimi: devor hajmi %(v)s m³, 1 m³ ga ~25 kg.") % {'v': _fmt(vol)}),
        ]
    try:
        layers = float(p.get('brick_layers', 1))
    except (TypeError, ValueError):
        layers = 1
    layers = layers if layers in _BRICKS_PER_M2 else 1
    n = _BRICKS_PER_M2[layers]
    mortar = area * _BRICK_T[layers] * 0.23
    return [
        _it('brick', area * n * 1.05, 'dona', _("G'isht: devor %(a)s m², %(k)s g'isht qalinligida, 1 m² ga %(n)s dona + 5 foiz zaxira.") % {'a': _fmt(area), 'k': _fmt(layers), 'n': n}),
        _it('cement', mortar * 250, 'kg', _("Qorishma uchun sement: %(v)s m³ qorishma, 1 m³ ga ~250 kg.") % {'v': _fmt(mortar)}),
        _it('sand', mortar * 1.4, 'tonna', _("Qorishma uchun qum: %(v)s m³ qorishma, 1 m³ ga ~1,4 t.") % {'v': _fmt(mortar)}),
    ]


def _plaster(p):
    area = _area(p, 'length_m', 'height_m')
    if not area:
        return None
    area = max(area - (_num(p, 'openings_m2') or 0), 0.0)
    th = _num(p, 'thickness_mm', 100) or 15
    k = 1.8 if str(p.get('plaster_type', 'gypsum')).lower().startswith('cem') else 0.9
    return [
        _it('gypsum', area * th * k, 'kg', _("Shtukaturka: %(a)s m², qalinlik %(t)s mm, 1 mm/m² ga %(k)s kg.") % {'a': _fmt(area), 't': _fmt(th), 'k': k}),
        _it('primer', area * 0.2, 'litr', _("Grunt: %(a)s m², %(r)s l/m².") % {'a': _fmt(area), 'r': '0,2'}),
    ]


def _paint(p):
    area = _area(p, 'length_m', 'height_m')
    if not area:
        return None
    area = max(area - (_num(p, 'openings_m2') or 0), 0.0)
    coats = int(_num(p, 'coats', 6) or 2)
    return [
        _it('paint', area * coats * 0.14 * 1.05, 'litr', _("Bo'yoq: %(a)s m², %(c)s qatlam, 0,14 l/m² (qatlamiga), zaxira 5 foiz.") % {'a': _fmt(area), 'c': coats}),
        _it('primer', area * 0.1, 'litr', _("Grunt: %(a)s m², %(r)s l/m².") % {'a': _fmt(area), 'r': '0,1'}),
    ]


def _tile(p):
    area = _area(p)
    if not area:
        return None
    return [
        _it('tile', area * 1.1, 'm2', _("Plitka: sirt %(a)s m² + 10 foiz zaxira.") % {'a': _fmt(area)}),
        _it('tile_glue', area * 5, 'kg', _("Plitka yelimi: 5 kg/m², sirt %(a)s m².") % {'a': _fmt(area)}),
        _it('grout', area * 0.5, 'kg', _("Fuga: 0,5 kg/m², sirt %(a)s m².") % {'a': _fmt(area)}),
    ]


def _flooring(p):
    area = _area(p)
    if not area:
        return None
    return [
        _it('laminate', area * 1.07, 'm2', _("Laminat/parket: pol %(a)s m² + 7 foiz zaxira.") % {'a': _fmt(area)}),
        _it('underlay', area * 1.05, 'm2', _("Podlojka: pol %(a)s m² + 5 foiz.") % {'a': _fmt(area)}),
    ]


def _foundation(p):
    length = _num(p, 'length_m')
    if not length:
        return None
    w = (_num(p, 'width_cm', 300) or 40) / 100
    h = (_num(p, 'height_cm', 500) or 80) / 100
    vol = length * w * h
    items = _concrete(vol)
    items.append(_it('rebar', vol * 80, 'kg', _("Armatura: 1 m³ betonga taxminan %(k)s kg (hajm %(v)s m³).") % {'k': 80, 'v': _fmt(vol)}))
    items.append(_it('rubberoid', length * (w + 2 * h) * 1.15, 'm2', _("Ruberoid: poydevor uzunligi %(l)s m, ko'ndalang kesim bo'yicha + 15 foiz.") % {'l': _fmt(length)}))
    return items


def _roof(p):
    area = _area(p)
    if not area:
        return None
    return [
        _it('roof', area * 1.1, 'm2', _("Tom yopish: tom yuzasi %(a)s m² + 10 foiz zaxira.") % {'a': _fmt(area)}),
        _it('screws', area * 8, 'dona', _("Samorezlar: 1 m² ga %(n)s dona.") % {'n': 8}),
    ]


def _fence(p):
    length = _num(p, 'length_m')
    if not length:
        return None
    height = _num(p, 'height_m', 10) or 2
    step = _num(p, 'post_spacing_m', 10) or 2.5
    posts = math.ceil(length / step) + 1
    area = length * height
    return [
        _it('post', posts, 'dona', _("Ustunlar: uzunlik %(l)s m, har %(s)s m da bitta + 1.") % {'l': _fmt(length), 's': _fmt(step)}),
        _it('profile_pipe', length * 2, 'metr', _("Ko'ndalang quvurlar: 2 qator, jami %(l)s m.") % {'l': _fmt(length)}),
        _it('profnastil', area * 1.05, 'm2', _("Profnastil: to'siq yuzasi %(a)s m² + 5 foiz.") % {'a': _fmt(area)}),
        _it('screws', area * 6, 'dona', _("Samorezlar: 1 m² ga %(n)s dona.") % {'n': 6}),
        _it('cement', posts * 12, 'kg', _("Ustunlarni betonlash uchun sement: har bir ustunga ~12 kg.")),
    ]


WORK_TYPES = {
    'slab': _slab, 'pool': _pool, 'wall': _wall, 'plaster': _plaster, 'paint': _paint,
    'tile': _tile, 'flooring': _flooring, 'foundation': _foundation, 'roof': _roof, 'fence': _fence,
}


def calculate_works(works):
    """AI ajratgan ish turlari -> material qatorlari. Qaytaradi: (qatorlar, izohlar)."""
    items, notes = [], []
    for w in works[:12]:
        if not isinstance(w, dict):
            continue
        fn = WORK_TYPES.get(str(w.get('type', '')).lower())
        params = w.get('params') if isinstance(w.get('params'), dict) else {}
        if not fn:
            continue
        result = fn(params)
        if result:
            items.extend(result)
        else:
            notes.append(_("Hisoblash uchun o'lchamlar yetarli emas: %(title)s.") % {'title': str(w.get('title') or w.get('type'))[:80]})
    return items, notes

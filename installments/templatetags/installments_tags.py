from decimal import Decimal

from django import template

from ..models import InstallmentPartner, ProductInstallment

register = template.Library()


def _offers(partners):
    out = []
    for p in partners:
        plans = [{'months': pl.months, 'percent': float(pl.markup_percent)}
                 for pl in p.plans.all() if pl.is_active]
        if plans:
            out.append({'id': p.pk, 'name': p.name, 'logo': p.logo.url if p.logo else '', 'plans': plans})
    return out


@register.inclusion_tag('installments/_calculator.html')
def installment_calculator(amount, product=None, form_prefix=None, partners=None):
    """Mahsulot sahifasida: {% installment_calculator product.price product=product %}
    Checkoutda: {% installment_calculator get_total_price partners=partners form_prefix='nasiya-' %}
    form_prefix berilsa forma ichiga <prefix>partner va <prefix>months yashirin maydonlari qo'shiladi."""
    if partners is None:
        qs = InstallmentPartner.objects.filter(is_active=True).prefetch_related('plans')
        if product is not None:
            qs = qs.filter(pk__in=ProductInstallment.objects.filter(product=product).values('partner_id'))
        partners = qs
    try:
        amount = Decimal(str(amount))
    except Exception:
        amount = Decimal('0')
    import uuid
    return {'offers': _offers(partners), 'amount': amount, 'form_prefix': form_prefix, 'uid': uuid.uuid4().hex[:8]}


@register.inclusion_tag('installments/_partner_picker.html')
def product_partner_picker(product=None):
    """Sotuvchining mahsulot qo'shish/tahrirlash formasi ichida (<form> ichiga) qo'yiladi."""
    selected = set()
    if product is not None and getattr(product, 'pk', None):
        selected = set(ProductInstallment.objects.filter(product=product).values_list('partner_id', flat=True))
    partners = InstallmentPartner.objects.filter(is_active=True).prefetch_related('plans')
    items = [{'partner': p, 'checked': p.pk in selected,
              'plans': [pl for pl in p.plans.all() if pl.is_active]} for p in partners]
    return {'items': items}


@register.inclusion_tag('installments/_cards_block.html', takes_context=True)
def buyer_cards_block(context):
    """Mijoz profil sahifasida: kartalar ro'yxati va "Karta qo'shish" tugmasi."""
    request = context['request']
    return {'cards': request.user.wallet_cards.all() if request.user.is_authenticated else [],
            'next_url': request.get_full_path(), 'csrf_token': context.get('csrf_token')}

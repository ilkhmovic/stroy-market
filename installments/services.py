from decimal import Decimal, ROUND_HALF_UP

from django.apps import apps
from django.db import transaction


class CardError(Exception):
    """Foydalanuvchiga ko'rsatiladigan xato matni bilan."""


def to_decimal(value):
    try:
        d = Decimal(str(value).replace(' ', '').replace(',', '.'))
    except Exception:
        return None
    return d if d.is_finite() else None


def calc_installment(amount, markup_percent, months):
    """(jami, oyiga) so'mga yaxlitlangan holda qaytaradi."""
    amount = Decimal(amount)
    total = (amount * (Decimal('100') + Decimal(markup_percent)) / Decimal('100')).quantize(Decimal('1'), ROUND_HALF_UP)
    monthly = (total / Decimal(months)).quantize(Decimal('1'), ROUND_HALF_UP)
    return total, monthly


def fmt_sum(value):
    return f"{int(Decimal(value).quantize(Decimal('1'), ROUND_HALF_UP)):,}".replace(',', ' ')


def order_total(order):
    OrderItem = apps.get_model('main', 'OrderItem')
    items = OrderItem.objects.filter(order=order).exclude(status='cancelled')
    return sum((i.price * i.quantity for i in items), Decimal('0'))


def detect_brand(number):
    n = ''.join(ch for ch in number if ch.isdigit())
    if n.startswith('8600'):
        return 'uzcard'
    if n.startswith('9860'):
        return 'humo'
    if n.startswith('4'):
        return 'visa'
    if n[:2] in ('51', '52', '53', '54', '55') or (n[:4].isdigit() and 2221 <= int(n[:4]) <= 2720):
        return 'mastercard'
    return 'other'


@transaction.atomic
def top_up(card_id, amount, by_user=None, note=''):
    from .models import CardTransaction, WalletCard
    amount = to_decimal(amount)
    if amount is None or amount <= 0:
        raise CardError("Summani to'g'ri kiriting.")
    card = WalletCard.objects.select_for_update().get(pk=card_id)
    card.balance += amount
    card.save(update_fields=['balance'])
    CardTransaction.objects.create(card=card, kind='topup', amount=amount, balance_after=card.balance,
                                   note=note or "Admin tomonidan to'ldirildi", created_by=by_user)
    return card


@transaction.atomic
def pay_order(user, card_id, order_id):
    """Buyurtmani karta hisobidan to'laydi."""
    from .models import CardTransaction, WalletCard
    Order = apps.get_model('main', 'Order')
    order = Order.objects.select_for_update().filter(pk=order_id, user=user).first()
    if not order:
        raise CardError("Buyurtma topilmadi.")
    if order.status != 'pending':
        raise CardError("Bu buyurtmani to'lab bo'lmaydi.")
    if CardTransaction.objects.filter(order=order, kind='purchase').exists():
        raise CardError("Bu buyurtma allaqachon to'langan.")
    card = WalletCard.objects.select_for_update().filter(pk=card_id, user=user).first()
    if not card:
        raise CardError("Karta topilmadi.")
    if card.is_expired:
        raise CardError("Kartaning amal qilish muddati tugagan.")
    total = order_total(order)
    if total <= 0:
        raise CardError("Buyurtma summasi 0.")
    if card.balance < total:
        raise CardError(f"Hisobda mablag' yetarli emas. Kerak: {fmt_sum(total)} so'm, hisobda: {fmt_sum(card.balance)} so'm.")
    card.balance -= total
    card.save(update_fields=['balance'])
    CardTransaction.objects.create(card=card, kind='purchase', amount=total, balance_after=card.balance,
                                   order=order, note=f"Buyurtma #{order.pk} uchun to'landi", created_by=user)
    if 'paid' in dict(getattr(Order, 'STATUS_CHOICES', [])):
        order.status = 'paid'
        order.save(update_fields=['status'])
    return order, total


# ───────────── mahsulot ↔ nasiya hamkori ─────────────

def save_product_partners(request, product):
    """Sotuvchi mahsulot formasidagi `installment_partners` belgilarini saqlaydi.
    Forma ichida `installment_partners_present` yashirin maydoni bo'lmasa, hech narsa o'zgarmaydi."""
    from .models import InstallmentPartner, ProductInstallment
    if 'installment_partners_present' not in request.POST:
        return
    ids = [i for i in request.POST.getlist('installment_partners') if i.isdigit()]
    valid = set(InstallmentPartner.objects.filter(pk__in=ids, is_active=True).values_list('pk', flat=True))
    ProductInstallment.objects.filter(product=product).exclude(partner_id__in=valid).delete()
    have = set(ProductInstallment.objects.filter(product=product).values_list('partner_id', flat=True))
    ProductInstallment.objects.bulk_create([ProductInstallment(product=product, partner_id=p) for p in valid - have])


def partners_for_products(product_ids):
    """Savatdagi HAMMA mahsulot uchun umumiy bo'lgan faol hamkorlar (plani bor)."""
    from .models import InstallmentPartner, ProductInstallment
    product_ids = set(product_ids)
    if not product_ids:
        return InstallmentPartner.objects.none()
    ok = None
    for pid in product_ids:
        cur = set(ProductInstallment.objects.filter(product_id=pid).values_list('partner_id', flat=True))
        ok = cur if ok is None else ok & cur
    return (InstallmentPartner.objects.filter(pk__in=ok or [], is_active=True, plans__is_active=True)
            .distinct().prefetch_related('plans'))


def record_choice(application, partner, months):
    from .models import InstallmentPlan, NasiyaChoice
    plan = InstallmentPlan.objects.filter(partner=partner, months=months, is_active=True).first()
    if plan:
        NasiyaChoice.objects.update_or_create(application=application, defaults={
            'partner': partner, 'partner_name': partner.name,
            'months': plan.months, 'markup_percent': plan.markup_percent})


def wallet_paid_annotation(qs):
    """Order querysetiga `wallet_paid` (karta hisobidan to'langanmi) belgisini qo'shadi."""
    from django.db.models import Exists, OuterRef
    from .models import CardTransaction
    return qs.annotate(wallet_paid=Exists(
        CardTransaction.objects.filter(order=OuterRef('pk'), kind='purchase')))

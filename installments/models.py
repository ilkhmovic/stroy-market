import os
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def partner_logo_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f'partner_logos/{uuid.uuid4().hex}{ext}'


class InstallmentPartner(models.Model):
    """Nasiya hamkori (platforma). Admin qo'shadi."""
    name = models.CharField("Hamkor nomi", max_length=100, unique=True)
    logo = models.ImageField("Logo", upload_to=partner_logo_path, blank=True, null=True)
    is_active = models.BooleanField("Faol", default=True)
    sort_order = models.PositiveSmallIntegerField("Tartib raqami", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = "Nasiya hamkori"
        verbose_name_plural = "Nasiya hamkorlari"

    def __str__(self):
        return self.name


class InstallmentPlan(models.Model):
    """Hamkorning bitta muddati va shu muddat uchun ustama foizi (masalan 6 oy = 18%)."""
    partner = models.ForeignKey(InstallmentPartner, on_delete=models.CASCADE, related_name='plans')
    months = models.PositiveSmallIntegerField("Muddat (oy)", validators=[MinValueValidator(1), MaxValueValidator(60)])
    markup_percent = models.DecimalField("Ustama foiz (%)", max_digits=5, decimal_places=2,
                                         default=Decimal('0'), validators=[MinValueValidator(0)])
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        ordering = ['months']
        unique_together = [('partner', 'months')]
        verbose_name = "Muddat va ustama"
        verbose_name_plural = "Muddatlar va ustamalar"

    def __str__(self):
        return f"{self.partner} - {self.months} oy ({self.markup_percent}%)"


class ProductInstallment(models.Model):
    """Do'kon mahsulot uchun qaysi hamkor bilan nasiya shartnomasi borligini belgilaydi."""
    product = models.ForeignKey('main.Product', on_delete=models.CASCADE, related_name='installment_links')
    partner = models.ForeignKey(InstallmentPartner, on_delete=models.CASCADE, related_name='product_links')

    class Meta:
        unique_together = [('product', 'partner')]
        verbose_name = "Mahsulot nasiya hamkori"
        verbose_name_plural = "Mahsulot nasiya hamkorlari"

    def __str__(self):
        return f"{self.product_id} - {self.partner}"


class WalletCard(models.Model):
    """Mijoz kartasi. Xavfsizlik uchun faqat oxirgi 4 raqam va amal qilish muddati saqlanadi,
    to'liq karta raqami bazaga YOZILMAYDI."""
    BRANDS = [('uzcard', 'Uzcard'), ('humo', 'Humo'), ('visa', 'Visa'),
              ('mastercard', 'Mastercard'), ('other', 'Karta')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet_cards')
    holder_name = models.CharField("Karta egasi", max_length=60, blank=True)
    brand = models.CharField("Turi", max_length=12, choices=BRANDS, default='other')
    last4 = models.CharField("Oxirgi 4 raqam", max_length=4)
    exp_month = models.PositiveSmallIntegerField("Amal qilish oyi")
    exp_year = models.PositiveSmallIntegerField("Amal qilish yili")
    balance = models.DecimalField("Hisob balansi (so'm)", max_digits=14, decimal_places=2, default=Decimal('0'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Mijoz kartasi"
        verbose_name_plural = "Mijoz kartalari"

    def __str__(self):
        return f"{self.get_brand_display()} ****{self.last4} ({self.user})"

    @property
    def expiry_display(self):
        return f"{self.exp_month:02d}/{self.exp_year % 100:02d}"

    @property
    def is_expired(self):
        today = timezone.localdate()
        return (self.exp_year, self.exp_month) < (today.year, today.month)


class CardTransaction(models.Model):
    KINDS = [('topup', "Hisob to'ldirildi"), ('purchase', "Xarid uchun sarflandi")]

    card = models.ForeignKey(WalletCard, on_delete=models.CASCADE, related_name='transactions')
    kind = models.CharField(max_length=10, choices=KINDS)
    amount = models.DecimalField("Summa", max_digits=14, decimal_places=2)
    balance_after = models.DecimalField("Qoldiq", max_digits=14, decimal_places=2)
    order = models.ForeignKey('main.Order', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='card_transactions')
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = "Karta harakati"
        verbose_name_plural = "Karta harakatlari"

    def __str__(self):
        return f"{self.get_kind_display()} {self.amount}"


class NasiyaChoice(models.Model):
    """Mijoz nasiya arizasida tanlagan hamkor va muddat (sotuvchi Excel'i uchun)."""
    application = models.OneToOneField('main.NasiyaApplication', on_delete=models.CASCADE,
                                       related_name='installment_choice')
    partner = models.ForeignKey(InstallmentPartner, on_delete=models.SET_NULL, null=True, blank=True)
    partner_name = models.CharField(max_length=100)
    months = models.PositiveSmallIntegerField()
    markup_percent = models.DecimalField(max_digits=5, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Nasiya tanlovi"
        verbose_name_plural = "Nasiya tanlovlari"

    def __str__(self):
        return f"{self.partner_name} / {self.months} oy / {self.markup_percent}%"

from django.db import models
from django.utils.translation import gettext_lazy as _, get_language
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
import os
from uuid import uuid4
from decimal import Decimal

from django.utils.deconstruct import deconstructible

@deconstructible
class PathAndRename(object):
    def __init__(self, sub_path):
        self.path = sub_path

    def __call__(self, instance, filename):
        ext = filename.split('.')[-1]
        if hasattr(instance, 'name'):
            name = instance.name
        elif hasattr(instance, 'username'):
            name = instance.username
        else:
            name = uuid4().hex
        
        # clean name for filename
        name = "".join([c for c in name if c.isalnum() or c in (' ', '.', '_')]).strip().replace(' ', '_')
        filename = f'{name}_{uuid4().hex[:8]}.{ext}'
        return os.path.join(self.path, filename)

path_and_rename = PathAndRename

class Brand(models.Model):
    name = models.CharField(max_length=100, verbose_name="Brend nomi")
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name

class Region(models.Model):
    name = models.CharField(max_length=100, verbose_name="Viloyat nomi")

    def __str__(self):
        return self.name

class User(AbstractUser):
    is_seller = models.BooleanField(default=False, verbose_name="Sotuvchi")
    is_buyer = models.BooleanField(default=True, verbose_name="Sotib oluvchi")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Telefon raqam")
    address = models.TextField(blank=True, verbose_name="Manzil")
    avatar = models.ImageField(upload_to=path_and_rename('avatars/'), blank=True, null=True, verbose_name="Rasm")
    stir_pinfl = models.CharField(max_length=14, blank=True, verbose_name="STIR/PINFL")

    @property
    def unread_notifications_count(self):
        return self.notifications.filter(is_read=False).count()

class Store(models.Model):
    owner = models.OneToOneField(User, on_delete=models.CASCADE, related_name='store')
    name = models.CharField(max_length=200, verbose_name="Do'kon nomi")
    description = models.TextField(blank=True, verbose_name="Tarif")
    logo = models.ImageField(upload_to=path_and_rename('store_logos/'), blank=True, null=True, verbose_name="Logo")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Telefon")
    address = models.TextField(blank=True, verbose_name="Manzil")
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True, related_name='stores_at', verbose_name="Do'kon joylashuvi")
    status = models.CharField(
        max_length=20, 
        choices=[
            ('pending', _('Kutilmoqda')), 
            ('active', _('Faol')), 
            ('rejected', _('Rad etildi')),
            ('suspended', _('Vaqtinchalik to\'xtatilgan'))
        ], 
        default='pending',
        verbose_name="Holati"
    )
    delivery_regions = models.ManyToManyField(Region, blank=True, related_name='stores', verbose_name="Yetkazib berish hududlari")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="Toifa nomi")
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

class Product(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products', verbose_name="Do'kon")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products', verbose_name="Toifa")
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products', verbose_name="Brend")
    name = models.CharField(max_length=255, verbose_name="Mahsulot nomi")
    description = models.TextField(blank=True, verbose_name="Tarif")
    price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Narxi")
    stock = models.IntegerField(default=0, verbose_name="Soni")
    image = models.ImageField(upload_to=path_and_rename('products/'), blank=True, null=True, verbose_name="Rasm")
    name_ru = models.CharField(max_length=255, blank=True, default='', verbose_name="Nomi (ruscha)")
    name_en = models.CharField(max_length=255, blank=True, default='', verbose_name="Nomi (inglizcha)")
    description_ru = models.TextField(blank=True, default='', verbose_name="Tavsif (ruscha)")
    description_en = models.TextField(blank=True, default='', verbose_name="Tavsif (inglizcha)")
    is_top = models.BooleanField(default=False, verbose_name="Top mahsulot")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def _localized(self, base, ru, en):
        lang = (get_language() or 'uz')[:2]
        return (ru if lang == 'ru' and ru else en if lang == 'en' and en else base)

    @property
    def display_name(self):
        return self._localized(self.name, self.name_ru, self.name_en)

    @property
    def display_description(self):
        return self._localized(self.description, self.description_ru, self.description_en)

    def __str__(self):
        return self.name

    def avg_rating(self):
        reviews = self.reviews.all()
        if not reviews:
            return 0
        return round(sum(r.rating for r in reviews) / len(reviews), 1)

    def review_count(self):
        return self.reviews.count()

class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Baho (1-5)"
    )
    comment = models.TextField(verbose_name="Fikr")
    seller_reply = models.TextField(blank=True, verbose_name="Sotuvchi javobi")
    created_at = models.DateTimeField(auto_now_add=True)
    replied_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('product', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} → {self.product.name} ({self.rating}★)"

class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} savati"

    def get_total_price(self):
        return sum(item.get_total_price() for item in self.items.all())

    def total_items(self):
        return sum(item.quantity for item in self.items.all())

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)

    def get_total_price(self):
        return self.product.price * self.quantity

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending',   _('Kutilmoqda')),
        ('confirmed', _('Tasdiqlandi')),
        ('shipping',  _('Yetkazilmoqda')),
        ('delivered', _('Yetkazildi')),
        ('cancelled', _('Bekor qilindi')),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(
        max_length=10, 
        choices=[('card', _('Karta')), ('cash', _('Naqd')), ('nasiya', _('Nasiya'))], 
        default='card',
        verbose_name="To'lov turi"
    )
    buyer_confirmed = models.BooleanField(default=False, verbose_name="Xaridor tasdiqladi")
    penalty_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Jarima summasi")
    address = models.TextField(verbose_name="Yetkazib berish manzili")
    note = models.TextField(blank=True, verbose_name="Izoh")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def update_status(self):
        item_statuses = list(self.items.values_list('status', flat=True))
        if not item_statuses:
            return

        if all(s == 'delivered' for s in item_statuses):
            new_status = 'delivered'
        elif any(s == 'shipped' for s in item_statuses):
            new_status = 'shipping'
        elif any(s != 'pending' for s in item_statuses):
            new_status = 'confirmed'
        else:
            new_status = 'pending'

        if self.status != new_status:
            self.status = new_status
            self.save(update_fields=['status'])

    def get_total_price(self):
        return sum(item.get_total_price() for item in self.items.all())

    def get_potential_penalty(self):
        total = self.get_total_price()
        if total < 1000000:
            return Decimal('100000')
        else:
            return total * Decimal('0.1')

    def get_item_penalty(self, item_price, item_quantity):
        item_total = item_price * item_quantity
        # 10% penalty for item cancellation
        return item_total * Decimal('0.1')

    def apply_penalty(self, item=None):
        if self.payment_method == 'cash':
            if item:
                # Add penalty for a specific cancelled item
                self.penalty_amount += self.get_item_penalty(item.price, item.quantity)
            elif self.status == 'cancelled':
                # Re-calculate full penalty if entire order cancelled
                self.penalty_amount = self.get_potential_penalty()
            self.save(update_fields=['penalty_amount'])

    def __str__(self):
        return f"Buyurtma #{self.pk} — {self.user.username}"

class OrderItem(models.Model):
    STATUS_CHOICES = [
        ('pending', _('Kutilmoqda')),
        ('shipped', _('Jo\'natildi')),
        ('delivered', _('Yetkazildi')),
        ('cancelled', _('Bekor qilindi')),
    ]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    buyer_confirmed = models.BooleanField(default=False, verbose_name="Xaridor tasdiqladi")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.order.update_status()

    def get_total_price(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"

class NasiyaApplication(models.Model):
    """Nasiya (bo'lib to'lash) arizasi. Hamkor tizimga ulanmagan: ariza menejerga
    yuboriladi, menejer mijoz bilan bog'lanib, rasmiylashtirishni qo'lda bajaradi.
    Pasport/PINFL kabi maxfiy ma'lumotlar saytda SAQLANMAYDI, menejer ularni
    telefon yoki shaxsan olishi kerak."""
    TERM_CHOICES = [(3, _('3 oy')), (6, _('6 oy')), (12, _('12 oy'))]
    STATUS_CHOICES = [
        ('new', _('Yangi')),
        ('contacted', _("Bog'lanildi")),
        ('approved', _('Tasdiqlandi')),
        ('rejected', _('Rad etildi')),
    ]
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='nasiya')
    full_name = models.CharField(max_length=150, verbose_name="F.I.Sh.")
    phone = models.CharField(max_length=20, verbose_name="Telefon raqam")
    term_months = models.PositiveSmallIntegerField(choices=TERM_CHOICES, default=6, verbose_name="Muddat")
    monthly_income = models.DecimalField(
        max_digits=12, decimal_places=0, null=True, blank=True,
        verbose_name="Oylik daromad (ixtiyoriy)"
    )
    workplace = models.CharField(max_length=200, blank=True, verbose_name="Ish joyi (ixtiyoriy)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', verbose_name="Holati")
    manager_note = models.TextField(blank=True, verbose_name="Menejer izohi")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Nasiya arizasi"
        verbose_name_plural = "Nasiya arizalari"

    def __str__(self):
        return f"Nasiya #{self.pk} (buyurtma #{self.order_id}) - {self.full_name}"

    @property
    def monthly_payment(self):
        """Taxminiy oylik to'lov (ustama foizsiz, faqat ma'lumot uchun)."""
        total = self.order.get_total_price()
        return round(total / self.term_months) if self.term_months else total

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    target_url = models.CharField(max_length=255, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message[:20]}..."


class AnoraFallback(models.Model):
    """Gemini javob bermaganda Anora ishlatadigan qo'lda yozilgan javoblar (3 tilda)."""
    title = models.CharField(max_length=150, verbose_name="Sarlavha (ichki)")
    keywords = models.TextField(
        verbose_name="Kalit so'zlar",
        help_text="Vergul bilan ajrating, har uch tilda yozing: yetkazib, доставка, delivery"
    )
    answer_uz = models.TextField(verbose_name="Javob (o'zbekcha)")
    answer_ru = models.TextField(blank=True, verbose_name="Javob (ruscha)")
    answer_en = models.TextField(blank=True, verbose_name="Javob (inglizcha)")
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Anora zaxira javobi"
        verbose_name_plural = "Anora zaxira javoblari"

    def __str__(self):
        return self.title

    def answer_for(self, lang):
        return (self.answer_ru if lang == 'ru' and self.answer_ru else
                self.answer_en if lang == 'en' and self.answer_en else self.answer_uz)

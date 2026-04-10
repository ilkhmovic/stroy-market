from django.db import models
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
            ('pending', 'Kutilmoqda'), 
            ('active', 'Faol'), 
            ('rejected', 'Rad etildi'),
            ('suspended', 'Vaqtinchalik to\'xtatilgan')
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
    is_top = models.BooleanField(default=False, verbose_name="Top mahsulot")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
        ('pending',   'Kutilmoqda'),
        ('confirmed', 'Tasdiqlandi'),
        ('shipping',  'Yetkazilmoqda'),
        ('delivered', 'Yetkazildi'),
        ('cancelled', 'Bekor qilindi'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(
        max_length=10, 
        choices=[('card', 'Karta'), ('cash', 'Naqd')], 
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
        ('pending', 'Kutilmoqda'),
        ('shipped', 'Jo\'natildi'),
        ('delivered', 'Yetkazildi'),
        ('cancelled', 'Bekor qilindi'),
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

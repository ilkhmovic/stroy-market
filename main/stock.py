"""Buyurtma zaxirasini kamaytirish va bekor qilishda qaytarish."""
from django.db.models import F

from .models import OrderItem, Product


class InsufficientStock(Exception):
    def __init__(self, product):
        self.product = product
        super().__init__(f"Yetarli zaxira yo'q: {product.name}")


def restore_item_stock_once(item):
    """Bekor qilinmagan qator zaxirasini aynan bir marta qaytaradi.

    Avval statusni `cancelled` qiladi (faqat hali bekor qilinmagan bo'lsa),
    keyin zaxirani oshiradi. Ikkinchi chaqiriq hech narsa qilmaydi.
    """
    updated = (
        OrderItem.objects.filter(pk=item.pk, status='pending')
        .update(status='cancelled')
    )
    if not updated:
        return False
    if item.product_id:
        Product.objects.filter(pk=item.product_id).update(
            stock=F('stock') + item.quantity
        )
    item.status = 'cancelled'
    item.order.update_status()
    return True

import os
import django
import random
from datetime import timedelta
from django.utils import timezone

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from main.models import Product, Order, OrderItem, Store

User = get_user_model()

def populate_data():
    # Get the first seller
    seller = User.objects.filter(is_seller=True).first()
    if not seller:
        print("Sotuvchi topilmadi. Avval sotuvchi sifatida ro'yxatdan o'ting.")
        return

    # Get seller's products
    products = Product.objects.filter(store__owner=seller)
    if not products.exists():
        print(f"{seller.username} uchun mahsulotlar topilmadi.")
        return

    # Get or create a buyer
    buyer = User.objects.filter(is_seller=False).first()
    if not buyer:
        buyer = User.objects.create_user(username='demo_buyer', password='password123', is_seller=False)

    print(f"Ma'lumotlar qo'shilmoqda: Seller={seller.username}, Buyer={buyer.username}")

    # Generate orders for the last 15 days
    now = timezone.now()
    order_count = 0

    for i in range(15):
        # Create a date for current iteration
        date = now - timedelta(days=i)
        
        # Create 1-3 orders per day
        for _ in range(random.randint(1, 3)):
            order = Order.objects.create(
                user=buyer,
                address="Toshkent sh., Yunusobod tumani",
                status='delivered'
            )
            # Update created_at directly to bypass auto_now_add
            Order.objects.filter(pk=order.pk).update(created_at=date)

            # Add 1-2 random items from this seller's products
            num_items = random.randint(1, min(len(products), 3))
            selected_products = random.sample(list(products), k=num_items)
            
            for prod in selected_products:
                qty = random.randint(1, 10)
                OrderItem.objects.create(
                    order=order,
                    product=prod,
                    product_name=prod.name,
                    price=prod.price,
                    quantity=qty,
                    status='delivered'
                )
            order_count += 1

    print(f"Muvaffaqiyatli! {order_count} ta buyurtma qo'shildi.")

if __name__ == "__main__":
    populate_data()

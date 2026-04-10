import urllib.request
import os
import django
from django.core.files.base import ContentFile
from django.utils.text import slugify
from django.contrib.auth import get_user_model

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from main.models import Store, Category, Product, Order, OrderItem

User = get_user_model()

def download_image(url):
    try:
        response = urllib.request.urlopen(url)
        return ContentFile(response.read())
    except Exception as e:
        print(f"Error downloading image {url}: {e}")
        return None

def run():
    print("Starting data population for Elit Qurilish...")

    # 1. Create Seller
    seller, created = User.objects.get_or_create(
        username='elite_admin',
        defaults={
            'first_name': 'Elit',
            'last_name': 'Sotuvchi',
            'email': 'elite@bozor.uz',
            'is_seller': True,
            'is_buyer': False
        }
    )
    if created:
        seller.set_password('elite123')
        seller.save()
        print(f"Created seller: {seller.username}")

    # 2. Create Store
    store, created = Store.objects.get_or_create(
        owner=seller,
        defaults={
            'name': 'Elit Qurilish',
            'description': "Professional qurilish materiallari va asbob-uskunalar. Sifat va ishonch kafolati.",
            'phone': '+998 90 123 45 67',
            'address': 'Toshkent sh., Yunusobod tumani, Qurilish bozori'
        }
    )
    if created:
        print(f"Created store: {store.name}")

    # 3. Categories
    cats = [
        ('Qurilish Materiallari', 'qurilish-materiallari'),
        ('Bo\'yoqlar', 'boyoqlar'),
        ('Asboblar', 'asboblar'),
    ]
    category_map = {}
    for name, slug in cats:
        cat, _ = Category.objects.get_or_create(name=name, defaults={'slug': slug})
        category_map[name] = cat

    # 4. Products Data (Unsplash IDs)
    products_data = [
        {
            'name': 'Sement Premium 450 (50kg)',
            'price': 65000,
            'stock': 500,
            'desc': 'Yuqori sifatli M450 markali sement. Beton ishlari uchun ideal.',
            'category': 'Qurilish Materiallari',
            'img_url': 'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?q=80&w=600&auto=format&fit=crop'
        },
        {
            'name': 'Pishgan G\'isht (Buxoro)',
            'price': 1800,
            'stock': 10000,
            'desc': 'Mustahkam va chiroyli pishgan g\'isht. Devorlar uchun.',
            'category': 'Qurilish Materiallari',
            'img_url': 'https://images.unsplash.com/photo-1582266255765-fa5cf1a1d501?q=80&w=600&auto=format&fit=crop'
        },
        {
            'name': 'Akril Bo\'yoq (Oq, 10L)',
            'price': 125000,
            'stock': 40,
            'desc': 'Yuviladigan yuqori sifatli oq akril bo\'yoq.',
            'category': 'Bo\'yoqlar',
            'img_url': 'https://images.unsplash.com/photo-1589939705384-5185137a7f0f?q=80&w=600&auto=format&fit=crop'
        },
        {
            'name': 'Professional Perforator 1500W',
            'price': 850000,
            'stock': 15,
            'desc': 'Kuchli va mustahkam perforator, og\'ir ishlar uchun.',
            'category': 'Asboblar',
            'img_url': 'https://images.unsplash.com/photo-1581244277943-fe4a9c777189?q=80&w=600&auto=format&fit=crop'
        },
        {
            'name': 'Tom yopish tunukasi (0.45mm)',
            'price': 75000,
            'stock': 200,
            'desc': 'Polimer qoplamali chidamli tunuka.',
            'category': 'Qurilish Materiallari',
            'img_url': 'https://images.unsplash.com/photo-1632759162402-0e9e4f3de549?q=80&w=600&auto=format&fit=crop'
        },
        {
            'name': 'Dekorativ panel (Moyli)',
            'price': 45000,
            'stock': 120,
            'desc': 'Chiroyli dizayndagi devor panellari.',
            'category': 'Bo\'yoqlar',
            'img_url': 'https://images.unsplash.com/photo-1595428774751-2292f392233f?q=80&w=600&auto=format&fit=crop'
        }
    ]

    added_products = []
    for p_data in products_data:
        p, created = Product.objects.get_or_create(
            name=p_data['name'],
            store=store,
            defaults={
                'price': p_data['price'],
                'stock': p_data['stock'],
                'description': p_data['desc'],
                'category': category_map[p_data['category']]
            }
        )
        if created:
            print(f"Downloading image for {p.name}...")
            img_content = download_image(p_data['img_url'])
            if img_content:
                p.image.save(f"{slugify(p.name)}.jpg", img_content, save=True)
            print(f"Created product: {p.name}")
        added_products.append(p)

    # 5. Simulate Sales for Top Sellers Carousel
    # We need a buyer
    buyer, _ = User.objects.get_or_create(
        username='test_buyer_elite',
        defaults={'is_buyer': True, 'is_seller': False}
    )

    print("Simulating sales to populate carousel...")
    for p in added_products:
        # Create an order for each product with random quantity 5-15
        import random
        qty = random.randint(10, 30)
        order = Order.objects.create(
            user=buyer,
            status='delivered',
            address='Test Address'
        )
        OrderItem.objects.create(
            order=order,
            product=p,
            product_name=p.name,
            price=p.price,
            quantity=qty,
            status='delivered'
        )
    
    print("Done! Data population complete.")

if __name__ == '__main__':
    run()

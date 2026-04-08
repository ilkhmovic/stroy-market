from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Avg, F
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from .models import Product, Store, Category, Cart, CartItem, Order, OrderItem, Review, Notification
from .forms import UserRegisterForm, StoreForm, ProductForm, BuyerProfileForm, ReviewForm


def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            if user.is_seller:
                return redirect('seller_dashboard')
            return redirect('marketplace')
    else:
        form = UserRegisterForm()
    return render(request, 'main/register.html', {'form': form})


def marketplace(request):
    products = Product.objects.all().order_by('-created_at')
    
    # Calculate top selling products (Sold quantity)
    top_sellers = Product.objects.annotate(
        total_sold=Sum('orderitem__quantity')
    ).filter(total_sold__gt=0).order_by('-total_sold')[:10]
    
    categories = Category.objects.all()
    q = request.GET.get('q')
    category_slug = request.GET.get('category')
    
    if q:
        products = products.filter(name__icontains=q)
    if category_slug:
        products = products.filter(category__slug=category_slug)
        
    return render(request, 'main/marketplace.html', {
        'products': products,
        'top_sellers': top_sellers,
        'categories': categories,
        'current_category': category_slug,
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    related = Product.objects.filter(category=product.category).exclude(pk=pk)[:4]
    return render(request, 'main/product_detail.html', {
        'product': product,
        'related': related,
    })


# ────────── PROFILE ──────────

@login_required
def profile(request):
    if request.user.is_seller:
        return redirect('seller_profile')
    return redirect('buyer_profile')


@login_required
def buyer_profile(request):
    if request.user.is_seller:
        return redirect('seller_profile')
    if request.method == 'POST':
        form = BuyerProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Ma'lumotlaringiz yangilandi!")
            return redirect('buyer_profile')
    else:
        form = BuyerProfileForm(instance=request.user)
    cart = Cart.objects.filter(user=request.user).first()
    return render(request, 'main/buyer_profile.html', {'form': form, 'cart': cart})


@login_required
def seller_profile(request):
    if not request.user.is_seller:
        return redirect('buyer_profile')
    store = getattr(request.user, 'store', None)
    if request.method == 'POST':
        form = StoreForm(request.POST, request.FILES, instance=store)
        if form.is_valid():
            s = form.save(commit=False)
            s.owner = request.user
            s.save()
            messages.success(request, "Do'kon ma'lumotlari yangilandi!")
            return redirect('seller_profile')
    else:
        form = StoreForm(instance=store)
    return render(request, 'main/seller_profile.html', {'form': form, 'store': store})


# ────────── SELLER DASHBOARD ──────────

@login_required
def seller_dashboard(request):
    if not request.user.is_seller:
        return redirect('marketplace')
    if not hasattr(request.user, 'store'):
        return redirect('create_store')
    store = request.user.store
    products = store.products.all()
    return render(request, 'main/seller_dashboard.html', {'store': store, 'products': products})


@login_required
def create_store(request):
    if not request.user.is_seller:
        return redirect('marketplace')
    if hasattr(request.user, 'store'):
        return redirect('seller_dashboard')
    if request.method == 'POST':
        form = StoreForm(request.POST, request.FILES)
        if form.is_valid():
            store = form.save(commit=False)
            store.owner = request.user
            store.save()
            return redirect('seller_dashboard')
    else:
        form = StoreForm()
    return render(request, 'main/store_form.html', {'form': form})


@login_required
def add_product(request):
    if not request.user.is_seller or not hasattr(request.user, 'store'):
        return redirect('marketplace')
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.store = request.user.store
            product.save()
            return redirect('seller_dashboard')
    else:
        form = ProductForm()
    return render(request, 'main/product_form.html', {'form': form})


# ────────── CART ──────────

def _get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


@login_required
def cart_view(request):
    if request.user.is_seller:
        return redirect('marketplace')
    cart = _get_or_create_cart(request.user)
    items = cart.items.select_related('product').all()
    return render(request, 'main/cart.html', {'cart': cart, 'items': items})


@login_required
def add_to_cart(request, pk):
    if request.user.is_seller:
        messages.error(request, "Sotuvchilar savat ishlatа olmaydi.")
        return redirect('product_detail', pk=pk)
    product = get_object_or_404(Product, pk=pk)
    cart = _get_or_create_cart(request.user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        item.quantity += 1
        item.save()
    messages.success(request, f"'{product.name}' savatga qo'shildi!")
    return redirect(request.META.get('HTTP_REFERER', 'cart'))


@login_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    item.delete()
    messages.success(request, "Mahsulot savatdan o'chirildi.")
    return redirect('cart')


@login_required
def update_cart(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    qty = int(request.POST.get('quantity', 1))
    if qty < 1:
        item.delete()
    else:
        item.quantity = qty
        item.save()
    return redirect('cart')


# ────────── CHECKOUT & ORDERS ──────────

@login_required
def checkout(request):
    if request.user.is_seller:
        return redirect('marketplace')
    
    cart = _get_or_create_cart(request.user)
    items = cart.items.select_related('product').all()
    
    if not items.exists():
        messages.error(request, "Savatda mahsulot yo'q!")
        return redirect('cart')
    
    if request.method == 'POST':
        address = request.POST.get('address', '').strip()
        note = request.POST.get('note', '').strip()
        
        if not address:
            messages.error(request, "Yetkazib berish manzilini kiriting!")
            return render(request, 'main/checkout.html', {
                'cart': cart,
                'items': items,
                'get_total_price': cart.get_total_price(),
            })
        
        # Create order
        get_total_price = cart.get_total_price()
        order = Order.objects.create(
            user=request.user,
            address=address,
            note=note,
            status='pending'
        )
        
        # Create order items and identify sellers to notify
        sellers_to_notify = set()
        for item in items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                product_name=item.product.name,
                price=item.product.price,
                quantity=item.quantity
            )
            # Notify seller
            if item.product.store:
                sellers_to_notify.add(item.product.store.owner)
            
            # Reduce stock
            item.product.stock -= item.quantity
            item.product.save()
        
        # Create notifications for sellers
        for seller in sellers_to_notify:
            Notification.objects.create(
                user=seller,
                message=f"Yangi buyurtma! #{order.pk} raqamli buyurtmada sizning mahsulotingiz bor."
            )
        
        # Clear cart
        cart.items.all().delete()
        
        messages.success(request, "Buyurtma muvaffaqiyatli qabul qilindi! Sotuvchilar xabardor qilindi.")
        return redirect('order_detail', order_id=order.pk)
    
    return render(request, 'main/checkout.html', {
        'cart': cart,
        'items': items,
        'get_total_price': cart.get_total_price(),
        'user_address': request.user.address,
    })


@login_required
def orders(request):
    if request.user.is_seller:
        return redirect('marketplace')
    
    user_orders = Order.objects.filter(user=request.user).prefetch_related('items').order_by('-created_at')
    return render(request, 'main/orders.html', {'orders': user_orders})


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    items = order.items.all()
    return render(request, 'main/order_detail.html', {'order': order, 'items': items})


# ────────── REVIEWS ──────────

@login_required
def add_review(request, pk):
    if request.user.is_seller:
        messages.error(request, "Sotuvchilar fikr bildira olmaydi.")
        return redirect('product_detail', pk=pk)
    
    product = get_object_or_404(Product, pk=pk)
    
    # Check if user has a DELIVERED order item for this product
    has_delivered = OrderItem.objects.filter(
        order__user=request.user,
        product=product,
        status='delivered'
    ).exists()
    
    if not has_delivered:
        messages.error(request, "Fikr bildirish uchun avval bu mahsulotni sotib olishingiz va u yetkazib berilishi kerak!")
        return redirect('product_detail', pk=pk)
    
    # Check if user already reviewed
    existing_review = Review.objects.filter(product=product, user=request.user).first()
    
    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=existing_review)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.user = request.user
            review.save()
            msg = "Sharh yangilandi!" if existing_review else "Sharh qo'shildi!"
            messages.success(request, msg)
            return redirect('product_detail', pk=pk)
    else:
        form = ReviewForm(instance=existing_review)
    
    return render(request, 'main/add_review.html', {'form': form, 'product': product})

@login_required
def add_review_reply(request, review_id):
    review = get_object_or_404(Review, pk=review_id, product__store__owner=request.user)
    
    if request.method == 'POST':
        reply_text = request.POST.get('reply_text', '').strip()
        if reply_text:
            review.seller_reply = reply_text
            import django.utils.timezone as timezone
            review.replied_at = timezone.now()
            review.save()
            messages.success(request, "Javobingiz muvaffaqiyatli saqlandi!")
        else:
            messages.error(request, "Javob matnini kiriting.")
            
    return redirect('seller_reviews')

@login_required
def seller_reviews(request):
    if not request.user.is_seller:
        return redirect('marketplace')
    
    # Get all reviews for products owned by this seller
    reviews = Review.objects.filter(product__store__owner=request.user).order_by('-created_at')
    
    return render(request, 'main/seller_reviews.html', {'reviews': reviews})

@login_required
def update_order_item_status(request, item_id):
    item = get_object_or_404(OrderItem, pk=item_id, product__store__owner=request.user)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(OrderItem.STATUS_CHOICES):
            item.status = new_status
            item.save()
            
            # Notify buyer
            Notification.objects.create(
                user=item.order.user,
                message=f"'{item.product_name}' mahsulotingiz holati '{item.get_status_display()}' ga o'zgardi."
            )
            messages.success(request, f"Status '{item.get_status_display()}' ga o'zgartirildi.")
            
    return redirect('seller_orders')

@login_required
def seller_statistics(request):
    if not request.user.is_seller:
        return redirect('marketplace')
    
    # Date filtering
    period = request.GET.get('period', '30')
    end_date = timezone.now()
    
    if period == '7':
        start_date = end_date - timedelta(days=7)
    elif period == '30':
        start_date = end_date - timedelta(days=30)
    elif period == '90':
        start_date = end_date - timedelta(days=90)
    elif period == 'custom':
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        try:
            from django.utils.dateparse import parse_date
            start_date = timezone.make_aware(timezone.datetime.combine(parse_date(start_date_str), timezone.datetime.min.time()))
            end_date = timezone.make_aware(timezone.datetime.combine(parse_date(end_date_str), timezone.datetime.max.time()))
        except:
            start_date = end_date - timedelta(days=30)
    else:
        start_date = end_date - timedelta(days=30)

    # Base Query
    base_items = OrderItem.objects.filter(
        product__store__owner=request.user,
        order__created_at__range=(start_date, end_date)
    ).exclude(status='cancelled')

    # Summary Metrics
    total_revenue = base_items.aggregate(total=Sum(F('price') * F('quantity')))['total'] or 0
    total_orders = base_items.values('order').distinct().count()
    items_sold = base_items.aggregate(total=Sum('quantity'))['total'] or 0

    # Top 5 Best Selling Products
    top_selling = base_items.values('product__name', 'product__image').annotate(
        total_qty=Sum('quantity'),
        total_val=Sum(F('price') * F('quantity'))
    ).order_by('-total_qty')[:5]

    # Top 5 Rated Products
    top_rated = Product.objects.filter(store__owner=request.user).annotate(
        avg_rating=Avg('reviews__rating'),
        review_count=Count('reviews')
    ).filter(review_count__gt=0).order_by('-avg_rating')[:5]

    # Daily Sales Data for Chart
    daily_sales = base_items.annotate(day=TruncDate('order__created_at')).values('day').annotate(
        daily_total=Sum(F('price') * F('quantity'))
    ).order_by('day')

    # Daily Sales Data for Chart (Formatted for JSON)
    daily_sales_list = []
    for d in daily_sales:
        daily_sales_list.append({
            'day': d['day'].strftime('%Y-%m-%d'),
            'daily_total': float(d['daily_total'])
        })

    context = {
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'items_sold': items_sold,
        'top_selling': top_selling,
        'top_rated': top_rated,
        'daily_sales_json': daily_sales_list,
        'start_date': start_date,
        'end_date': end_date,
        'period': period
    }
    
    return render(request, 'main/seller_statistics.html', context)

@login_required
def seller_orders(request):
    if not request.user.is_seller:
        return redirect('marketplace')
    
    # Get all order items that belong to this seller's products
    seller_items = OrderItem.objects.filter(
        product__store__owner=request.user
    ).select_related('order', 'order__user', 'product').order_by('-order__created_at')
    
    return render(request, 'main/seller_orders.html', {'items': seller_items})

@login_required
def mark_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save()
    return redirect(request.META.get('HTTP_REFERER', 'seller_dashboard'))

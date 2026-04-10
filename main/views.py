from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Count, Avg, F
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from .models import User, Product, Store, Category, Cart, CartItem, Order, OrderItem, Review, Notification, Brand, Region
from .forms import UserRegisterForm, StoreForm, ProductForm, BuyerProfileForm, ReviewForm, CategoryForm, UserAdminForm, OrderAdminForm, NotificationForm, BrandForm, RegionForm


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
    # Only show products from active stores
    products = Product.objects.filter(store__status='active').order_by('-created_at')
    
    # Filters
    q = request.GET.get('q')
    category_slug = request.GET.get('category')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    brand_ids = request.GET.getlist('brands')
    region_ids = request.GET.getlist('regions')
    
    if q:
        products = products.filter(name__icontains=q)
    if category_slug:
        products = products.filter(category__slug=category_slug)
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)
    if brand_ids:
        products = products.filter(brand_id__in=brand_ids)
    if region_ids:
        # Filter by store's delivery regions
        products = products.filter(store__delivery_regions__id__in=region_ids).distinct()
        
    top_sellers = Product.objects.annotate(
        total_sold=Sum('orderitem__quantity')
    ).filter(total_sold__gt=0).order_by('-total_sold')[:10]
    
    categories = Category.objects.all()
    brands = Brand.objects.all()
    regions = Region.objects.all()
        
    return render(request, 'main/marketplace.html', {
        'products': products,
        'top_sellers': top_sellers,
        'categories': categories,
        'brands': brands,
        'regions': regions,
        'current_category': category_slug,
        'current_brands': list(map(int, brand_ids)) if brand_ids else [],
        'current_regions': list(map(int, region_ids)) if region_ids else [],
        'min_price': min_price,
        'max_price': max_price,
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    related = Product.objects.filter(category=product.category).exclude(pk=pk)[:4]
    
    has_delivered = False
    if request.user.is_authenticated:
        has_delivered = OrderItem.objects.filter(
            order__user=request.user,
            product=product,
            status='delivered'
        ).exists()
        
    return render(request, 'main/product_detail.html', {
        'product': product,
        'related': related,
        'has_delivered': has_delivered,
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
    if store.status == 'pending':
        return render(request, 'main/store_pending.html', {'store': store})
    if store.status == 'rejected':
        return render(request, 'main/store_rejected.html', {'store': store})
        
    products = store.products.all()
    return render(request, 'main/seller_dashboard.html', {'store': store, 'products': products})


@login_required
def create_store(request):
    if not request.user.is_seller:
        return redirect('marketplace')
    if hasattr(request.user, 'store'):
        return redirect('seller_dashboard')
        
    # Check for missing info
    if not request.user.stir_pinfl or not request.user.phone:
        messages.warning(request, "Do'kon ochishdan oldin STIR va telefon raqamingizni kiriting.")
        return redirect('buyer_profile')
        
    if request.method == 'POST':
        form = StoreForm(request.POST, request.FILES)
        if form.is_valid():
            store = form.save(commit=False)
            store.owner = request.user
            store.save()
            form.save_m2m() # Save ManyToMany delivery_regions
            messages.success(request, "Do'kon muvaffaqiyatli yaratildi va tasdiqlash uchun yuborildi.")
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
        payment_method = request.POST.get('payment_method', 'card')
        
        if not address:
            messages.error(request, "Yetkazib berish manzilini kiriting!")
            return render(request, 'main/checkout.html', {
                'cart': cart,
                'items': items,
                'get_total_price': cart.get_total_price(),
            })
        
        # Create order
        order = Order.objects.create(
            user=request.user,
            address=address,
            note=note,
            payment_method=payment_method,
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
                message=f"Yangi buyurtma! #{order.pk} raqamli buyurtmada sizning mahsulotingiz bor.",
                target_url='/seller/orders/'
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
    
    # Group items by store for split confirmation
    stores_data = {}
    for item in order.items.all().select_related('product__store'):
        store = item.product.store
        if store.pk not in stores_data:
            stores_data[store.pk] = {
                'store': store,
                'items': [],
                'all_confirmed': True,
                'can_confirm': False
            }
        stores_data[store.pk]['items'].append(item)
        if not item.buyer_confirmed:
            stores_data[store.pk]['all_confirmed'] = False
            if item.status in ['shipped', 'delivered']:
                stores_data[store.pk]['can_confirm'] = True
                
    return render(request, 'main/order_detail.html', {
        'order': order, 
        'stores_data': stores_data.values()
    })


@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    # Allow cancellation if entire order is pending OR if it's confirmed but has pending items
    pending_items = order.items.filter(status='pending')
    
    if order.status in ['pending', 'confirmed'] and pending_items.exists():
        # Cancel only pending items
        for item in pending_items:
            if item.product:
                item.product.stock += item.quantity
                item.product.save()
            item.status = 'cancelled'
            item.save()
            
            # Notify seller
            if item.product and item.product.store:
                Notification.objects.create(
                    user=item.product.store.owner,
                    message=f"#{order.pk} buyurtmadagi '{item.product_name}' mahsuloti xaridor tomonidan bekor qilindi.",
                    target_url='/seller/orders/'
                )
            
            # Apply penalty for each pending item being cancelled
            old_penalty = order.penalty_amount
            order.apply_penalty(item=item)
            if order.penalty_amount > old_penalty:
                penalty_diff = order.penalty_amount - old_penalty
                messages.warning(request, f"Naqd puldagi buyurtma bekor qilingani uchun {penalty_diff|floatformat:0} so'm jarima qo'llandi.")
        
        # If all items are now cancelled, set order status to cancelled
        # If some were delivered/shipped, update_status (called in item.save) will handle it
        
        messages.success(request, "Kutilayotgan mahsulotlar bekor qilindi.")
    else:
        messages.error(request, "Bu buyurtmani bekor qilib bo'lmaydi yoki kutilayotgan mahsulotlar yo'q.")
        
    return redirect('order_detail', order_id=order.pk)


@login_required
def cancel_order_item(request, item_id):
    item = get_object_or_404(OrderItem, pk=item_id, order__user=request.user)
    if item.status == 'pending':
        item.status = 'cancelled'
        if item.product:
            item.product.stock += item.quantity
            item.product.save()
        item.save()
        
        # Notify seller
        if item.product and item.product.store:
            Notification.objects.create(
                user=item.product.store.owner,
                message=f"#{item.order.pk} buyurtmadagi '{item.product_name}' mahsuloti xaridor tomonidan bekor qilindi.",
                target_url='/seller/orders/'
            )
            
        old_penalty = item.order.penalty_amount
        item.order.apply_penalty(item=item)
        if item.order.penalty_amount > old_penalty:
            penalty_diff = item.order.penalty_amount - old_penalty
            messages.warning(request, f"Naqd puldagi mahsulot bekor qilingani uchun {penalty_diff|floatformat:0} so'm jarima qo'llandi.")
            
        messages.success(request, f"'{item.product_name}' bekor qilindi.")
    else:
        messages.error(request, "Ushbu mahsulotni bekor qilib bo'lmaydi.")
        
    return redirect('order_detail', order_id=item.order.pk)


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
        status='delivered',
        buyer_confirmed=True
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
            # Check for buyer confirmation if setting to delivered
            if new_status == 'delivered' and not item.buyer_confirmed:
                messages.error(request, "Xaridor ushbu mahsulotni qabul qilganini tasdiqlashi kerak!")
            else:
                item.status = new_status
                item.save()
                
                if new_status == 'cancelled':
                    item.order.apply_penalty()
                
                # Notify buyer
                Notification.objects.create(
                    user=item.order.user,
                    message=f"'{item.product_name}' mahsulotingiz holati '{item.get_status_display()}' ga o'zgardi.",
                    target_url=f"/order/{item.order.pk}/"
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
def notifications_view(request):
    all_notifs = request.user.notifications.all()
    return render(request, 'main/notifications.html', {'notifications': all_notifs})

@login_required
def mark_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save()
    
    if notification.target_url:
        return redirect(notification.target_url)
    return redirect(request.META.get('HTTP_REFERER', 'seller_dashboard'))

# ────────── ADMIN DASHBOARD ──────────

def is_superuser(user):
    return user.is_authenticated and user.is_superuser

@user_passes_test(is_superuser)
def admin_dashboard(request):
    total_revenue = OrderItem.objects.exclude(status='cancelled').aggregate(total=Sum(F('price') * F('quantity')))['total'] or 0
    total_orders = Order.objects.count()
    total_users = User.objects.count()
    total_stores = Store.objects.count()
    
    pending_stores = Store.objects.filter(status='pending')
    all_stores = Store.objects.all().order_by('-created_at')
    all_products = Product.objects.all().order_by('-created_at')
    
    context = {
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'total_users': total_users,
        'total_stores': total_stores,
        'pending_stores': pending_stores,
        'all_stores': all_stores,
        'all_products': all_products,
    }
    return render(request, 'main/admin_dashboard.html', context)

@user_passes_test(is_superuser)
def admin_toggle_top(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    product.is_top = not product.is_top
    product.save()
    messages.success(request, f"'{product.name}' top holati o'zgartirildi.")
    return redirect('admin_dashboard')

@user_passes_test(is_superuser)
def admin_model_list(request, model_name):
    model_map = {
        'user': User,
        'store': Store,
        'category': Category,
        'product': Product,
        'order': Order,
        'review': Review,
        'notification': Notification,
        'brand': Brand,
        'region': Region,
    }
    
    if model_name not in model_map:
        messages.error(request, "Model topilmadi.")
        return redirect('admin_dashboard')
        
    model = model_map[model_name]
    queryset = model.objects.all().order_by('-pk')
    
    # Search logic
    search_query = request.GET.get('q', '')
    if search_query:
        if model_name == 'user':
            queryset = queryset.filter(username__icontains=search_query) | queryset.filter(phone__icontains=search_query)
        elif model_name in ['store', 'category', 'product']:
            queryset = queryset.filter(name__icontains=search_query)
        elif model_name == 'order':
            queryset = queryset.filter(id__icontains=search_query) | queryset.filter(user__username__icontains=search_query)
            
    return render(request, 'main/admin/model_list.html', {
        'model_name': model_name,
        'items': queryset,
        'search_query': search_query,
        'verbose_name': model._meta.verbose_name.capitalize(),
        'verbose_name_plural': model._meta.verbose_name_plural.capitalize(),
    })

@user_passes_test(is_superuser)
def admin_model_edit(request, model_name, pk=None):
    model_map = {
        'user': (User, UserAdminForm),
        'store': (Store, StoreForm),
        'category': (Category, CategoryForm),
        'product': (Product, ProductForm),
        'order': (Order, OrderAdminForm),
        'review': (Review, ReviewForm),
        'notification': (Notification, NotificationForm),
        'brand': (Brand, BrandForm),
        'region': (Region, RegionForm),
    }
    
    if model_name not in model_map:
        return redirect('admin_dashboard')
        
    model, form_class = model_map[model_name]
    instance = get_object_or_404(model, pk=pk) if pk else None
    
    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, f"{model._meta.verbose_name} saqlandi.")
            return redirect('admin_model_list', model_name=model_name)
    else:
        form = form_class(instance=instance)
        
    return render(request, 'main/admin/model_form.html', {
        'form': form,
        'model_name': model_name,
        'instance': instance,
        'verbose_name': model._meta.verbose_name.capitalize(),
    })

@user_passes_test(is_superuser)
def admin_model_delete(request, model_name, pk):
    model_map = {
        'user': User,
        'store': Store,
        'category': Category,
        'product': Product,
        'order': Order,
        'review': Review,
        'notification': Notification,
        'brand': Brand,
        'region': Region,
    }
    
    if model_name not in model_map:
        return redirect('admin_dashboard')
        
    obj = get_object_or_404(model_map[model_name], pk=pk)
    obj.delete()
    messages.success(request, f"{obj} o'chirildi.")
    return redirect('admin_model_list', model_name=model_name)

@user_passes_test(is_superuser)
def admin_store_status(request, store_id, status):
    store = get_object_or_404(Store, pk=store_id)
    if status in ['active', 'rejected', 'suspended']:
        store.status = status
        store.save()
        
        status_map = {
            'active': 'tasdiqlandi va faollashtirildi',
            'rejected': 'rad etildi',
            'suspended': 'vaqtinchalik to\'xtatildi'
        }
        msg = status_map.get(status)
        
        Notification.objects.create(
            user=store.owner,
            message=f"Sizning do'koningiz {msg}."
        )
        messages.success(request, f"Do'kon holati '{status}' ga o'zgartirildi.")
    return redirect('admin_dashboard')

@login_required
def confirm_store_receipt(request, order_id, store_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    items = order.items.filter(product__store_id=store_id)
    
    if not items.exists():
        messages.error(request, "Bu do'kondan mahsulot topilmadi.")
        return redirect('order_detail', order_id=order.pk)
        
    items.update(buyer_confirmed=True)
    
    # Check if all items in order are confirmed to update order level status
    if not order.items.filter(buyer_confirmed=False).exists():
        order.buyer_confirmed = True
        order.save(update_fields=['buyer_confirmed'])
    
    # Notify ONLY the relevant store owner
    store = get_object_or_404(Store, pk=store_id)
    Notification.objects.create(
        user=store.owner,
        message=f"#{order.pk} buyurtmadagi mahsulotlaringizni xaridor qabul qildi. Endi siz 'Yetkazildi' holatiga o'tkazishingiz mumkin.",
        target_url='/seller/orders/'
    )
    
    messages.success(request, f"'{store.name}' do'koni mahsulotlari qabul qilingani tasdiqlandi!")
    return redirect('order_detail', order_id=order.pk)

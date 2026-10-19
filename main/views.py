from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse, reverse_lazy
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json
import logging
from django.db import transaction, connection
from django.db.models import Sum, Count, Avg, F
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.translation import gettext, get_language
from datetime import timedelta
from .models import User, Product, Store, Category, Cart, CartItem, Order, OrderItem, Review, Notification, Brand, Region, NasiyaApplication
from .forms import UserRegisterForm, SellerRegisterForm, BuyerAuthForm, SellerAuthForm, AdminAuthForm, StoreForm, ProductForm, BuyerProfileForm, ReviewForm, CategoryForm, UserAdminForm, OrderAdminForm, NotificationForm, BrandForm, RegionForm, NasiyaApplicationForm, NasiyaAdminForm
from .nasiya import notify_managers
from .http_utils import safe_redirect
from .stock import restore_item_stock_once, InsufficientStock
from .ai_limits import rate_limited, sanitize_history, TEXT_MAX
from .roles import seller_required, admin_required, home_url, get_role, BUYER, SELLER, ADMIN

logger = logging.getLogger(__name__)
MAX_CART_QTY = 10000


@login_required
def role_home(request):
    """Kirgandan keyin: har bir rol o'z paneliga."""
    return redirect(home_url(request.user))


# ────────── AUTH: har bir rol uchun alohida portal ──────────

def register(request):
    """Xaridor ro'yxatdan o'tishi. Sotuvchilar /seller/register/ da."""
    if request.user.is_authenticated and get_role(request.user) == BUYER:
        return redirect('marketplace')
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('marketplace')
    else:
        form = UserRegisterForm()
    return render(request, 'main/auth_page.html', {
        'form': form,
        'title': gettext("Ro'yxatdan o'tish"),
        'subtitle': gettext("Xarid qilish uchun akkaunt yarating"),
        'submit_label': gettext("Ro'yxatdan o'tish"),
        'alt_text': gettext("Allaqachon akkauntingiz bormi?"),
        'alt_label': gettext("Kirish"),
        'alt_url': reverse('login'),
    })


class _PortalLogin(LoginView):
    """Rolga mos kirish sahifasi. Boshqa rolning akkaunti bu portalga kira olmaydi."""
    portal = BUYER
    redirect_authenticated_user = False
    template_name = 'main/auth_page.html'
    title = ''
    subtitle = ''
    alt_text = ''
    alt_label = ''
    alt_url_name = None

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and get_role(request.user) == self.portal:
            return redirect(home_url(request.user))
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return self.get_redirect_url() or home_url(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'title': self.title, 'subtitle': self.subtitle,
            'submit_label': gettext("Kirish"),
            'alt_text': self.alt_text, 'alt_label': self.alt_label,
            'alt_url': reverse(self.alt_url_name) if self.alt_url_name else '',
            'next': self.request.GET.get('next', ''),
        })
        return ctx


class BuyerLoginView(_PortalLogin):
    portal = BUYER
    authentication_form = BuyerAuthForm
    title = property(lambda self: gettext("Tizimga kirish"))
    subtitle = property(lambda self: gettext("Xaridor akkaunti"))
    alt_text = property(lambda self: gettext("Akkauntingiz yo'qmi?"))
    alt_label = property(lambda self: gettext("Ro'yxatdan o'ting"))
    alt_url_name = 'register'


class SellerLoginView(_PortalLogin):
    portal = SELLER
    authentication_form = SellerAuthForm
    template_name = 'main/portal/auth_page.html'
    title = property(lambda self: gettext("Sotuvchi kabiniga kirish"))
    subtitle = property(lambda self: gettext("Do'koningizni boshqaring"))
    alt_text = property(lambda self: gettext("Hali sotuvchi emasmisiz?"))
    alt_label = property(lambda self: gettext("Do'kon oching"))
    alt_url_name = 'seller_register'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({'portal_name': gettext("Sotuvchi portali"), 'show_buyer_link': True})
        return ctx


class AdminLoginView(_PortalLogin):
    portal = ADMIN
    authentication_form = AdminAuthForm
    template_name = 'main/portal/auth_page.html'
    title = property(lambda self: gettext("Admin paneliga kirish"))
    subtitle = ''

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({'portal_name': gettext("Admin panel"), 'show_buyer_link': False})
        return ctx


def seller_register(request):
    """Sotuvchi portalida ro'yxatdan o'tish (telefon va STIR/PINFL majburiy)."""
    if request.user.is_authenticated and get_role(request.user) == SELLER:
        return redirect('seller_dashboard')
    if request.method == 'POST':
        form = SellerRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('seller_dashboard')
    else:
        form = SellerRegisterForm()
    return render(request, 'main/portal/auth_page.html', {
        'form': form,
        'portal_name': gettext("Sotuvchi portali"),
        'title': gettext("Sotuvchi bo'lish"),
        'subtitle': gettext("Do'kon oching va mahsulotlaringizni soting"),
        'submit_label': gettext("Ro'yxatdan o'tish"),
        'alt_text': gettext("Akkauntingiz bormi?"),
        'alt_label': gettext("Kirish"),
        'alt_url': reverse('seller_login'),
        'show_buyer_link': True,
    })


class BuyerLogoutView(LogoutView):
    next_page = reverse_lazy('marketplace')


class SellerLogoutView(LogoutView):
    next_page = reverse_lazy('seller_login')


class AdminLogoutView(LogoutView):
    next_page = reverse_lazy('admin_login')


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
    if request.user.is_superuser:
        return redirect('admin_dashboard')
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
            messages.success(request, gettext("Ma'lumotlaringiz yangilandi!"))
            return redirect('buyer_profile')
    else:
        form = BuyerProfileForm(instance=request.user)
    cart = Cart.objects.filter(user=request.user).first()
    return render(request, 'main/buyer_profile.html', {'form': form, 'cart': cart})


@seller_required
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
            messages.success(request, gettext("Do'kon ma'lumotlari yangilandi!"))
            return redirect('seller_profile')
    else:
        form = StoreForm(instance=store)
    return render(request, 'main/seller_profile.html', {'form': form, 'store': store})


# ────────── SELLER DASHBOARD ──────────

@seller_required
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


@seller_required
def create_store(request):
    if not request.user.is_seller:
        return redirect('marketplace')
    if hasattr(request.user, 'store'):
        return redirect('seller_dashboard')
        
    # Check for missing info
    if not request.user.stir_pinfl or not request.user.phone:
        messages.warning(request, gettext("Do'kon ochishdan oldin STIR va telefon raqamingizni kiriting."))
        return redirect('seller_profile')
        
    if request.method == 'POST':
        form = StoreForm(request.POST, request.FILES)
        if form.is_valid():
            store = form.save(commit=False)
            store.owner = request.user
            store.save()
            form.save_m2m() # Save ManyToMany delivery_regions
            messages.success(request, gettext("Do'kon muvaffaqiyatli yaratildi va tasdiqlash uchun yuborildi."))
            return redirect('seller_dashboard')
    else:
        form = StoreForm()
    return render(request, 'main/store_form.html', {'form': form})


@seller_required
def add_product(request):
    if not request.user.is_seller or not hasattr(request.user, 'store'):
        return redirect('marketplace')
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.store = request.user.store
            product.save()
            messages.success(request, f"'{product.name}' muvaffaqiyatli qo'shildi!")
            return redirect('seller_dashboard')
    else:
        form = ProductForm()
    return render(request, 'main/product_form.html', {'form': form})


@seller_required
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk, store__owner=request.user)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"'{product.name}' muvaffaqiyatli tahrirlandi.")
            return redirect('seller_dashboard')
    else:
        form = ProductForm(instance=product)
    return render(request, 'main/product_form.html', {'form': form, 'edit': True, 'product': product})


@seller_required
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk, store__owner=request.user)
    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f"'{name}' o'chirildi.")
        return redirect('seller_dashboard')
    return render(request, 'main/product_confirm_delete.html', {'product': product})


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


def _parse_qty(raw, default=None):
    try:
        qty = int(raw)
    except (TypeError, ValueError):
        return None
    if qty > MAX_CART_QTY:
        return None
    return qty


@login_required
@require_POST
def add_to_cart(request, pk):
    if request.user.is_seller:
        messages.error(request, gettext("Sotuvchilar savat ishlatа olmaydi."))
        return redirect('product_detail', pk=pk)
    product = get_object_or_404(Product, pk=pk)
    if product.stock <= 0:
        messages.error(request, gettext("Bu mahsulot sotuvda yo'q."))
        return safe_redirect(request, 'cart')
    qty = _parse_qty(request.POST.get('quantity', 1))
    if qty is None or qty < 1:
        messages.error(request, gettext("Miqdor noto'g'ri. Musbat butun son kiriting."))
        return safe_redirect(request, 'cart')
    cart = _get_or_create_cart(request.user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    new_qty = qty if created else item.quantity + qty
    if new_qty > product.stock:
        messages.error(
            request,
            gettext("%(name)s: omborda faqat %(stock)s qolgan.") % {
                'name': product.display_name,
                'stock': product.stock,
            },
        )
        if created:
            item.delete()
        return safe_redirect(request, 'cart')
    item.quantity = new_qty
    item.save()
    messages.success(request, gettext("'%(name)s' savatga qo'shildi!") % {'name': product.display_name})
    return safe_redirect(request, 'cart')


@login_required
@require_POST
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    item.delete()
    messages.success(request, gettext("Mahsulot savatdan o'chirildi."))
    return redirect('cart')


@login_required
@require_POST
def update_cart(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    qty = _parse_qty(request.POST.get('quantity', 1))
    if qty is None:
        messages.error(request, gettext("Miqdor noto'g'ri. Musbat butun son kiriting."))
        return redirect('cart')
    if qty < 1:
        item.delete()
        messages.success(request, gettext("Mahsulot savatdan o'chirildi."))
        return redirect('cart')
    stock = item.product.stock
    if qty > stock:
        messages.error(
            request,
            gettext("%(name)s: omborda faqat %(stock)s qolgan.") % {
                'name': item.product.display_name,
                'stock': stock,
            },
        )
        return redirect('cart')
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
        messages.error(request, gettext("Savatda mahsulot yo'q!"))
        return redirect('cart')
    
    if request.method == 'POST':
        address = request.POST.get('address', '').strip()
        note = request.POST.get('note', '').strip()
        payment_method = request.POST.get('payment_method', 'card')

        nasiya_form = NasiyaApplicationForm(request.POST, prefix='nasiya')

        def _checkout_error(msg):
            messages.error(request, msg)
            return render(request, 'main/checkout.html', {
                'cart': cart,
                'items': items,
                'get_total_price': cart.get_total_price(),
                'nasiya_form': nasiya_form,
                'user_address': address,
                'selected_payment': payment_method,
            })

        if payment_method not in ('card', 'cash', 'nasiya'):
            return _checkout_error(gettext("To'lov turi noto'g'ri tanlangan!"))

        if not address:
            return _checkout_error(gettext("Yetkazib berish manzilini kiriting!"))

        # Nasiya tanlansa, ariza ma'lumotlari to'g'ri to'ldirilishi shart
        if payment_method == 'nasiya' and not nasiya_form.is_valid():
            return _checkout_error(gettext("Nasiya arizasidagi ma'lumotlarni to'g'ri to'ldiring!"))

        try:
            with transaction.atomic():
                locked_rows = []
                sellers_to_notify = set()
                for item in items.select_related('product', 'product__store'):
                    product = Product.objects.select_for_update().get(pk=item.product_id)
                    if product.stock < item.quantity:
                        raise InsufficientStock(product)
                    locked_rows.append((item, product))
                    if product.store_id:
                        sellers_to_notify.add(product.store.owner_id)

                order = Order.objects.create(
                    user=request.user,
                    address=address,
                    note=note,
                    payment_method=payment_method,
                    status='pending'
                )
                for item, product in locked_rows:
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        product_name=product.name,
                        price=product.price,
                        quantity=item.quantity
                    )
                    Product.objects.filter(pk=product.pk).update(
                        stock=F('stock') - item.quantity
                    )

                cart.items.all().delete()

                application = None
                if payment_method == 'nasiya':
                    application = nasiya_form.save(commit=False)
                    application.order = order
                    application.save()

                order_id = order.pk
                app_id = application.pk if application else None
                seller_ids = list(sellers_to_notify)

                def _notify_after_commit():
                    try:
                        for seller_id in seller_ids:
                            Notification.objects.create(
                                user_id=seller_id,
                                message=gettext("Yangi buyurtma! #%(n)s raqamli buyurtmada sizning mahsulotingiz bor.") % {'n': order_id},
                                target_url='/seller/orders/'
                            )
                        if app_id:
                            notify_managers(NasiyaApplication.objects.get(pk=app_id))
                    except Exception:
                        logger.exception("Buyurtma bildirishnomasini yuborib bo'lmadi")

                if connection.savepoint_ids:
                    _notify_after_commit()
                else:
                    transaction.on_commit(_notify_after_commit)
        except InsufficientStock as exc:
            return _checkout_error(
                gettext("%(name)s: omborda faqat %(stock)s qolgan. Buyurtma yaratilmadi.") % {
                    'name': exc.product.display_name,
                    'stock': exc.product.stock,
                }
            )

        if payment_method == 'nasiya':
            messages.success(
                request,
                gettext("Buyurtma va nasiya arizangiz qabul qilindi! Menejerimiz tez orada telefon orqali bog'lanadi.")
            )
        else:
            messages.success(request, gettext("Buyurtma muvaffaqiyatli qabul qilindi! Sotuvchilar xabardor qilindi."))
        return redirect('order_detail', order_id=order_id)

    return render(request, 'main/checkout.html', {
        'cart': cart,
        'items': items,
        'get_total_price': cart.get_total_price(),
        'user_address': request.user.address,
        'nasiya_form': NasiyaApplicationForm(
            prefix='nasiya',
            initial={
                'full_name': request.user.get_full_name(),
                'phone': request.user.phone,
            },
        ),
        'selected_payment': 'card',
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
    # Mahsulot yoki do'kon o'chirilgan bo'lishi mumkin (product=SET_NULL): sahifa qulamasin.
    stores_data = {}
    for item in order.items.all().select_related('product__store'):
        store = item.product.store if item.product_id and item.product else None
        key = store.pk if store else 0
        if key not in stores_data:
            stores_data[key] = {
                'store': store or {'name': gettext("Do'kon mavjud emas"), 'pk': None},
                'items': [],
                'all_confirmed': True,
                'can_confirm': False
            }
        stores_data[key]['items'].append(item)
        if not item.buyer_confirmed:
            stores_data[key]['all_confirmed'] = False
            if store and item.status in ['shipped', 'delivered']:
                stores_data[key]['can_confirm'] = True
                
    return render(request, 'main/order_detail.html', {
        'order': order, 
        'stores_data': stores_data.values()
    })


@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    # Allow cancellation if entire order is pending OR if it's confirmed but has pending items
    pending_items = list(order.items.filter(status='pending').select_related('product', 'product__store'))
    
    if order.status in ['pending', 'confirmed'] and pending_items:
        cancelled_any = False
        for item in pending_items:
            if restore_item_stock_once(item):
                cancelled_any = True
                # Notify seller
                if item.product and item.product.store:
                    Notification.objects.create(
                        user=item.product.store.owner,
                        message=gettext("#%(order_id)s buyurtmadagi '%(name)s' mahsuloti xaridor tomonidan bekor qilindi.") % {
                            'order_id': order.pk,
                            'name': item.product_name,
                        },
                        target_url='/seller/orders/'
                    )
                
                # Apply penalty for each pending item being cancelled
                old_penalty = order.penalty_amount
                order.apply_penalty(item=item)
                if order.penalty_amount > old_penalty:
                    penalty_diff = order.penalty_amount - old_penalty
                    messages.warning(
                        request,
                        gettext("Naqd puldagi buyurtma bekor qilingani uchun %(amount)s so'm jarima qo'llandi.") % {
                            'amount': f"{penalty_diff:,.0f}"
                        }
                    )
        
        if cancelled_any:
            order.refresh_from_db()
            if order.status == 'cancelled' and order.payment_method == 'cash':
                order.apply_penalty()
            messages.success(request, gettext("Kutilayotgan mahsulotlar bekor qilindi."))
        else:
            messages.error(request, gettext("Bu buyurtmani bekor qilib bo'lmaydi yoki kutilayotgan mahsulotlar yo'q."))
    else:
        messages.error(request, gettext("Bu buyurtmani bekor qilib bo'lmaydi yoki kutilayotgan mahsulotlar yo'q."))
        
    return redirect('order_detail', order_id=order.pk)


@login_required
def cancel_order_item(request, item_id):
    item = get_object_or_404(OrderItem, pk=item_id, order__user=request.user)
    if item.status == 'pending':
        if restore_item_stock_once(item):
            # Notify seller
            if item.product and item.product.store:
                Notification.objects.create(
                    user=item.product.store.owner,
                    message=gettext("#%(order_id)s buyurtmadagi '%(name)s' mahsuloti xaridor tomonidan bekor qilindi.") % {
                        'order_id': item.order.pk,
                        'name': item.product_name,
                    },
                    target_url='/seller/orders/'
                )
                
            old_penalty = item.order.penalty_amount
            item.order.apply_penalty(item=item)
            if item.order.penalty_amount > old_penalty:
                penalty_diff = item.order.penalty_amount - old_penalty
                messages.warning(
                    request,
                    gettext("Naqd puldagi mahsulot bekor qilingani uchun %(amount)s so'm jarima qo'llandi.") % {
                        'amount': f"{penalty_diff:,.0f}"
                    }
                )
                
            messages.success(request, gettext("'%(name)s' bekor qilindi.") % {'name': item.product_name})
        else:
            messages.error(request, gettext("Ushbu mahsulotni bekor qilib bo'lmaydi."))
    else:
        messages.error(request, gettext("Ushbu mahsulotni bekor qilib bo'lmaydi."))
        
    return redirect('order_detail', order_id=item.order.pk)


# ────────── REVIEWS ──────────

@login_required
def add_review(request, pk):
    if request.user.is_seller:
        messages.error(request, gettext("Sotuvchilar fikr bildira olmaydi."))
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
        messages.error(request, gettext("Fikr bildirish uchun avval bu mahsulotni sotib olishingiz va u yetkazib berilishi kerak!"))
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

@seller_required
def add_review_reply(request, review_id):
    review = get_object_or_404(Review, pk=review_id, product__store__owner=request.user)
    
    if request.method == 'POST':
        reply_text = request.POST.get('reply_text', '').strip()
        if reply_text:
            review.seller_reply = reply_text
            import django.utils.timezone as timezone
            review.replied_at = timezone.now()
            review.save()
            messages.success(request, gettext("Javobingiz muvaffaqiyatli saqlandi!"))
        else:
            messages.error(request, gettext("Javob matnini kiriting."))
            
    return redirect('seller_reviews')

@seller_required
def seller_reviews(request):
    if not request.user.is_seller:
        return redirect('marketplace')
    
    # Get all reviews for products owned by this seller
    reviews = Review.objects.filter(product__store__owner=request.user).order_by('-created_at')
    
    return render(request, 'main/seller_reviews.html', {'reviews': reviews})

@seller_required
def update_order_item_status(request, item_id):
    item = get_object_or_404(OrderItem, pk=item_id, product__store__owner=request.user)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(OrderItem.STATUS_CHOICES):
            # Check for buyer confirmation if setting to delivered
            if new_status == 'delivered' and not item.buyer_confirmed:
                messages.error(request, gettext("Xaridor ushbu mahsulotni qabul qilganini tasdiqlashi kerak!"))
            elif new_status == 'cancelled':
                # Sotuvchi bekor qilsa zaxira qaytariladi va xaridor JARIMA olmaydi.
                if restore_item_stock_once(item):
                    Notification.objects.create(
                        user=item.order.user,
                        message=f"'{item.product_name}' mahsuloti sotuvchi tomonidan bekor qilindi.",
                        target_url=f"/order/{item.order.pk}/"
                    )
                    messages.success(request, gettext("Mahsulot bekor qilindi, zaxira qaytarildi."))
                else:
                    messages.error(request, gettext("Faqat kutilayotgan mahsulotni bekor qilish mumkin."))
            else:
                item.status = new_status
                item.save()

                # Notify buyer
                Notification.objects.create(
                    user=item.order.user,
                    message=f"'{item.product_name}' mahsulotingiz holati '{item.get_status_display()}' ga o'zgardi.",
                    target_url=f"/order/{item.order.pk}/"
                )
                messages.success(request, f"Status '{item.get_status_display()}' ga o'zgartirildi.")
            
    return redirect('seller_orders')

@seller_required
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

@seller_required
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
    return render(request, 'main/notifications.html', {'notifications': all_notifs, 'is_panel': get_role(request.user) != BUYER})

@login_required
def mark_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save()
    
    if notification.target_url:
        return redirect(notification.target_url)
    return redirect(request.META.get('HTTP_REFERER') or home_url(request.user))

# ────────── ADMIN DASHBOARD ──────────

def _admin_models():
    """Admin panelda boshqariladigan modellar: nom -> (Model, Form)."""
    return {
        'user': (User, UserAdminForm),
        'store': (Store, StoreForm),
        'category': (Category, CategoryForm),
        'product': (Product, ProductForm),
        'order': (Order, OrderAdminForm),
        'review': (Review, ReviewForm),
        'notification': (Notification, NotificationForm),
        'brand': (Brand, BrandForm),
        'region': (Region, RegionForm),
        'nasiya': (NasiyaApplication, NasiyaAdminForm),
    }


def is_superuser(user):
    return user.is_authenticated and user.is_superuser

@admin_required
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

@admin_required
def admin_toggle_top(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    product.is_top = not product.is_top
    product.save()
    messages.success(request, f"'{product.name}' top holati o'zgartirildi.")
    return redirect('admin_dashboard')

@admin_required
def admin_model_list(request, model_name):
    model_map = _admin_models()
    
    if model_name not in model_map:
        messages.error(request, gettext("Model topilmadi."))
        return redirect('admin_dashboard')
        
    model = model_map[model_name][0]
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

@admin_required
def admin_model_edit(request, model_name, pk=None):
    model_map = _admin_models()
    
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

@admin_required
def admin_model_delete(request, model_name, pk):
    model_map = _admin_models()
    
    if model_name not in model_map:
        return redirect('admin_dashboard')
        
    obj = get_object_or_404(model_map[model_name][0], pk=pk)
    obj.delete()
    messages.success(request, f"{obj} o'chirildi.")
    return redirect('admin_model_list', model_name=model_name)

@admin_required
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
        messages.error(request, gettext("Bu do'kondan mahsulot topilmadi."))
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


# ────────── ANORA AI CHAT ──────────

@require_POST
def ai_chat(request):
    """AJAX endpoint for Anora AI yordamchi (UZ/RU/EN)."""
    lang = (get_language() or 'uz')[:2]
    from .anora_fallback import find_fallback
    try:
        data = json.loads(request.body)
        message = data.get('message', '')
        if not isinstance(message, str):
            return JsonResponse({'success': False, 'response': gettext("Noto'g'ri so'rov formati.")})
        message = message.strip()
        raw_history = data.get('history', [])

        if not message:
            return JsonResponse({'success': False, 'response': gettext('Xabar kiriting.')})

        if len(message) > TEXT_MAX:
            return JsonResponse({'success': False, 'response': gettext('Xabar juda uzun. 1000 belgidan oshmasin.')})

        if rate_limited(request):
            return JsonResponse({
                'success': False,
                'response': gettext("So'rovlar soni juda ko'p. Iltimos, bir daqiqadan so'ng qayta urinib ko'ring.")
            }, status=429)

        chat_history = sanitize_history(raw_history)

        from .ai_assistant import get_ai_response
        result = get_ai_response(request.user, message, chat_history, language=lang)
        if result.get('success'):
            return JsonResponse(result)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'response': gettext("Noto'g'ri so'rov formati.")})
    except Exception as exc:
        logger.exception("Anora AI xatosi: %s", type(exc).__name__)
        message = locals().get('message', '')

    # Gemini javob bermadi: avval qo'lda yozilgan javob, bo'lmasa umumiy xabar
    manual = find_fallback(message, lang)
    if manual:
        return JsonResponse({'success': True, 'response': manual, 'source': 'manual'})
    return JsonResponse({'success': False, 'response': gettext("Hozir javob bera olmayman. Birozdan so'ng qayta urinib ko'ring.")})

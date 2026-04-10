"""
Anora — ArzonMaterial AI Yordamchi
Gemini API orqali foydalanuvchilarga yordam beradi.
"""
import json
import logging
from django.conf import settings
from django.db.models import Sum, Avg, Count, F, Min, Max

logger = logging.getLogger(__name__)

# Lazy-init client
_client = None

def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


ANORA_SYSTEM_PROMPT = """Sen "Anora" — ArzonMaterial qurilish materiallari onlayn marketplace saytining AI yordamchisisan.

## Sening shaxsiyating:
- Isming: **Anora**
- Vazifang: Foydalanuvchilarga sayt bo'yicha yordam berish
- Tilingni: O'zbek tilida gaplash (lekin foydalanuvchi boshqa tilda yozsa, o'sha tilda javob ber)
- Uslub: Samimiy, do'stona, professional. Qisqa va aniq javoblar ber.
- Emojidan foydalanishing mumkin, lekin ortiqcha ishlatma.

## ArzonMaterial haqida:
- Bu qurilish materiallari onlayn bozori (marketplace)
- Sotuvchilar do'kon ochib mahsulot sotadi
- Xaridorlar mahsulotlarni qidiradi, savatga qo'shadi va buyurtma beradi
- To'lov turlari: Karta va Naqd pul
- Yetkazib berish bepul
- Sayt manzili: ArzonMaterial.uz

## Asosiy sahifalar:
- **Bozor** (/) — barcha mahsulotlar ro'yxati, filter va qidiruv
- **Profil** (/profile/) — foydalanuvchi ma'lumotlari
- **Savat** (/cart/) — tanlangan mahsulotlar
- **Buyurtmalarim** (/orders/) — buyurtmalar tarixi
- **Sotuvchi kabineti** (/dashboard/) — sotuvchilar uchun
- **Statistika** (/seller/statistics/) — sotuvlar statistikasi

## Qoidalar:
1. Saytga aloqador bo'lmagan savollarga qisqacha javob berib, sayt mavzusiga qaytish.
2. Mahsulot narxlari va ma'lumotlarini FAQAT kontekstda berilgan ma'lumotlar asosida ayt.
3. Agar biror narsani bilmasang, to'g'ridan-to'g'ri ayting.
4. Hech qachon soxta narx yoki mahsulot to'qima.
5. Foydalanuvchiga doim "siz" deb murojaat qil.
"""


def _get_buyer_context(user):
    """Xaridor uchun kontekst ma'lumotlarini yig'ish."""
    from .models import Product, Category, Order, Brand, Region

    context_parts = []

    # Kategoriyalar
    categories = list(Category.objects.values_list('name', flat=True))
    if categories:
        context_parts.append(f"📂 Mavjud toifalar: {', '.join(categories)}")

    # Brendlar
    brands = list(Brand.objects.values_list('name', flat=True))
    if brands:
        context_parts.append(f"🏷️ Brendlar: {', '.join(brands)}")

    # Hududlar
    regions = list(Region.objects.values_list('name', flat=True))
    if regions:
        context_parts.append(f"📍 Yetkazib berish hududlari: {', '.join(regions)}")

    # Eng arzon 5 ta mahsulot
    cheapest = Product.objects.filter(store__status='active', stock__gt=0).order_by('price')[:5]
    if cheapest:
        lines = []
        for p in cheapest:
            lines.append(f"  - {p.name} — {p.price:,.0f} so'm ({p.store.name})")
        context_parts.append("💰 Eng arzon mahsulotlar:\n" + "\n".join(lines))

    # Eng qimmat 5 ta mahsulot
    expensive = Product.objects.filter(store__status='active', stock__gt=0).order_by('-price')[:5]
    if expensive:
        lines = []
        for p in expensive:
            lines.append(f"  - {p.name} — {p.price:,.0f} so'm ({p.store.name})")
        context_parts.append("💎 Eng qimmat mahsulotlar:\n" + "\n".join(lines))

    # Top mahsulotlar
    top_products = Product.objects.filter(is_top=True, store__status='active')[:5]
    if top_products:
        lines = [f"  - {p.name} — {p.price:,.0f} so'm" for p in top_products]
        context_parts.append("⭐ Top mahsulotlar:\n" + "\n".join(lines))

    # Eng yuqori reyting
    best_rated = Product.objects.filter(store__status='active').annotate(
        avg_r=Avg('reviews__rating'), r_count=Count('reviews')
    ).filter(r_count__gt=0).order_by('-avg_r')[:5]
    if best_rated:
        lines = [f"  - {p.name} — {p.avg_r:.1f}⭐ ({p.r_count} sharh)" for p in best_rated]
        context_parts.append("🌟 Eng yaxshi baholangan:\n" + "\n".join(lines))

    # Narx diapazoni
    price_info = Product.objects.filter(store__status='active', stock__gt=0).aggregate(
        min_price=Min('price'), max_price=Max('price')
    )
    if price_info['min_price']:
        context_parts.append(
            f"📊 Narx diapazoni: {price_info['min_price']:,.0f} — {price_info['max_price']:,.0f} so'm"
        )

    # Umumiy mahsulotlar soni
    total = Product.objects.filter(store__status='active').count()
    context_parts.append(f"📦 Jami aktiv mahsulotlar soni: {total}")

    # Foydalanuvchi buyurtmalari
    if user.is_authenticated:
        user_orders = Order.objects.filter(user=user).count()
        if user_orders:
            context_parts.append(f"🛒 Sizning buyurtmalaringiz soni: {user_orders}")

    return "\n\n".join(context_parts)


def _get_seller_context(user):
    """Sotuvchi uchun kontekst ma'lumotlarini yig'ish."""
    from .models import Product, OrderItem, Review
    from django.utils import timezone
    from datetime import timedelta

    context_parts = []

    if not hasattr(user, 'store'):
        context_parts.append("⚠️ Siz hali do'kon ochmadingiz. Do'kon ochish uchun /create-store/ sahifasiga boring.")
        return "\n\n".join(context_parts)

    store = user.store
    context_parts.append(f"🏪 Do'koningiz: {store.name} (Holati: {store.get_status_display()})")

    # Mahsulotlar
    products = store.products.all()
    context_parts.append(f"📦 Jami mahsulotlar: {products.count()}")

    # Stock 0 bo'lganlar
    out_of_stock = products.filter(stock=0).count()
    if out_of_stock:
        context_parts.append(f"⚠️ Tugagan mahsulotlar: {out_of_stock} ta")

    # So'nggi 30 kunlik sotuvlar
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_items = OrderItem.objects.filter(
        product__store=store,
        order__created_at__gte=thirty_days_ago
    ).exclude(status='cancelled')

    total_revenue = recent_items.aggregate(
        total=Sum(F('price') * F('quantity'))
    )['total'] or 0
    total_sold = recent_items.aggregate(total=Sum('quantity'))['total'] or 0
    total_orders = recent_items.values('order').distinct().count()

    context_parts.append(f"💰 So'nggi 30 kun: {total_revenue:,.0f} so'm daromad")
    context_parts.append(f"📊 {total_sold} ta mahsulot sotildi, {total_orders} ta buyurtma")

    # Bugungi sotuvlar
    today = timezone.now().date()
    today_items = OrderItem.objects.filter(
        product__store=store,
        order__created_at__date=today
    ).exclude(status='cancelled')
    today_revenue = today_items.aggregate(
        total=Sum(F('price') * F('quantity'))
    )['total'] or 0
    today_sold = today_items.aggregate(total=Sum('quantity'))['total'] or 0
    context_parts.append(f"📅 Bugun: {today_revenue:,.0f} so'm, {today_sold} ta sotildi")

    # Kutilayotgan buyurtmalar
    pending_count = OrderItem.objects.filter(
        product__store=store, status='pending'
    ).count()
    if pending_count:
        context_parts.append(f"🔔 Kutilayotgan buyurtmalar: {pending_count} ta")

    # Sharhlar
    review_stats = Review.objects.filter(product__store=store).aggregate(
        avg_rating=Avg('rating'), total_reviews=Count('id')
    )
    if review_stats['total_reviews']:
        context_parts.append(
            f"⭐ Sharhlar: O'rtacha {review_stats['avg_rating']:.1f}/5 ({review_stats['total_reviews']} ta)"
        )

    # Top 3 eng ko'p sotilgan
    top_selling = OrderItem.objects.filter(
        product__store=store
    ).exclude(status='cancelled').values('product__name').annotate(
        total_qty=Sum('quantity')
    ).order_by('-total_qty')[:3]
    if top_selling:
        lines = [f"  - {item['product__name']} ({item['total_qty']} dona)" for item in top_selling]
        context_parts.append("🏆 Eng ko'p sotilgan:\n" + "\n".join(lines))

    return "\n\n".join(context_parts)


def get_ai_response(user, message, chat_history=None):
    """Gemini API ga so'rov yuborish va javob olish."""
    try:
        client = _get_client()

        # Rolga qarab kontekst
        if user.is_authenticated and user.is_seller:
            role_label = "Sotuvchi"
            context = _get_seller_context(user)
            role_instructions = """
Foydalanuvchi SOTUVCHI. Unga quyidagilar bo'yicha yordam ber:
- Sotuvlar statistikasi va daromad haqida
- Mahsulot qo'shish qadamlari: /add-product/ sahifasiga borib, nomi, toifa, narx, soni kiritish
- Do'kon rasmiylashtirilishi: STIR/PINFL kiritish kerak, admin tasdiqlaydi
- Buyurtmalarni boshqarish: /seller/orders/ sahifasida status o'zgartirish
- Sharhlarni ko'rish va javob berish: /seller/reviews/ sahifasida
- Statistikani ko'rish: /seller/statistics/ sahifasida
"""
        elif user.is_authenticated:
            role_label = "Xaridor"
            context = _get_buyer_context(user)
            role_instructions = """
Foydalanuvchi XARIDOR. Unga quyidagilar bo'yicha yordam ber:
- Mahsulot qidirish va filtrlash
- Savatga qo'shish va buyurtma berish jarayoni
- Eng arzon/eng qimmat/eng yaxshi mahsulotlarni topish
- Buyurtma holati haqida
- Profil sozlamalari
"""
        else:
            role_label = "Mehmon"
            context = _get_buyer_context(user)
            role_instructions = """
Foydalanuvchi MEHMON (tizimga kirmagan). Unga quyidagilar bo'yicha yordam ber:
- Sayt haqida umumiy ma'lumot
- Ro'yxatdan o'tish: /register/ sahifasida
- Kirish: /login/ sahifasida
- Mahsulotlar haqida umumiy ma'lumot
"""

        # System prompt + kontekst
        full_system = f"""{ANORA_SYSTEM_PROMPT}

## Hozirgi foydalanuvchi: {role_label}
{'' if not user.is_authenticated else f'Ismi: {user.get_full_name() or user.username}'}

{role_instructions}

## Hozirgi ma'lumotlar bazasi konteksti:
{context}
"""

        # Chat history ni tayyorlash
        contents = []
        if chat_history:
            for msg in chat_history[-10:]:  # oxirgi 10 ta xabar
                contents.append({
                    "role": msg["role"],
                    "parts": [{"text": msg["text"]}]
                })

        # Foydalanuvchi xabarini qo'shish
        contents.append({
            "role": "user",
            "parts": [{"text": message}]
        })

        # Try models in order of preference
        models_to_try = [
            "gemini-2.0-flash", 
            "gemini-flash-latest",
            "gemini-1.5-flash-latest",
            "gemini-2.0-flash-lite"
        ]
        last_error = None

        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config={
                        "system_instruction": full_system,
                        "temperature": 0.7,
                        "max_output_tokens": 1024,
                    }
                )
                return {
                    "success": True,
                    "response": response.text
                }
            except Exception as model_error:
                last_error = model_error
                logger.warning(f"Anora: {model_name} xatosi: {model_error}")
                continue

        # All models failed
        raise last_error

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Anora AI xatosi: {e}")

        if '429' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg:
            return {
                "success": False,
                "response": "Hozir so'rovlar ko'p bo'lgani uchun javob bera olmayapman. Iltimos, 1 daqiqadan keyin qayta urinib ko'ring."
            }
        elif '503' in error_msg or 'UNAVAILABLE' in error_msg:
            return {
                "success": False,
                "response": "AI server hozir band. Iltimos, bir ozdan keyin qayta urinib ko'ring."
            }
        return {
            "success": False,
            "response": "Kechirasiz, texnik nosozlik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring."
        }

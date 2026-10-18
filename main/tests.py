from unittest import mock
from django.test import TestCase
from django.urls import reverse
from .models import User, Store, Product, Cart, CartItem, Order, OrderItem, NasiyaApplication, Notification


class NasiyaCheckoutTests(TestCase):
    def setUp(self):
        seller = User.objects.create_user('sotuvchi', password='x', is_seller=True)
        store = Store.objects.create(owner=seller, name='Test do\'kon', status='active')
        self.product = Product.objects.create(store=store, name='Sement', price=50000, stock=100)
        self.manager = User.objects.create_superuser('menejer', password='x')
        self.buyer = User.objects.create_user('xaridor', password='x', is_buyer=True)
        cart = Cart.objects.create(user=self.buyer)
        CartItem.objects.create(cart=cart, product=self.product, quantity=4)
        self.client.login(username='xaridor', password='x')

    def _post(self, **extra):
        data = {'payment_method': 'nasiya', 'address': 'Toshkent, Chilonzor',
                'nasiya-full_name': 'Aliyev Vali', 'nasiya-phone': '90 123 45 67',
                'nasiya-term_months': '6'}
        data.update(extra)
        return self.client.post(reverse('checkout'), data)

    def test_valid_nasiya_creates_application_and_notifies_manager(self):
        resp = self._post()
        self.assertEqual(resp.status_code, 302)
        app = NasiyaApplication.objects.get()
        self.assertEqual(app.phone, '+998901234567')
        self.assertEqual(app.order.payment_method, 'nasiya')
        self.assertEqual(app.monthly_payment, round(200000 / 6))
        self.assertTrue(Notification.objects.filter(user=self.manager).exists())

    def test_invalid_phone_creates_nothing(self):
        self._post(**{'nasiya-phone': '123'})
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(NasiyaApplication.objects.count(), 0)

    def test_telegram_failure_does_not_break_order(self):
        with self.settings(TELEGRAM_BOT_TOKEN='t', TELEGRAM_MANAGER_CHAT_ID='1'), \
                mock.patch('main.nasiya.requests.post', side_effect=Exception('down')):
            resp = self._post()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Order.objects.count(), 1)

    def test_unknown_payment_method_rejected(self):
        self._post(payment_method='bitcoin')
        self.assertEqual(Order.objects.count(), 0)


class PagesRenderTests(TestCase):
    """Dizayn o'zgarganda shablonlar buzilmaganini tekshiradi."""
    def setUp(self):
        seller = User.objects.create_user('s', password='x', is_seller=True)
        store = Store.objects.create(owner=seller, name="Do'kon", status='active')
        self.p1 = Product.objects.create(store=store, name='Sement M400', price=65000, stock=10, is_top=True)
        self.p2 = Product.objects.create(store=store, name='Laminat', price=450000, stock=0)

    def test_marketplace_anonymous_and_search(self):
        r = self.client.get(reverse('marketplace'))
        self.assertContains(r, 'Sement M400')
        self.assertContains(r, 'Tugagan')
        self.assertContains(r, 'Nasiya: ~75000')       # 450000 / 6
        r = self.client.get(reverse('marketplace'), {'q': 'sement'})
        self.assertContains(r, 'natijalar')
        r = self.client.get(reverse('marketplace'), {'q': 'yoq-narsa'})
        self.assertContains(r, 'Hech narsa topilmadi')

    def test_other_pages_render(self):
        for name in ('login', 'register'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(self.client.get(reverse('product_detail', args=[self.p1.pk])).status_code, 200)
        buyer = User.objects.create_user('b', password='x', is_buyer=True)
        self.client.login(username='b', password='x')
        Cart.objects.create(user=buyer)
        for name in ('cart', 'orders', 'notifications'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)


class ThemeToggleTests(TestCase):
    def test_toggle_and_init_script_present(self):
        r = self.client.get(reverse('marketplace'))
        self.assertContains(r, 'id="theme-toggle"')
        self.assertContains(r, "localStorage.getItem('theme')")


class I18nTests(TestCase):
    def setUp(self):
        seller = User.objects.create_user('s2', password='x', is_seller=True)
        store = Store.objects.create(owner=seller, name="Do'kon", status='active')
        self.p = Product.objects.create(store=store, name='Sement', price=65000, stock=0,
                                        name_ru='Цемент', description='Yaxshi sement', description_en='Good cement')

    def _lang(self, code):
        self.client.post(reverse('set_language'), {'language': code, 'next': '/'})

    def test_interface_switches_language(self):
        r = self.client.get(reverse('marketplace'))
        self.assertContains(r, 'Tugagan')
        self._lang('ru')
        r = self.client.get(reverse('marketplace'))
        self.assertContains(r, 'Нет в наличии')
        self.assertContains(r, '<html lang="ru"')
        self._lang('en')
        r = self.client.get(reverse('marketplace'))
        self.assertContains(r, 'Sold out')
        self.assertNotContains(r, 'Tugagan')

    def test_all_public_pages_render_in_every_language(self):
        for code in ('uz', 'ru', 'en'):
            self._lang(code)
            for name in ('marketplace', 'login', 'register'):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200, (code, name))
            self.assertEqual(self.client.get(reverse('product_detail', args=[self.p.pk])).status_code, 200)

    def test_product_text_falls_back_to_uzbek(self):
        from django.utils import translation
        with translation.override('ru'):
            self.assertEqual(self.p.display_name, 'Цемент')
            self.assertEqual(self.p.display_description, 'Yaxshi sement')   # ruscha tavsif yo'q
        with translation.override('en'):
            self.assertEqual(self.p.display_name, 'Sement')                 # inglizcha nom yo'q
            self.assertEqual(self.p.display_description, 'Good cement')

    def test_anora_gets_language_and_manual_fallback(self):
        from .models import AnoraFallback
        AnoraFallback.objects.create(title='Yetkazish', keywords='yetkazib, доставка, delivery',
                                     answer_uz='Yetkazish 1-3 kun.', answer_ru='Доставка 1-3 дня.')
        self._lang('ru')
        failed = {'success': False, 'response': 'xato'}
        with mock.patch('main.ai_assistant.get_ai_response', return_value=failed) as m:
            r = self.client.post(reverse('ai_chat'), '{"message": "Как работает доставка?"}',
                                 content_type='application/json')
        self.assertEqual(m.call_args.kwargs['language'], 'ru')
        self.assertEqual(r.json()['response'], 'Доставка 1-3 дня.')
        with mock.patch('main.ai_assistant.get_ai_response', return_value=failed):
            r = self.client.post(reverse('ai_chat'), '{"message": "salom"}', content_type='application/json')
        self.assertFalse(r.json()['success'])
        self.assertIn('Сейчас я не могу ответить', r.json()['response'])


from decimal import Decimal
from django.core.cache import cache
from django.test import Client, TransactionTestCase
from main.ai_limits import sanitize_history


class StockAndOrderSecurityTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user('seller_sec', password='x', is_seller=True)
        self.store = Store.objects.create(owner=self.seller, name='Sec Store', status='active')
        self.product = Product.objects.create(store=self.store, name='Gips', price=100000, stock=5)
        self.buyer = User.objects.create_user('buyer_sec', password='x', is_buyer=True)
        self.other_buyer = User.objects.create_user('other_buyer', password='x', is_buyer=True)
        self.cart = Cart.objects.create(user=self.buyer)
        self.client.login(username='buyer_sec', password='x')

    def test_order_exceeding_stock_rejected_stock_and_cart_unchanged(self):
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=10)
        resp = self.client.post(reverse('checkout'), {
            'payment_method': 'card',
            'address': 'Toshkent',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(CartItem.objects.filter(cart=self.cart).count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_successful_order_reduces_stock_and_cancel_restores_once(self):
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)
        resp = self.client.post(reverse('checkout'), {
            'payment_method': 'card',
            'address': 'Toshkent',
        })
        self.assertEqual(resp.status_code, 302)
        order = Order.objects.get(user=self.buyer)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

        # Cancel order
        self.client.get(reverse('cancel_order', args=[order.pk]))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

        # Cancel order again - stock must NOT increase again
        self.client.get(reverse('cancel_order', args=[order.pk]))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

        # Cancel item individually - stock must NOT increase again
        item = order.items.first()
        self.client.get(reverse('cancel_order_item', args=[item.pk]))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_cash_cancel_penalty_thresholds(self):
        # Order < 1,000,000 -> 100,000 penalty
        order_small = Order.objects.create(user=self.buyer, payment_method='cash', status='pending')
        OrderItem.objects.create(order=order_small, product=self.product, product_name='P', price=300000, quantity=1)
        order_small.status = 'cancelled'
        order_small.apply_penalty()
        self.assertEqual(order_small.penalty_amount, Decimal('100000'))

        # Order >= 1,000,000 -> 10% penalty
        order_large = Order.objects.create(user=self.buyer, payment_method='cash', status='pending')
        OrderItem.objects.create(order=order_large, product=self.product, product_name='P', price=2000000, quantity=1)
        order_large.status = 'cancelled'
        order_large.apply_penalty()
        self.assertEqual(order_large.penalty_amount, Decimal('200000'))

    def test_user_cannot_view_other_users_order(self):
        order = Order.objects.create(user=self.buyer, payment_method='card', status='pending')
        self.client.login(username='other_buyer', password='x')
        resp = self.client.get(reverse('order_detail', args=[order.pk]))
        self.assertEqual(resp.status_code, 404)


class CartSecurityTests(TestCase):
    def setUp(self):
        seller = User.objects.create_user('seller_c', password='x', is_seller=True)
        store = Store.objects.create(owner=seller, name='C Store', status='active')
        self.product = Product.objects.create(store=store, name='Beton', price=50000, stock=20)
        self.buyer = User.objects.create_user('buyer_c', password='x', is_buyer=True)
        self.cart = Cart.objects.create(user=self.buyer)
        self.client.login(username='buyer_c', password='x')

    def test_add_to_cart_get_returns_405(self):
        resp = self.client.get(reverse('add_to_cart', args=[self.product.pk]))
        self.assertEqual(resp.status_code, 405)

    def test_update_cart_bad_input_does_not_500(self):
        for bad_val in ('invalid', '-5', '0', '99999999'):
            item, _ = CartItem.objects.get_or_create(cart=self.cart, product=self.product, defaults={'quantity': 2})
            resp = self.client.post(reverse('update_cart', args=[item.pk]), {'quantity': bad_val})
            self.assertNotEqual(resp.status_code, 500)


class AiChatSecurityTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_ai_chat_rejects_without_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        resp = csrf_client.post(reverse('ai_chat'), '{"message": "salom"}', content_type='application/json')
        self.assertEqual(resp.status_code, 403)

    def test_ai_chat_rate_limiting(self):
        with mock.patch('main.ai_assistant.get_ai_response', return_value={'success': True, 'response': 'ok'}):
            for _ in range(3):
                r = self.client.post(reverse('ai_chat'), '{"message": "salom"}', content_type='application/json')
                self.assertEqual(r.status_code, 200)
            r = self.client.post(reverse('ai_chat'), '{"message": "salom"}', content_type='application/json')
            self.assertEqual(r.status_code, 429)

    def test_history_sanitization(self):
        raw = [
            {'role': 'system', 'text': 'attack'},
            {'role': 'user', 'text': 'a' * 2000},
            {'role': 'model', 'text': 'valid'},
            'not a dict',
        ]
        cleaned = sanitize_history(raw)
        self.assertEqual(len(cleaned), 2)
        self.assertEqual(cleaned[0]['role'], 'user')
        self.assertEqual(len(cleaned[0]['text']), 1000)
        self.assertEqual(cleaned[1]['role'], 'assistant')


class ParallelPurchaseTests(TransactionTestCase):
    def test_parallel_purchase_stock_never_negative(self):
        seller = User.objects.create_user('seller_par', password='x', is_seller=True)
        store = Store.objects.create(owner=seller, name='P Store', status='active')
        product = Product.objects.create(store=store, name='Armatura', price=100000, stock=3)

        buyer1 = User.objects.create_user('b1', password='x', is_buyer=True)
        buyer2 = User.objects.create_user('b2', password='x', is_buyer=True)

        cart1 = Cart.objects.create(user=buyer1)
        cart2 = Cart.objects.create(user=buyer2)
        CartItem.objects.create(cart=cart1, product=product, quantity=2)
        CartItem.objects.create(cart=cart2, product=product, quantity=2)

        client1 = Client()
        client1.login(username='b1', password='x')
        client2 = Client()
        client2.login(username='b2', password='x')

        r1 = client1.post(reverse('checkout'), {'payment_method': 'card', 'address': 'A'})
        r2 = client2.post(reverse('checkout'), {'payment_method': 'card', 'address': 'B'})

        product.refresh_from_db()
        self.assertEqual(product.stock, 1)
        self.assertEqual(Order.objects.count(), 1)

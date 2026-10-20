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


# ───────── Alohida portallar: xaridor / sotuvchi / admin ─────────
from django.test import override_settings


class PortalTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user('buyer1', password='pass12345', phone='+998901112233')
        self.seller = User.objects.create_user('seller1', password='pass12345', is_seller=True, is_buyer=False)
        self.admin = User.objects.create_superuser('admin1', 'a@a.uz', 'pass12345')
        self.store = Store.objects.create(owner=self.seller, name='Dokon', status='active')
        self.product = Product.objects.create(store=self.store, name='Sement', price=50000, stock=50)

    # --- kirish sahifalari ---
    def test_each_portal_login_page_renders(self):
        for name in ('login', 'seller_login', 'admin_login', 'register', 'seller_register'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_login_redirects_by_role(self):
        cases = (('login', 'buyer1', '/'), ('seller_login', 'seller1', reverse('seller_dashboard')),
                 ('admin_login', 'admin1', reverse('admin_dashboard')))
        for url_name, username, expected in cases:
            self.client.logout()
            r = self.client.post(reverse(url_name), {'username': username, 'password': 'pass12345'})
            self.assertRedirects(r, expected, fetch_redirect_response=False)

    def test_wrong_portal_is_rejected_with_message(self):
        r = self.client.post(reverse('login'), {'username': 'seller1', 'password': 'pass12345'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.wsgi_request.user.is_authenticated)
        self.assertIn('xaridor akkaunti emas', r.content.decode())
        r = self.client.post(reverse('seller_login'), {'username': 'buyer1', 'password': 'pass12345'})
        self.assertFalse(r.wsgi_request.user.is_authenticated)
        r = self.client.post(reverse('admin_login'), {'username': 'seller1', 'password': 'pass12345'})
        self.assertFalse(r.wsgi_request.user.is_authenticated)

    def test_unauthenticated_panels_go_to_their_own_login(self):
        self.assertRedirects(self.client.get(reverse('seller_dashboard')),
                             reverse('seller_login') + '?next=/seller/', fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse('admin_dashboard')),
                             reverse('admin_login') + '?next=/panel/', fetch_redirect_response=False)

    # --- ro'yxatdan o'tish ---
    # --- ajratish ---
    def test_seller_and_admin_cannot_open_marketplace(self):
        for user, home in ((self.seller, reverse('seller_dashboard')), (self.admin, reverse('admin_dashboard'))):
            self.client.force_login(user)
            for name in ('marketplace', 'cart', 'orders', 'checkout'):
                self.assertRedirects(self.client.get(reverse(name)), home, fetch_redirect_response=False)

    def test_buyer_cannot_open_panels(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(reverse('admin_dashboard')).status_code, 404)
        r = self.client.get(reverse('seller_dashboard'))
        self.assertRedirects(r, '/', fetch_redirect_response=False)

    def test_panels_look_like_panels_and_have_anora(self):
        self.client.force_login(self.seller)
        html = self.client.get(reverse('seller_dashboard')).content.decode()
        self.assertIn('Sotuvchi paneli', html)
        self.assertIn('portal-sidebar', html)
        self.assertNotIn('name="q"', html)           # marketplace qidiruvi yo'q
        self.assertIn('id="anora-chat"', html)       # Anora hamma uchun
        self.assertEqual(html.count("getElementById('theme-toggle')"), 1)  # tema tugmasi bir marta ulangan
        self.client.force_login(self.admin)
        html = self.client.get(reverse('admin_dashboard')).content.decode()
        self.assertIn('Admin panel', html)
        self.assertIn('id="anora-chat"', html)
        self.assertNotIn('name="q"', html)

    def test_buyer_site_has_seller_link_and_anora(self):
        self.client.force_login(self.buyer)
        html = self.client.get(reverse('marketplace')).content.decode()
        self.assertIn('name="q"', html)
        self.assertIn(reverse('seller_login'), html)
        self.assertIn('id="anora-chat"', html)

    def test_notifications_page_per_role(self):
        for user, name in ((self.buyer, 'notifications'), (self.seller, 'seller_notifications'),
                           (self.admin, 'admin_notifications')):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_logout_goes_to_own_portal_login(self):
        self.client.force_login(self.seller)
        self.assertRedirects(self.client.post(reverse('seller_logout')), reverse('seller_login'), fetch_redirect_response=False)
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.post(reverse('admin_logout')), reverse('admin_login'), fetch_redirect_response=False)

    def test_admin_nasiya_list(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('admin_model_list', args=['nasiya'])).status_code, 200)

    # --- alohida domenlar (seller.example.uz / admin.example.uz) ---
    @override_settings(SELLER_HOST='seller.test', ADMIN_HOST='admin.test', ALLOWED_HOSTS=['*'])
    def test_host_mode(self):
        # seller domeni: ildiz va /login/ sotuvchi portaliga olib boradi
        r = self.client.get('/', HTTP_HOST='seller.test')
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r['Location'].startswith('/seller/login/'))
        r = self.client.get('/login/', HTTP_HOST='seller.test')
        self.assertIn('Sotuvchi kabiniga kirish', r.content.decode())
        # admin domeni
        r = self.client.get('/login/', HTTP_HOST='admin.test')
        self.assertIn('Admin paneliga kirish', r.content.decode())
        # asosiy domen: oddiy xaridor sayti
        r = self.client.get('/login/', HTTP_HOST='main.test')
        self.assertIn('Tizimga kirish', r.content.decode())
        self.assertNotIn('Sotuvchi kabiniga kirish', r.content.decode())


class EmailVerificationTests(TestCase):
    """Ro'yxatdan o'tish -> xat -> havola -> kirish."""
    PW = 'Str0ngPass!234'

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def _register(self, url_name, **extra):
        data = {'username': 'newuser', 'email': 'New@Example.com', 'password1': self.PW, 'password2': self.PW,
                'phone': '+998901234567'}
        data.update(extra)
        return self.client.post(reverse(url_name), data)

    def _link(self, message):
        import re
        m = re.search(r'https?://[^\s]+/accounts/confirm-email/[^\s/]+/', message.body)
        self.assertIsNotNone(m, message.body)
        return m.group(0).split('://', 1)[1].split('/', 1)[1].join(['/', ''])

    def _confirm(self, message):
        path = self._link(message)
        page = self.client.get(path)
        self.assertEqual(page.status_code, 200)
        return self.client.post(path)

    def test_buyer_flow(self):
        from django.core import mail
        r = self._register('register')
        self.assertRedirects(r, reverse('account_email_verification_sent'), fetch_redirect_response=False)
        u = User.objects.get(username='newuser')
        self.assertTrue(u.is_buyer and not u.is_seller)
        self.assertEqual(u.email, 'new@example.com')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/accounts/confirm-email/', mail.outbox[0].body)
        # tasdiqlanmaguncha kira olmaydi (va yangi xat ketadi)
        r = self.client.post(reverse('login'), {'username': 'newuser', 'password': self.PW})
        self.assertFalse(r.wsgi_request.user.is_authenticated)
        self.assertIn('tasdiqlanmagan', r.content.decode())
        self.assertEqual(len(mail.outbox), 2)
        # 2 daqiqa ichida takroriy urinish xatni ko'paytirmaydi
        self.client.post(reverse('login'), {'username': 'newuser', 'password': self.PW})
        self.assertEqual(len(mail.outbox), 2)
        # havola -> tasdiqlanadi -> login sahifasiga
        r = self._confirm(mail.outbox[1])
        self.assertRedirects(r, reverse('login') + '?verified=1', fetch_redirect_response=False)
        r = self.client.post(reverse('login'), {'username': 'newuser', 'password': self.PW})
        self.assertRedirects(r, '/', fetch_redirect_response=False)

    def test_seller_flow(self):
        from django.core import mail
        r = self._register('seller_register', username='newseller', email='s@example.com', stir_pinfl='123456789')
        self.assertRedirects(r, reverse('account_email_verification_sent'), fetch_redirect_response=False)
        r = self.client.post(reverse('seller_login'), {'username': 'newseller', 'password': self.PW})
        self.assertFalse(r.wsgi_request.user.is_authenticated)
        r = self._confirm(mail.outbox[0])
        self.assertRedirects(r, reverse('seller_login') + '?verified=1', fetch_redirect_response=False)
        r = self.client.post(reverse('seller_login'), {'username': 'newseller', 'password': self.PW})
        self.assertRedirects(r, reverse('seller_dashboard'), fetch_redirect_response=False)

    def test_seller_register_requires_stir(self):
        self.assertEqual(self._register('seller_register', username='x1', stir_pinfl='').status_code, 200)
        self.assertEqual(self._register('seller_register', username='x2', stir_pinfl='12').status_code, 200)
        self.assertFalse(User.objects.filter(username__in=['x1', 'x2']).exists())

    def test_email_required_and_unique(self):
        self.assertEqual(self._register('register', email='').status_code, 200)
        self.assertEqual(self._register('register', email='not-an-email').status_code, 200)
        self._register('register')
        r = self._register('register', username='other', email='new@example.com')   # shu email band
        self.assertEqual(r.status_code, 200)
        self.assertIn('allaqachon mavjud', r.content.decode())
        self.assertFalse(User.objects.filter(username='other').exists())

    def test_legacy_users_without_email_record_can_still_login(self):
        User.objects.create_user('old', password=self.PW)
        r = self.client.post(reverse('login'), {'username': 'old', 'password': self.PW})
        self.assertRedirects(r, '/', fetch_redirect_response=False)

    def test_admin_not_blocked(self):
        User.objects.create_superuser('boss', 'b@b.uz', self.PW)
        r = self.client.post(reverse('admin_login'), {'username': 'boss', 'password': self.PW})
        self.assertRedirects(r, reverse('admin_dashboard'), fetch_redirect_response=False)

    def test_mail_failure_does_not_crash_registration(self):
        from unittest import mock
        with mock.patch('allauth.account.models.EmailAddress.send_confirmation', side_effect=OSError('smtp down')):
            r = self._register('register')
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_allauth_own_pages_are_closed_or_redirected(self):
        self.assertRedirects(self.client.get('/accounts/login/'), reverse('login'), fetch_redirect_response=False)
        self.assertRedirects(self.client.get('/accounts/signup/'), reverse('register'), fetch_redirect_response=False)

    def test_allauth_pages_use_site_design(self):
        html = self.client.get(reverse('account_email_verification_sent')).content.decode()
        self.assertIn('auth-card', html)
        self.assertIn('ArzonMaterial', html)
        self.assertEqual(self.client.get('/accounts/password/reset/').status_code, 200)


class OrderDetailRegressionTests(TestCase):
    """Mahsulot o'chirilgandan keyin buyurtma sahifasi 500 bermasligi kerak."""

    def test_order_detail_with_deleted_product(self):
        buyer = User.objects.create_user('b2', password='x')
        seller = User.objects.create_user('s2', password='x', is_seller=True, is_buyer=False)
        store = Store.objects.create(owner=seller, name='D', status='active')
        product = Product.objects.create(store=store, name='G\'isht', price=1000, stock=10)
        order = Order.objects.create(user=buyer, address='Toshkent', payment_method='cash')
        OrderItem.objects.create(order=order, product=product, product_name='G\'isht', price=1000, quantity=2)
        product.delete()
        self.client.force_login(buyer)
        self.assertEqual(self.client.get(reverse('order_detail', args=[order.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('orders')).status_code, 200)

    def test_seller_cancel_restores_stock_without_penalty(self):
        buyer = User.objects.create_user('b3', password='x')
        seller = User.objects.create_user('s3', password='x', is_seller=True, is_buyer=False)
        store = Store.objects.create(owner=seller, name='D', status='active')
        product = Product.objects.create(store=store, name='Sement', price=100000, stock=8)
        order = Order.objects.create(user=buyer, address='T', payment_method='cash')
        item = OrderItem.objects.create(order=order, product=product, product_name='Sement', price=100000, quantity=2)
        self.client.force_login(seller)
        self.client.post(reverse('update_order_item_status', args=[item.pk]), {'status': 'cancelled'})
        product.refresh_from_db(); order.refresh_from_db(); item.refresh_from_db()
        self.assertEqual(item.status, 'cancelled')
        self.assertEqual(product.stock, 10)
        self.assertEqual(order.penalty_amount, 0)


class Stage6Tests(TestCase):
    def setUp(self):
        seller = User.objects.create_user('s6', password='x', is_seller=True)
        self.store = Store.objects.create(owner=seller, name="Do'kon", status='active')
        for i in range(30):
            Product.objects.create(store=self.store, name=f'Mahsulot {i}', price=1000 + i, stock=5)
        self.ru = Product.objects.create(store=self.store, name='Sement', name_ru='Цемент', price=65000, stock=5, unit='qop')

    def _lang(self, code):
        self.client.post(reverse('set_language'), {'language': code})

    def test_pagination_and_total(self):
        r = self.client.get(reverse('marketplace'))
        self.assertContains(r, 'page=2')
        self.assertContains(r, '31 ')                       # umumiy soni (31 ta)
        self.assertEqual(self.client.get(reverse('marketplace'), {'page': 2}).status_code, 200)
        self.assertEqual(self.client.get(reverse('marketplace'), {'page': 999}).status_code, 200)

    def test_search_in_russian_name_and_unit_label(self):
        self._lang('ru')
        r = self.client.get(reverse('marketplace'), {'q': 'Цемент'})
        self.assertContains(r, 'Цемент')
        self.assertContains(r, 'мешок')

    def test_static_pages_seeded_and_localized(self):
        r = self.client.get(reverse('page', args=['about']))
        self.assertContains(r, 'Biz haqimizda')
        self.assertContains(r, reverse('page', args=['faq']))        # footer havolasi
        self._lang('en')
        self.assertContains(self.client.get(reverse('page', args=['delivery'])), 'Delivery')
        self.assertEqual(self.client.get(reverse('page', args=['yoq-sahifa'])).status_code, 404)

    def test_notification_follows_language(self):
        from django.utils import translation
        from .notifications import notify
        u = User.objects.create_user('n1', password='x')
        n = notify(u, "#%(n)s buyurtmadagi mahsulotlaringizni xaridor qabul qildi. Endi siz 'Yetkazildi' holatiga o'tkazishingiz mumkin.", {'n': 7})
        with translation.override('uz'):
            self.assertIn('xaridor qabul qildi', n.display_message)
        with translation.override('ru'):
            self.assertIn('Покупатель получил', n.display_message)
        with translation.override('en'):
            self.assertIn('The buyer received', n.display_message)

    def test_footer_contact_only_when_configured(self):
        self.assertNotContains(self.client.get(reverse('marketplace')), '+998 90 000 00 00')
        with self.settings(SUPPORT_PHONE='+998 71 123 45 67'):
            self.assertContains(self.client.get(reverse('marketplace')), '+998 71 123 45 67')


class EstimatorTests(TestCase):
    def _pool(self):
        return {'type': 'pool', 'title': 'Hovuz', 'params': {'length_m': 6, 'width_m': 3, 'depth_m': 1.5}}

    def _find(self, items, word):
        return next(i for i in items if word in i['query'])

    def test_slab_formula(self):
        from .estimator import calculate_works
        items, notes = calculate_works([{'type': 'slab', 'params': {'length_m': 5, 'width_m': 4, 'thickness_cm': 10}}])
        self.assertEqual(notes, [])
        self.assertAlmostEqual(self._find(items, 'sement')['quantity'], 2 * 300 * 1.05, places=1)   # 2 m3 beton
        self.assertAlmostEqual(self._find(items, 'plyonka')['quantity'], 20 * 1.15, places=1)

    def test_pool_formula(self):
        from .estimator import calculate_works
        items, _n = calculate_works([self._pool()])
        vol = (6.4 * 3.4 * 0.2) + 1.5 * (2 * 0.2 * 9 + 4 * 0.04)             # taglik + devorlar
        self.assertAlmostEqual(self._find(items, 'sement')['quantity'], vol * 315, delta=1)
        self.assertAlmostEqual(self._find(items, 'plitka yelimi')['quantity'], 45 * 5, places=1)   # ichki sirt 45 m2
        self.assertAlmostEqual(self._find(items, 'gidroizolyatsiya')['quantity'], 45 * 3, places=1)

    def test_brick_wall_with_openings_and_missing_dimensions(self):
        from .estimator import calculate_works
        items, _n = calculate_works([{'type': 'wall', 'params': {'length_m': 10, 'height_m': 2.5, 'openings_m2': 4}}])
        self.assertAlmostEqual(self._find(items, 'isht')['quantity'], 21 * 102 * 1.05, places=1)
        items, notes = calculate_works([{'type': 'slab', 'title': 'Pol', 'params': {'length_m': 5}}, {'type': 'noma\'lum', 'params': {}}])
        self.assertEqual(items, [])
        self.assertEqual(len(notes), 1)                                      # noma'lum tur e'tiborsiz, yetishmaydigan o'lcham haqida izoh

    def test_params_are_sanitized(self):
        from .estimator import calculate_works
        items, notes = calculate_works([{'type': 'slab', 'params': {'length_m': -5, 'width_m': 'abc'}}])
        self.assertEqual(items, [])

    def test_unit_conversion_to_product_units(self):
        from .estimator import cart_quantity
        P = lambda **kw: Product(**{'name': 'X', 'price': 1, 'stock': 100, **kw})
        self.assertEqual(cart_quantity(630, 'kg', P(name='Sement M400, 50 kg', unit='qop')), (13, True, True))
        self.assertEqual(cart_quantity(630, 'kg', P(name='Sement', unit='kg')), (630, False, True))
        self.assertEqual(cart_quantity(1.2, 'tonna', P(name='Sement 25 kg', unit='qop'))[0], 48)
        self.assertEqual(cart_quantity(14, 'litr', P(name="Bo'yoq 20 l", unit='dona'))[0], 1)
        self.assertEqual(cart_quantity(20, 'm2', P(name='Laminat 2.2 m²', unit='dona'))[0], 10)
        self.assertEqual(cart_quantity(5, 'dona', P(name='Plitka', unit='dona')), (5, False, True))
        qty, conv, ok = cart_quantity(630, 'kg', P(name='Sement', unit='qop'))          # qop og'irligi noma'lum
        self.assertFalse(ok)

    def _setup_buyer_and_catalog(self):
        seller = User.objects.create_user('est_s', 'est_s@example.com', 'x', is_seller=True)
        store = Store.objects.create(owner=seller, name="Do'kon", status='active')
        self.cement = Product.objects.create(store=store, name='Sement M400, 50 kg', price=65000, stock=500, unit='qop')
        User.objects.create_user('est_b', 'est_b@example.com', 'x')
        self.client.login(username='est_b', password='x')

    def test_estimate_endpoint_converts_kg_to_bags_and_limits(self):
        from django.core.cache import cache
        cache.clear()
        self._setup_buyer_and_catalog()
        fake = {'project_type': 'Beton pol', 'assumptions': [], 'items': [],
                'works': [{'type': 'slab', 'params': {'length_m': 5, 'width_m': 4, 'thickness_cm': 10}}]}
        with mock.patch('main.ai_project.analyze_project', return_value=fake):
            r = self.client.post(reverse('ai_project_estimate'), {'message': '5x4 pol, 10 sm'})
            self.assertEqual(r.json()['success'], True)
            line = next(i for i in r.json()['items'] if 'sement' in i['query'])
            m = line['matches'][0]
            self.assertEqual(m['id'], self.cement.pk)
            self.assertEqual(m['cart_quantity'], 13)                         # 630 kg / 50 kg = 12,6 -> 13 qop (630 qop emas!)
            with mock.patch('main.ai_limits.PROJECT_LIMIT', 1):
                self.assertEqual(self.client.post(reverse('ai_project_estimate'), {'message': '5x4 pol'}).status_code, 429)

    def test_estimate_rejects_fake_file_type(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self._setup_buyer_and_catalog()
        fake_pdf = SimpleUploadedFile('smeta.pdf', b'bu pdf emas', content_type='application/pdf')
        with mock.patch('main.ai_project.analyze_project') as m:
            r = self.client.post(reverse('ai_project_estimate'), {'message': 'x', 'estimate': fake_pdf})
        self.assertEqual(r.status_code, 400)
        m.assert_not_called()
        real = SimpleUploadedFile('smeta.pdf', b'%PDF-1.4 ...', content_type='application/pdf')
        with mock.patch('main.ai_project.analyze_project', return_value={'project_type': 'x', 'assumptions': [], 'items': [], 'works': []}):
            self.assertEqual(self.client.post(reverse('ai_project_estimate'), {'message': 'x', 'estimate': real}).status_code, 200)

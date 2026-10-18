from unittest import mock
from django.test import TestCase
from django.urls import reverse
from .models import User, Store, Product, Cart, CartItem, Order, NasiyaApplication, Notification


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

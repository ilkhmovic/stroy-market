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

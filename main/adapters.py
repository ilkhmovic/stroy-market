from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse


class CustomAccountAdapter(DefaultAccountAdapter):
    """allauth faqat tasdiqlash xatlari uchun ishlatiladi.

    - allauth'ning o'z ro'yxatdan o'tish sahifasi yopiq (hamma /register/ yoki /seller/register/ dan o'tadi);
    - tasdiqlangandan keyin foydalanuvchi o'z portalining kirish sahifasiga yuboriladi.
    """

    def is_open_for_signup(self, request):
        return False

    def get_email_verification_redirect_url(self, email_address):
        user = email_address.user
        if user.is_superuser:
            return reverse('admin_login')
        if user.is_seller:
            return reverse('seller_login') + '?verified=1'
        return reverse('login') + '?verified=1'

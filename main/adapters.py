from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.urls import reverse


class CustomAccountAdapter(DefaultAccountAdapter):
    """allauth faqat tasdiqlash xatlari uchun ishlatiladi.

    - allauth'ning o'z ro'yxatdan o'tish sahifasi yopiq (hamma /register/ yoki /seller/register/ dan o'tadi);
    - tasdiqlangandan keyin foydalanuvchi o'z portalining kirish sahifasiga yuboriladi.
    """

    def is_open_for_signup(self, request):
        return True

    def get_email_verification_redirect_url(self, email_address):
        user = email_address.user
        if user.is_superuser:
            return reverse('admin_login')
        if user.is_seller:
            return reverse('seller_login') + '?verified=1'
        return reverse('login') + '?verified=1'


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Google orqali yangi xaridor akkauntiga ruxsat beradi.

    Google tasdiqlagan email allaqachon oddiy akkauntga tegishli bo'lsa,
    allauth sozlamasi (SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT)
    foydalanuvchini shu akkauntga kiritadi.
    """

    def is_open_for_signup(self, request, sociallogin):
        return True

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form=form)
        if not user.is_seller and not user.is_superuser:
            user.is_verified = True
            user.save(update_fields=['is_verified'])
        return user

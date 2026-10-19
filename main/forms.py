from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
import re
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache
from django.utils.translation import gettext
from .models import User, Store, Product, Review, Category, Order, Notification, Brand, Region, NasiyaApplication


def _email_taken(email):
    from allauth.account.models import EmailAddress
    return (User.objects.filter(email__iexact=email).exists()
            or EmailAddress.objects.filter(email__iexact=email).exists())


class _EmailFieldMixin:
    """Ro'yxatdan o'tishda email majburiy va noyob."""

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if _email_taken(email):
            raise forms.ValidationError(_("Bu email bilan akkaunt allaqachon mavjud."))
        return email


def email_needs_verification(user):
    """Faqat tasdiqlanmagan EmailAddress yozuvi bor va tasdiqlangani yo'q akkauntlar bloklanadi.

    Email yozuvi umuman yo'q eski akkauntlar (va adminlar) ta'sirlanmaydi.
    """
    from allauth.account.models import EmailAddress
    qs = EmailAddress.objects.filter(user=user)
    return qs.exists() and not qs.filter(verified=True).exists()


def create_unverified_email(user, email):
    from allauth.account.models import EmailAddress
    return EmailAddress.objects.create(user=user, email=email, primary=True, verified=False)


class UserRegisterForm(_EmailFieldMixin, UserCreationForm):
    email = forms.EmailField(label=_("Email manzilingiz"), help_text=_("Tasdiqlash xati shu manzilga yuboriladi"))

    """Xaridor ro'yxatdan o'tishi (faqat xarid qilish). Sotuvchilar alohida portalda."""
    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email', 'phone')
        labels = {'phone': 'Telefon raqamingiz'}

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data.get('phone', '')
        user.is_seller = False
        user.is_buyer = True
        if commit:
            user.save()
            create_unverified_email(user, user.email)
        return user


class SellerRegisterForm(_EmailFieldMixin, UserCreationForm):
    email = forms.EmailField(label=_("Email manzilingiz"), help_text=_("Tasdiqlash xati shu manzilga yuboriladi"))
    """Sotuvchi portalida ro'yxatdan o'tish: telefon va STIR/PINFL majburiy."""
    phone = forms.CharField(max_length=20, label="Telefon raqamingiz")
    stir_pinfl = forms.CharField(max_length=14, label="STIR / PINFL")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email', 'phone', 'stir_pinfl')

    def clean_stir_pinfl(self):
        value = re.sub(r'\D', '', self.cleaned_data['stir_pinfl'])
        if len(value) not in (9, 14):
            raise forms.ValidationError(_("STIR 9 ta, PINFL 14 ta raqamdan iborat bo'lishi kerak."))
        return value

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data['phone']
        user.stir_pinfl = self.cleaned_data['stir_pinfl']
        user.is_seller = True
        user.is_buyer = False
        if commit:
            user.save()
            create_unverified_email(user, user.email)
        return user


class _PortalAuthForm(AuthenticationForm):
    """Har bir portal faqat o'z rolidagi akkauntlarni kiritadi."""
    portal = None
    wrong_portal_message = ''

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        from .roles import get_role
        if get_role(user) != self.portal:
            raise forms.ValidationError(self.wrong_portal_message, code='wrong_portal')
        if self.portal != 'admin' and email_needs_verification(user):
            self._resend_verification(user)
            raise forms.ValidationError(
                gettext("Emailingiz hali tasdiqlanmagan. Pochtangizga yuborilgan havolani bosing "
                        "(Spam papkasini ham tekshiring). Yangi tasdiqlash xati yuborildi."),
                code='email_not_verified')

    def _resend_verification(self, user):
        """Parol to'g'ri kiritilgan bo'lsagina xat qayta yuboriladi; 2 daqiqada ko'pi bilan 1 marta."""
        from allauth.account.models import EmailAddress
        key = f'verif-resend:{user.pk}'
        if cache.get(key):
            return
        address = EmailAddress.objects.filter(user=user, verified=False).order_by('-primary').first()
        if address:
            try:
                address.send_confirmation(self.request, signup=False)
                cache.set(key, 1, 120)
            except Exception:
                import logging
                logging.getLogger(__name__).exception("Tasdiqlash xatini yuborib bo'lmadi: user=%s", user.pk)


class BuyerAuthForm(_PortalAuthForm):
    portal = 'buyer'
    wrong_portal_message = _("Bu akkaunt xaridor akkaunti emas. Sotuvchi yoki admin portaliga kiring.")


class SellerAuthForm(_PortalAuthForm):
    portal = 'seller'
    wrong_portal_message = _("Bu akkaunt sotuvchi akkaunti emas. Xaridor sifatida asosiy saytdan kiring.")


class AdminAuthForm(_PortalAuthForm):
    portal = 'admin'
    wrong_portal_message = _("Bu akkauntda admin huquqi yo'q.")

class BuyerProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'address', 'avatar']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }

class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ['name', 'description', 'logo', 'phone', 'address', 'region', 'delivery_regions']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'address': forms.Textarea(attrs={'rows': 2}),
            'delivery_regions': forms.CheckboxSelectMultiple(),
        }

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['category', 'brand', 'name', 'description', 'name_ru', 'name_en', 'description_ru', 'description_en', 'price', 'stock', 'image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment', 'seller_reply']
        widgets = {
            'rating': forms.RadioSelect(choices=[(i, f"{i} ★") for i in range(1, 6)]),
            'comment': forms.Textarea(attrs={'rows': 4}),
            'seller_reply': forms.Textarea(attrs={'rows': 4}),
        }

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'slug']

class UserAdminForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'phone', 'address', 'is_seller', 'is_buyer', 'is_staff', 'is_active', 'stir_pinfl']

class OrderAdminForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['status', 'payment_method', 'buyer_confirmed', 'penalty_amount', 'address', 'note']

class NotificationForm(forms.ModelForm):
    class Meta:
        model = Notification
        fields = ['user', 'message', 'target_url', 'is_read']

class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ['name', 'slug']

class RegionForm(forms.ModelForm):
    class Meta:
        model = Region
        fields = ['name']


class NasiyaApplicationForm(forms.ModelForm):
    """Checkoutda 'Nasiya' tanlanganda to'ldiriladi (prefix='nasiya')."""
    class Meta:
        model = NasiyaApplication
        fields = ['full_name', 'phone', 'term_months', 'monthly_income', 'workplace']

    def clean_full_name(self):
        name = ' '.join(self.cleaned_data['full_name'].split())
        if len(name) < 5 or ' ' not in name:
            raise forms.ValidationError(_("Familiya va ismingizni to'liq kiriting."))
        return name

    def clean_phone(self):
        raw = self.cleaned_data['phone']
        digits = re.sub(r'\D', '', raw)
        # 998901234567 yoki 901234567 ko'rinishlari
        if len(digits) == 9:
            digits = '998' + digits
        if not (len(digits) == 12 and digits.startswith('998')):
            raise forms.ValidationError(_("Telefon raqamni to'g'ri kiriting (masalan: +998 90 123 45 67)."))
        return '+' + digits


class NasiyaAdminForm(forms.ModelForm):
    """Admin panelda nasiya arizasini ko'rib chiqish (status va menejer izohi)."""
    class Meta:
        model = NasiyaApplication
        fields = ['status', 'manager_note']

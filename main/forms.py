from django import forms
from django.contrib.auth.forms import UserCreationForm
import re
from django.utils.translation import gettext_lazy as _
from .models import User, Store, Product, Review, Category, Order, Notification, Brand, Region, NasiyaApplication

class UserRegisterForm(UserCreationForm):
    ROLE_CHOICES = (
        ('buyer', "Sotib oluvchi (Faqat xarid qilish)"),
        ('seller', "Sotuvchi (Do'kon ochish va sotish)"),
    )
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.RadioSelect, initial='buyer', label="Kim bo'lib kirmisiz?")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('role', 'phone', 'stir_pinfl')
        labels = {
            'phone': 'Telefon raqamingiz',
            'stir_pinfl': 'STIR / PINFL (Sotuvchilar uchun)',
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        role = self.cleaned_data.get('role')
        user.phone = self.cleaned_data.get('phone')
        user.stir_pinfl = self.cleaned_data.get('stir_pinfl')
        if role == 'seller':
            user.is_seller = True
            user.is_buyer = False
            # Ensure STIR and Phone are provided
            if not user.phone or not user.stir_pinfl:
                raise forms.ValidationError("Sotuvchilar uchun telefon va STIR majburiy!")
        else:
            user.is_seller = False
            user.is_buyer = True
        if commit:
            user.save()
        return user

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        phone = cleaned_data.get('phone')
        stir = cleaned_data.get('stir_pinfl')
        
        if role == 'seller':
            if not phone:
                self.add_error('phone', "Sotuvchilar uchun telefon raqami majburiy!")
            if not stir:
                self.add_error('stir_pinfl', "Sotuvchilar uchun STIR/PINFL majburiy!")
        return cleaned_data

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

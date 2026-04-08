from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Store, Product, Review

class UserRegisterForm(UserCreationForm):
    ROLE_CHOICES = (
        ('buyer', "Sotib oluvchi (Faqat xarid qilish)"),
        ('seller', "Sotuvchi (Do'kon ochish va sotish)"),
    )
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.RadioSelect, initial='buyer', label="Kim bo'lib kirmisiz?")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('role',)

    def save(self, commit=True):
        user = super().save(commit=False)
        role = self.cleaned_data.get('role')
        if role == 'seller':
            user.is_seller = True
            user.is_buyer = False
        else:
            user.is_seller = False
            user.is_buyer = True
        if commit:
            user.save()
        return user

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
        fields = ['name', 'description', 'logo', 'phone', 'address']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'address': forms.Textarea(attrs={'rows': 2}),
        }

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['category', 'name', 'description', 'price', 'stock', 'image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.RadioSelect(choices=[(i, f"{i} ★") for i in range(1, 6)]),
            'comment': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Mahsulot haqida fikringizni yozing...'}),
        }
        labels = {
            'rating': 'Baho',
            'comment': 'Fikringiz',
        }

from allauth.account.adapter import DefaultAccountAdapter

class CustomAccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        
        # Bazadagi xatolikni chetlab o'tish uchun shu yerda ham qiymat berib ketamiz
        user.stir_verified = False  
        user.is_buyer = True
        user.is_seller = False
        
        if commit:
            user.save()
        return user
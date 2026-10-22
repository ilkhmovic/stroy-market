from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from . import services
from .models import CardTransaction, InstallmentPartner, InstallmentPlan, NasiyaChoice, WalletCard


class InstallmentPlanInline(admin.TabularInline):
    model = InstallmentPlan
    extra = 3


@admin.register(InstallmentPartner)
class InstallmentPartnerAdmin(admin.ModelAdmin):
    list_display = ('logo_preview', 'name', 'plans_summary', 'is_active', 'sort_order')
    list_editable = ('is_active', 'sort_order')
    list_display_links = ('name',)
    inlines = [InstallmentPlanInline]

    @admin.display(description="Logo")
    def logo_preview(self, obj):
        return format_html('<img src="{}" style="height:28px">', obj.logo.url) if obj.logo else '-'

    @admin.display(description="Muddatlar")
    def plans_summary(self, obj):
        return ', '.join(f"{p.months} oy ({p.markup_percent}%)" for p in obj.plans.all())


class CardTransactionInline(admin.TabularInline):
    model = CardTransaction
    extra = 0
    can_delete = False
    readonly_fields = ('kind', 'amount', 'balance_after', 'order', 'note', 'created_by', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(WalletCard)
class WalletCardAdmin(admin.ModelAdmin):
    list_display = ('user', 'brand', 'last4', 'expiry_display', 'balance', 'topup_link')
    search_fields = ('user__username', 'user__email', 'last4')
    readonly_fields = ('user', 'brand', 'last4', 'exp_month', 'exp_year', 'holder_name', 'balance', 'created_at')
    inlines = [CardTransactionInline]

    def has_add_permission(self, request):
        return False

    @admin.display(description="Muddati")
    def expiry_display(self, obj):
        return obj.expiry_display

    @admin.display(description="Hisob")
    def topup_link(self, obj):
        return format_html('<a href="{}">To\'ldirish</a>',
                           reverse('admin:installments_walletcard_topup', args=[obj.pk]))

    def get_urls(self):
        return [path('<int:card_id>/topup/', self.admin_site.admin_view(self.topup_view),
                     name='installments_walletcard_topup')] + super().get_urls()

    def topup_view(self, request, card_id):
        card = get_object_or_404(WalletCard, pk=card_id)
        if not self.has_change_permission(request, card):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        if request.method == 'POST':
            try:
                services.top_up(card.pk, request.POST.get('amount'), by_user=request.user,
                                note=request.POST.get('note', '')[:200])
                self.message_user(request, "Hisob to'ldirildi.", messages.SUCCESS)
                return HttpResponseRedirect(reverse('admin:installments_walletcard_changelist'))
            except services.CardError as e:
                self.message_user(request, str(e), messages.ERROR)
        card.refresh_from_db()
        ctx = {**self.admin_site.each_context(request), 'card': card, 'title': "Hisobni to'ldirish"}
        return TemplateResponse(request, 'installments/admin_topup.html', ctx)


@admin.register(NasiyaChoice)
class NasiyaChoiceAdmin(admin.ModelAdmin):
    list_display = ('application', 'partner_name', 'months', 'markup_percent', 'created_at')
    readonly_fields = ('application', 'partner', 'partner_name', 'months', 'markup_percent')

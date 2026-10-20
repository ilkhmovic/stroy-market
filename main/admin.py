from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Store, Category, Product, Review, Cart, CartItem, Order, OrderItem, Notification, Brand, Region, NasiyaApplication, AnoraFallback, Page

class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Roles', {'fields': ('is_seller', 'is_buyer')}),
        ('Additional Info', {'fields': ('phone', 'address', 'avatar')}),
    )

class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'category', 'price', 'stock')
    list_filter = ('category', 'store')
    search_fields = ('name',)

class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('product__name', 'user__username')

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'get_total_price', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'address')
    inlines = [OrderItemInline]

class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('user__username', 'message')

class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)

class RegionAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)

class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'region', 'status', 'created_at')
    list_filter = ('status', 'region', 'created_at')
    search_fields = ('name', 'owner__username')

class NasiyaApplicationAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'full_name', 'phone', 'term_months', 'order_total', 'status', 'created_at')
    list_filter = ('status', 'term_months', 'created_at')
    list_editable = ('status',)
    search_fields = ('full_name', 'phone', 'order__id')
    readonly_fields = ('order', 'created_at', 'updated_at')

    @admin.display(description="Jami summa (so'm)")
    def order_total(self, obj):
        return f"{obj.order.get_total_price():,.0f}".replace(',', ' ')

admin.site.register(NasiyaApplication, NasiyaApplicationAdmin)
admin.site.register(User, CustomUserAdmin)
admin.site.register(Store, StoreAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Brand, BrandAdmin)
admin.site.register(Region, RegionAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Review, ReviewAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(Cart)
admin.site.register(CartItem)
admin.site.register(Notification, NotificationAdmin)


class AnoraFallbackAdmin(admin.ModelAdmin):
    list_display = ('title', 'keywords', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title', 'keywords', 'answer_uz', 'answer_ru', 'answer_en')

admin.site.register(AnoraFallback, AnoraFallbackAdmin)


class PageAdmin(admin.ModelAdmin):
    list_display = ('slug', 'title_uz', 'order', 'is_published', 'updated_at')
    list_editable = ('order', 'is_published')
    search_fields = ('title_uz', 'title_ru', 'title_en')

admin.site.register(Page, PageAdmin)

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Store, Category, Product, Review, Cart, CartItem, Order, OrderItem, Notification, Brand, Region

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

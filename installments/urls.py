from django.urls import path

from . import views

app_name = 'installments'

# Yo'llar mavjud rol-bo'linishiga (profile/ - xaridor, seller/ - sotuvchi) mos qo'yilgan.
urlpatterns = [
    path('profile/buyer/cards/', views.cards_page, name='cards'),
    path('profile/buyer/cards/add/', views.add_card, name='add_card'),
    path('profile/buyer/cards/pay/', views.pay_order, name='pay_order'),
    path('profile/buyer/cards/<int:card_id>/history/', views.card_history, name='card_history'),
    path('seller/nasiya-export/', views.seller_export, name='seller_export'),
]

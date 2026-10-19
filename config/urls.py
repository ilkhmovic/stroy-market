from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path(settings.ADMIN_URL, admin.site.urls),
    # allauth'ning o'z kirish/ro'yxatdan o'tish sahifalari o'rniga bizning portallar:
    path('accounts/login/', RedirectView.as_view(pattern_name='login', query_string=True)),
    path('accounts/signup/', RedirectView.as_view(pattern_name='register')),
    path('accounts/', include('allauth.urls')),   # tasdiqlash havolasi, parolni tiklash
    path('', include("main.urls"))
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

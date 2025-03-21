"""
URL configuration for SkillSphere project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from SkillSphere import settings
from SkillSphere.views import CoverPageView, feedback_create

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', CoverPageView.as_view(), name='cover_page'),
    path('accounts/', include('accounts.urls')),
    path('classes/', include('classes.urls')),
    path('payments/', include('payments.urls')),
    path('notifications/', include('notifications.urls')),
    path('thanks/', feedback_create, name='feedback_create_url'),
]

if settings.DEBUG:  # Important: Only do this in DEBUG mode!
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:  # Important: Only do this in DEBUG mode!
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

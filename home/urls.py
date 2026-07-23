from django.urls import path
from . import views

app_name = 'home'

urlpatterns = [
    path('', views.index, name='index'),
    path('page/<slug:slug>/', views.cms_page_detail, name='cms_page'),
    path('faqs/', views.faq_view, name='faq'),
    path('contact/', views.contact_view, name='contact'),
    path('api/contact/', views.ContactFormAPIView.as_view(), name='api_contact_home'),
    path('debug-db/', views.debug_db_view, name='debug_db'),
]

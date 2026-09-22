from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('services/', views.services, name='services'),
    path('solutions/', views.solutions, name='solutions'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-and-conditions/', views.terms_conditions, name='terms_conditions'),
    path('cookie-policy/', views.cookie_policy, name='cookie_policy'),
    path('api/contact/', views.contact_submit_ajax, name='contact_submit_ajax'),
    
    # CMS Management
    path('admin-portal/cms/', views.admin_cms, name='admin_cms'),
    path('admin-portal/cms/delete/<str:item_type>/<int:item_id>/', views.admin_cms_delete_item, name='admin_cms_delete_item'),
    path('admin-portal/inquiries/', views.admin_inquiries, name='admin_inquiries'),
]

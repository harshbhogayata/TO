from django.urls import path
from . import views

urlpatterns = [
    path('create-checkout-session/', views.create_checkout_session, name='create-checkout-session'),
    path('webhook/', views.stripe_webhook, name='stripe-webhook'),
    path('invoice/<str:invoice_id>/', views.download_invoice, name='download-invoice'),
]

from django.urls import path

from . import views

urlpatterns = [
    path("accounts", views.social_accounts, name="social-accounts"),
    path("accounts/<int:pk>", views.social_account, name="social-account"),
    path("accounts/<int:pk>/creator-info", views.social_creator_info, name="social-creator-info"),
    path("<slug:platform>/connect", views.social_connect, name="social-connect"),
    path("<slug:platform>/callback", views.social_callback, name="social-callback"),
]

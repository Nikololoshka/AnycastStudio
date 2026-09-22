from django.urls import path

from . import views

urlpatterns = [
    path("accounts", views.accounts, name="social-accounts"),
    path("accounts/<int:pk>", views.account, name="social-account"),
    path("<slug:platform>/connect", views.connect, name="social-connect"),
    path("<slug:platform>/callback", views.callback, name="social-callback"),
]

from django.urls import path

from . import views

urlpatterns = [
    path("csrf", views.account_csrf, name="auth-csrf"),
    path("login", views.account_login, name="auth-login"),
    path("logout", views.account_logout, name="auth-logout"),
    path("me", views.account_me, name="auth-me"),
]

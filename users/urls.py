from django.contrib import admin
from django.urls import path
from users import views

urlpatterns = [
   path('', views.UserLoginView.as_view(), name='login'),
   path('register/', views.UserRegistrationView.as_view(), name='register'),
   path('logout/', views.UserLogoutView.as_view(), name='logout'),
]

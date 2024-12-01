# views.py
from django.contrib.auth.views import LoginView, LogoutView
from django.views import View
from django.views.generic import CreateView
from django.shortcuts import redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from .forms import UserRegistrationForm, UserLoginForm
from django.contrib.messages.views import SuccessMessageMixin

class UserRegistrationView(SuccessMessageMixin, CreateView):
    form_class = UserRegistrationForm
    template_name = 'register.html'
    success_message = "Konto zostało utworzone pomyślnie! Możesz się teraz zalogować."
   
    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        if self.request.user.is_employee:
           return redirect('dashboard_employee', pk=self.request.user.id)
        elif not self.request.user.is_employee:
           return redirect('dashboard_client', pk=self.request.user.id)

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_employee:
            return redirect('dashboard_employee', pk=request.user.id)
        elif request.user.is_authenticated and not request.user.is_employee:
            return redirect('dashboard_client', pk=request.user.id)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy('login')

class UserLoginView(SuccessMessageMixin, LoginView):
    form_class = UserLoginForm
    template_name = 'login.html'
    success_message = "Zostałeś pomyślnie zalogowany!"
   
    def get_success_url(self):
           return reverse('dashboard_client', kwargs={'pk': self.request.user.id})
   
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_employee and request.user.is_active:
            return redirect('dashboard_employee', pk=request.user.id)
        elif request.user.is_authenticated and not request.user.is_employee and request.user.is_active:
            return redirect('dashboard_client', pk=request.user.id)
        return super().dispatch(request, *args, **kwargs)

class UserLogoutView(View):
    def get(self, request):
        logout(request)
        return redirect('login')
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect
from django.contrib import messages

from users.models import CustomUser

class CustomerMixin(UserPassesTestMixin):

    def test_func(self):
        if not CustomUser.objects.get(id=self.request.user.id).is_employee or CustomUser.objects.get(id=self.request.user.id).is_admin:
            return True
        return False
    
    def handle_no_permission(self):
        return redirect('login')
    
class EmployeeMixin(UserPassesTestMixin):

    def test_func(self):
        if CustomUser.objects.get(id=self.request.user.id).is_employee or CustomUser.objects.get(id=self.request.user.id).is_admin:
            return True
        return False
    
    def handle_no_permission(self):
        return redirect('login')
    
class AdminMixin(UserPassesTestMixin):

    def test_func(self):
        if CustomUser.objects.get(id=self.request.user.id).is_admin:
            return True
        return False
    
    def handle_no_permission(self):
        return redirect('login')
    

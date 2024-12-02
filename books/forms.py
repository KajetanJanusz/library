from typing import Any
from django import forms
from django.forms import Form, ModelForm
from django.shortcuts import redirect

from books.models import Book, BookCopy, BookRental, Opinion
from users.models import CustomUser

class BookForm(ModelForm):
    class Meta:
        model = Book
        fields = ['title', 'author', 'category', 'published_date', 'isbn', 'total_copies', 'description']
        labels = {
            'title': 'Tytuł',
            'author': 'Autor',
            'category': 'Kategoria',
            'published_date': 'Data publikacji',
            'isbn': 'Numer ISBN',
            'total_copies': 'Całkowita liczba kopii',
            'description': 'Opis'
        }
        widgets = {
            'published_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }

class UserForm(ModelForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'phone')
        labels = {
            'username': 'Nazwa użytkownika',
            'email': 'Adres e-mail',
            'first_name': 'Imię',
            'last_name': 'Nazwisko',
            'phone': 'Numer telefonu'
        }
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nazwa użytkownika'
            }),
        }
        help_texts = {
            'username': None,
        }

class OpinionForm(ModelForm):
    class Meta:
        model = Opinion
        fields = ('rate', 'comment')
        labels = {
            'rate': 'Ocena',
            'comment': 'Komentarz'
        }
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 4})
        }

class CustomUserForm(ModelForm):
    class Meta:
        model = CustomUser
        fields = ('username', 
                  'first_name', 
                  'last_name', 
                  'password',
                  'email',
                  'phone',
                  'is_employee',
                  'is_admin',
                  'is_active')
        labels = {
            'username': 'Nazwa użytkownika',
            'first_name': 'Imię',
            'last_name': 'Nazwisko',
            'password': 'Hasło',
            'email': 'Adres e-mail',
            'phone': 'Numer telefonu',
            'is_employee': 'Pracownik',
            'is_admin': 'Administrator',
            'is_active': 'Aktywny'
        }
        help_texts = {
            'username': None,
        }
        widgets = {
            'password': forms.PasswordInput(),
        }
        
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        
        if commit:
            user.save()
        return user
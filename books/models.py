from datetime import date, timedelta
from typing import Iterable
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MaxValueValidator


class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Book(models.Model):
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    category = models.ForeignKey(Category, related_name='books', on_delete=models.CASCADE)
    published_date = models.DateField()
    isbn = models.CharField(max_length=13, unique=True)
    description = models.TextField(blank=True, null=True)
    total_copies = models.PositiveIntegerField(blank=False, null=False)

    def __str__(self):
        return self.title


class CustomUser(AbstractUser):
    phone = models.CharField(max_length=15, null=True, blank=True)
    is_employee = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.username
    
class BookCopy(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="copies")
    is_available = models.BooleanField(default=True)
    borrower = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)  # Użytkownik wypożyczający

    def __str__(self):
        return f"{self.book.title} - Copy {self.id}"

    
class BookRental(models.Model):
    book_copy = models.ForeignKey(BookCopy, related_name='rentals', on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, related_name='rentals', on_delete=models.CASCADE)
    rental_date = models.DateField(auto_now_add=True)
    due_date = models.DateField(null=False, blank=False)
    return_date = models.DateField(null=True, blank=True)
    is_extended = models.BooleanField(default=False)
    status_choices = [
        ('rented', 'Wypożyczona'),
        ('returned', 'Zwrócona'),
        ('overdue', 'Po terminie'),
    ]
    status = models.CharField(max_length=10, choices=status_choices, default='rented')
    fine = models.DecimalField(blank=True, null=True, decimal_places=2, max_digits=5)


    def __str__(self):
        return f"{self.user.username} rented {self.book_copy.book.title}, id {self.book_copy.book.id}"
    
    def save(self, *args, **kwargs):
        if not self.due_date:
            self.due_date = self.rental_date + timedelta(days=30)

        return super(BookRental, self).save(*args, **kwargs)
    
class Opinion(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="rate")
    user = models.ForeignKey(CustomUser, related_name='rate', on_delete=models.CASCADE)
    rate = models.PositiveIntegerField(validators=[MaxValueValidator(5)])
    comment = models.CharField(max_length=250)
    created_at = models.DateField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.user}'s opinion on {self.book}"

    class Meta:
        ordering = ['-created_at']
    
class Notification(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    is_available = models.BooleanField(default=False)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.username}"

    class Meta:
        ordering = ['-created_at']

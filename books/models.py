from datetime import timedelta
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MaxValueValidator

from books.ai import generate_and_save_image


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
    ai_image = models.ImageField(upload_to='book_covers/', null=True, blank=True)

    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.ai_image:
            result = generate_and_save_image(
                self.title,
                self.author
            )
            if result:
                file_name, image_content = result
                if file_name and image_content:
                    self.ai_image.save(file_name, image_content, save=False)
        super().save(*args, **kwargs)

class CustomUser(AbstractUser):
    phone = models.CharField(max_length=15, null=True, blank=True)
    is_employee = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        is_new = self._state.adding

        super().save(*args, **kwargs)

        if is_new:
            Badge.objects.create(user=self)

    def __str__(self):
        return self.username
    
class Badge(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="badges")
    first_book = models.BooleanField(default=False)
    ten_books = models.BooleanField(default=False)
    twenty_books = models.BooleanField(default=False)
    hundred_books = models.BooleanField(default=False)
    three_categories = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username}'s badges"
    
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
        ('pending', 'Zwrot oczekuje na zatwierdzenie')
    ]
    status = models.CharField(max_length=10, choices=status_choices, default='rented')
    fine = models.DecimalField(blank=True, null=True, decimal_places=2, max_digits=5)

    def __str__(self):
        return f"{self.user.username} rented {self.book_copy.book.title}, id {self.book_copy.book.id}"
    
    def save(self, *args, **kwargs):
        if not self.due_date:
            self.due_date = self.rental_date + timedelta(days=30)

        super().save(*args, **kwargs)
    
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

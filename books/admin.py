from django.contrib import admin

from books.models import Book, BookCopy, BookRental, Category, CustomUser, Notification, Opinion

admin.site.register(Category)
admin.site.register(Book)
admin.site.register(BookCopy)
admin.site.register(BookRental)
admin.site.register(Notification)
admin.site.register(Opinion)
admin.site.register(CustomUser)

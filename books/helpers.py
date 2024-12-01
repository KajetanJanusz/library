from django.db.models import Count
from .models import BookRental, Book, Category

def recommend_books_for_user(user):
    top_category = (
        BookRental.objects
        .filter(user=user)
        .values('book_copy__book__category')
        .annotate(rental_count=Count('id'))
        .order_by('-rental_count')
    )

    if not top_category:
        return []

    recommended_books = []
    for category_data in top_category:
        category_id = category_data['book_copy__book__category']
        category = Category.objects.get(id=category_id)

        books_not_rented = (
            Book.objects.filter(category=category)
            .exclude(copies__rentals__user=user)
            .distinct()
        )

        recommended_books.extend(books_not_rented[:3])

        if len(recommended_books) >= 3:
            break

    return recommended_books[:3]
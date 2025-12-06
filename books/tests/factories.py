import factory
from factory.django import DjangoModelFactory
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from books.models import (
    Category, Book, CustomUser, Badge, BookCopy,
    BookRental, Opinion, Notification
)

class CustomUserFactory(DjangoModelFactory):
    class Meta:
        model = CustomUser
        django_get_or_create = ('username',)

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.Faker('email')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    phone = factory.Faker('phone_number')
    is_employee = False
    is_admin = False
    is_active = True
    password = factory.PostGenerationMethodCall('set_password', 'defaultpassword123')

    class Params:
        employee = factory.Trait(is_employee=True, is_admin=False)
        user = factory.Trait(is_employee=False, is_admin=False)
        admin = factory.Trait(is_employee=True, is_admin=True)


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f'Category {n}')
    description = factory.Faker('text', max_nb_chars=200)


class BookFactory(DjangoModelFactory):
    class Meta:
        model = Book

    title = factory.Faker('sentence', nb_words=4)
    author = factory.Faker('name')
    category = factory.SubFactory(CategoryFactory)
    published_date = factory.Faker('date_between', start_date='-30y', end_date='today')
    isbn = factory.Sequence(lambda n: f'978{n:010d}')
    description = factory.Faker('text', max_nb_chars=500)
    total_copies = factory.Faker('random_int', min=1, max=50)
    ai_image = factory.django.ImageField(color='blue')


class BadgeFactory(DjangoModelFactory):
    class Meta:
        model = Badge

    user = factory.SubFactory(CustomUserFactory)
    first_book = False
    ten_books = False
    twenty_books = False
    hundred_books = False
    three_categories = False


class BookCopyFactory(DjangoModelFactory):
    class Meta:
        model = BookCopy

    book = factory.SubFactory(BookFactory)
    is_available = True
    borrower = None

    class Params:
        available = factory.Trait(is_available=True)
        unavailable = factory.Trait(is_available=False)


class BookRentalFactory(DjangoModelFactory):
    class Meta:
        model = BookRental

    book_copy = factory.SubFactory(BookCopyFactory)
    user = factory.SubFactory(CustomUserFactory)
    rental_date = factory.LazyFunction(lambda: timezone.now().date())
    due_date = factory.LazyAttribute(lambda o: o.rental_date + timedelta(days=30))
    return_date = None
    is_extended = False
    status = 'rented'
    fine = None

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override create to handle auto_now_add field for rental_date"""
        rental_date = kwargs.pop('rental_date', None)
        obj = super()._create(model_class, *args, **kwargs)
        if rental_date is not None:
            model_class.objects.filter(pk=obj.pk).update(rental_date=rental_date)
            obj.refresh_from_db()
        return obj

    class Params:
        rented = factory.Trait(
            status='rented'
        )

        returned = factory.Trait(
            status='returned',
            return_date=factory.LazyFunction(lambda: timezone.now().date())
        )

        overdue = factory.Trait(
            status='overdue',
            rental_date=factory.LazyFunction(
                lambda: (timezone.now() - timedelta(days=35)).date()
            ),
            fine=Decimal('5.00')
        )

        pending = factory.Trait(
            status='pending'
        )

        extended = factory.Trait(
            is_extended=True,
            due_date=factory.LazyAttribute(lambda o: o.rental_date + timedelta(days=60))
        )

    @factory.post_generation
    def set_book_copy_unavailable(obj, create, extracted, **kwargs):
        """Automatycznie ustawia kopię jako niedostępną po wypożyczeniu"""
        if not create:
            return

        if obj.status != 'returned':
            obj.book_copy.is_available = False
            obj.book_copy.borrower = obj.user
            obj.book_copy.save()
        else:
            obj.book_copy.is_available = True
            obj.book_copy.borrower = None
            obj.book_copy.save()

class OpinionFactory(DjangoModelFactory):
    class Meta:
        model = Opinion

    book = factory.SubFactory(BookFactory)
    user = factory.SubFactory(CustomUserFactory)
    rate = factory.Faker('random_int', min=1, max=5)
    comment = factory.Faker('text', max_nb_chars=250)
    created_at = factory.LazyFunction(lambda: timezone.now().date())

    class Params:
        positive = factory.Trait(rate=factory.Faker('random_int', min=4, max=5))
        negative = factory.Trait(rate=1)


class NotificationFactory(DjangoModelFactory):
    class Meta:
        model = Notification

    user = factory.SubFactory(CustomUserFactory)
    book = factory.SubFactory(BookFactory)
    is_available = True
    message = factory.Faker('sentence', nb_words=10)
    is_read = False
    created_at = factory.LazyFunction(timezone.now)

    class Params:
        read = factory.Trait(is_read=True)
        unread = factory.Trait(is_read=False)

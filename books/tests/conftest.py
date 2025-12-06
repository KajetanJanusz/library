import pytest
from django.test import Client
from pytest_factoryboy import register

from books.tests.factories import (
    CustomUserFactory,
    BookRentalFactory,
    BookFactory,
    BookCopyFactory,
    CategoryFactory,
    BadgeFactory,
    OpinionFactory,
    NotificationFactory,
)

register(CustomUserFactory)
register(BookRentalFactory)
register(BookFactory)
register(BookCopyFactory)
register(CategoryFactory)
register(BadgeFactory)
register(OpinionFactory)
register(NotificationFactory)

@pytest.fixture
def client(user):
    client = Client()
    client.force_login(user)
    return client

@pytest.fixture
def user():
    return CustomUserFactory(user=True)


@pytest.fixture
def admin_user():
    return CustomUserFactory(admin=True)


@pytest.fixture
def employee_user():
    return CustomUserFactory(employee=True)


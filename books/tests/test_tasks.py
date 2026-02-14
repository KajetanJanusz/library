from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone

from books.tasks import check_overdue_books


@pytest.mark.django_db
class TestCheckOverdueBooks:
    @pytest.fixture(autouse=True)
    def mock_send_mail(self):
        with patch('books.tasks.send_mail') as mock:
            yield mock

    def test_marks_overdue_rental_as_overdue(self, book_rental_factory):
        # Arrange
        rental = book_rental_factory(rented=True)
        rental.due_date = timezone.now().date() - timedelta(days=5)
        rental.save()

        # Act
        check_overdue_books()

        # Assert
        rental.refresh_from_db()
        assert rental.status == 'overdue'

    def test_calculates_fine_for_overdue_rental(self, book_rental_factory):
        # Arrange
        rental = book_rental_factory(rented=True)
        rental.due_date = timezone.now().date() - timedelta(days=10)
        rental.save()

        # Act
        check_overdue_books()

        # Assert
        rental.refresh_from_db()
        assert rental.fine == Decimal('5.00')

    def test_sends_overdue_notification(self, book_rental_factory, mock_send_mail):
        # Arrange
        rental = book_rental_factory(rented=True)
        rental.due_date = timezone.now().date() - timedelta(days=3)
        rental.save()

        # Act
        check_overdue_books()

        # Assert
        assert mock_send_mail.called

    def test_sends_upcoming_due_notification(self, book_rental_factory, mock_send_mail):
        # Arrange
        rental = book_rental_factory(rented=True)
        rental.due_date = timezone.now().date() + timedelta(days=7)
        rental.save()

        # Act
        check_overdue_books()

        # Assert
        assert mock_send_mail.called

    def test_does_not_change_already_returned_rental(self, book_rental_factory):
        # Arrange
        rental = book_rental_factory(returned=True)
        rental.due_date = timezone.now().date() - timedelta(days=5)
        rental.save()

        # Act
        check_overdue_books()

        # Assert
        rental.refresh_from_db()
        assert rental.status == 'returned'

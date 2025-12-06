from datetime import timedelta
from unittest.mock import Mock, patch
from decimal import Decimal

import pytest
from django.urls import reverse

from books.models import BookRental, Badge


@pytest.fixture
def three_rentals(user, book_rental_factory):
    return [book_rental_factory(user=user, rented=True) for _ in range(3)]


@pytest.fixture
def other_user(custom_user_factory):
    return custom_user_factory(user=True)


@pytest.mark.django_db
class TestDashboardClientView:
    @pytest.fixture(autouse=True)
    def mock_model_response(self):
        mock_response = Mock()
        mock_response.text = (
            " 1. *Książka A* - bo pasuje "
            " 2. *Książka B* - świetny wybór "
            " 3. *Książka C* - polecam"
        )

        with patch('books.ai.model.generate_content', return_value=mock_response) as mock:
            yield mock

    def test_dashboard_client_view(self, client, user, three_rentals):
        # Arrange
        client.force_login(user)

        # Act
        response = client.get(reverse('dashboard_client', kwargs={'pk': user.pk}))

        # Assert
        response_context_data = response.context_data
        assert response.status_code == 200
        assert response_context_data['ai_recommendations'] == [
            "Książka A - bo pasuje",
            "Książka B - świetny wybór",
            "Książka C - polecam",
        ]
        assert {rental.id for rental in three_rentals} == {rental.id for rental in response_context_data['rented_books']}
        assert not response_context_data['notifications']
        assert not response_context_data['rented_books_old']
        assert not response_context_data['opinions']
        assert response_context_data['all_my_rents'] == 3

    def test_login_required(self, client, user):
        # Arrange
        client.logout()

        # Act
        response = client.get(reverse('dashboard_client', kwargs={'pk': user.pk}))

        # Assert
        assert response.status_code == 302
        assert '/' == response.url

    def test_admin_redirects_to_employee_dashboard(self, client, admin_user):
        # Arrange
        client.force_login(admin_user)

        # Act
        response = client.get(reverse('dashboard_client', kwargs={'pk': admin_user.pk}))

        # Assert
        assert response.status_code == 302
        assert 'dashboard_employee' in response.url or f'/employee/{admin_user.pk}' in response.url

    def test_rented_books_shows_only_active_rentals(self, client, user, book_rental_factory):
        # Arrange
        client.force_login(user)
        rented = book_rental_factory(user=user, rented=True)
        pending = book_rental_factory(user=user, pending=True)
        overdue = book_rental_factory(user=user, overdue=True)
        returned = book_rental_factory(user=user, returned=True)

        # Act
        response = client.get(reverse('dashboard_client', kwargs={'pk': user.pk}))

        # Assert
        rented_books = response.context_data['rented_books']
        rented_books_old = response.context_data['rented_books_old']

        assert rented in rented_books
        assert pending in rented_books
        assert overdue in rented_books
        assert returned not in rented_books
        assert returned in rented_books_old

    def test_notifications_shows_only_unread_and_available(self, client, user, notification_factory):
        # Arrange
        client.force_login(user)
        unread_available = notification_factory(user=user, is_read=False, is_available=True)
        read_available = notification_factory(user=user, is_read=True, is_available=True)
        unread_unavailable = notification_factory(user=user, is_read=False, is_available=False)

        # Act
        response = client.get(reverse('dashboard_client', kwargs={'pk': user.pk}))

        # Assert
        notifications = response.context_data['notifications']
        assert unread_available in notifications
        assert read_available not in notifications
        assert unread_unavailable not in notifications

    def test_opinions_shows_only_user_opinions(self, client, user, other_user, book_factory, opinion_factory):
        # Arrange
        client.force_login(user)
        book = book_factory()
        user_opinion = opinion_factory(user=user, book=book)
        other_opinion = opinion_factory(user=other_user, book=book)

        # Act
        response = client.get(reverse('dashboard_client', kwargs={'pk': user.pk}))

        # Assert
        opinions = response.context_data['opinions']
        assert user_opinion in opinions
        assert other_opinion not in opinions

    def test_all_my_rents_counts_all_user_rentals(self, client, user, other_user, book_rental_factory):
        # Arrange
        client.force_login(user)
        book_rental_factory.create_batch(5, user=user)
        book_rental_factory.create_batch(3, user=other_user)

        # Act
        response = client.get(reverse('dashboard_client', kwargs={'pk': user.pk}))

        # Assert
        assert response.context_data['all_my_rents'] == 5

    def test_context_contains_badges(self, client, user):
        # Arrange
        client.force_login(user)

        # Act
        response = client.get(reverse('dashboard_client', kwargs={'pk': user.pk}))

        # Assert
        assert 'badges' in response.context_data
        assert response.context_data['badges'].user == user

    def test_context_contains_ai_fun_fact(self, client, user, three_rentals):
        # Arrange
        client.force_login(user)

        # Act
        response = client.get(reverse('dashboard_client', kwargs={'pk': user.pk}))

        # Assert
        assert 'ai_fun_fact' in response.context_data

    def test_books_in_categories_aggregation(self, client, user, book_rental_factory, category_factory, book_factory, book_copy_factory):
        # Arrange
        client.force_login(user)
        category1 = category_factory(name='Fantasy')
        category2 = category_factory(name='Sci-Fi')
        book1 = book_factory(category=category1)
        book2 = book_factory(category=category1)
        book3 = book_factory(category=category2)

        copy1 = book_copy_factory(book=book1)
        copy2 = book_copy_factory(book=book2)
        copy3 = book_copy_factory(book=book3)

        book_rental_factory(user=user, book_copy=copy1, rented=True)
        book_rental_factory(user=user, book_copy=copy2, rented=True)
        book_rental_factory(user=user, book_copy=copy3, rented=True)

        # Act
        response = client.get(reverse('dashboard_client', kwargs={'pk': user.pk}))

        # Assert
        books_in_categories = list(response.context_data['books_in_categories'])
        assert len(books_in_categories) == 2

        fantasy_count = next((c['count'] for c in books_in_categories if c['book_copy__book__category__name'] == 'Fantasy'), 0)
        scifi_count = next((c['count'] for c in books_in_categories if c['book_copy__book__category__name'] == 'Sci-Fi'), 0)

        assert fantasy_count == 2
        assert scifi_count == 1

    def test_less_than_3_rentals_shows_message(self, client, user, book_rental_factory):
        # Arrange
        client.force_login(user)
        book_rental_factory.create_batch(2, user=user, rented=True)

        # Act
        with patch('books.ai.get_ai_book_recommendations') as mock_recommendations:
            mock_recommendations.return_value = ["Musisz przeczytać więcej niż 3 książki, aby otrzymać rekomendacje AI."]
            # Clear session to force new recommendations
            session = client.session
            if 'ai_recommendations' in session:
                del session['ai_recommendations']
            session.save()

            response = client.get(reverse('dashboard_client', kwargs={'pk': user.pk}))

        # Assert
        assert response.status_code == 200

    def test_overdue_rental_has_fine(self, client, user, book_rental_factory):
        # Arrange
        client.force_login(user)
        overdue_rental = book_rental_factory(user=user, overdue=True)

        # Act
        response = client.get(reverse('dashboard_client', kwargs={'pk': user.pk}))

        # Assert
        assert overdue_rental.fine is not None
        assert overdue_rental.fine == Decimal('5.00')
        assert overdue_rental in response.context_data['rented_books']

    def test_average_user_rents_calculation(self, client, user, other_user, book_rental_factory, custom_user_factory):
        # Arrange
        client.force_login(user)
        book_rental_factory.create_batch(4, user=user)
        book_rental_factory.create_batch(6, user=other_user)

        third_user = custom_user_factory(user=True)
        book_rental_factory.create_batch(2, user=third_user)

        # Act
        response = client.get(reverse('dashboard_client', kwargs={'pk': user.pk}))

        # Assert
        # Average for other users: (6 + 2) / 2 = 4.0
        assert response.context_data['avarage_user_rents'] == 4.0


@pytest.mark.django_db
class TestArticlesView:
    @pytest.fixture(autouse=True)
    def mock_get_five_book_articles(self):
        mock_articles = [
            {
                'source': 'lubimyczytac.pl',
                'title': 'Artykuł testowy 1',
                'description': 'Opis artykułu 1',
                'link': 'https://lubimyczytac.pl/artykul/1'
            },
            {
                'source': 'zacofany-w-lekturze.pl',
                'title': 'Artykuł testowy 2',
                'description': 'Opis artykułu 2',
                'link': 'https://zacofany-w-lekturze.pl/artykul/2'
            },
        ]

        with patch('books.views.get_five_book_articles', return_value=mock_articles) as mock:
            yield mock

    def test_articles_view_returns_articles(self, client, user):
        # Arrange
        client.force_login(user)

        # Act
        response = client.get(reverse('articles'))

        # Assert
        assert response.status_code == 200
        assert 'articles' in response.context
        articles = response.context['articles']
        assert len(articles) == 2
        assert articles[0]['title'] == 'Artykuł testowy 1'
        assert articles[1]['title'] == 'Artykuł testowy 2'

    def test_articles_view_requires_login(self, client, user):
        # Arrange
        client.logout()

        # Act
        response = client.get(reverse('articles'))

        # Assert
        assert response.status_code == 302


@pytest.mark.django_db
class TestMarkNotificationAsReadView:
    def test_marks_notification_as_read(self, client, user, notification_factory):
        # Arrange
        client.force_login(user)
        notification = notification_factory(user=user, is_read=False, is_available=True)

        # Act
        response = client.post(reverse('mark_as_read', kwargs={'pk': notification.pk}))

        # Assert
        notification.refresh_from_db()
        assert notification.is_read is True
        assert response.status_code == 302


@pytest.mark.django_db
class TestBorrowBookView:
    def test_borrow_book_success(self, client, user, book_factory, book_copy_factory):
        # Arrange
        client.force_login(user)
        book = book_factory()
        book_copy = book_copy_factory(book=book, is_available=True)

        # Act
        response = client.post(reverse('borrow_book', kwargs={'pk': book.pk}))

        # Assert
        book_copy.refresh_from_db()
        assert book_copy.is_available is False
        assert book_copy.borrower == user
        assert response.status_code == 302

    def test_borrow_book_no_available_copy(self, client, user, book_factory, book_copy_factory):
        # Arrange
        client.force_login(user)
        book = book_factory()
        book_copy_factory(book=book, is_available=False)

        # Act
        response = client.post(reverse('borrow_book', kwargs={'pk': book.pk}))

        # Assert
        assert response.status_code == 302

    def test_borrow_book_already_rented_same_book(self, client, user, book_rental_factory):
        # Arrange
        client.force_login(user)
        rental = book_rental_factory(user=user, rented=True)
        book = rental.book_copy.book

        # Act
        response = client.post(reverse('borrow_book', kwargs={'pk': book.pk}))

        # Assert
        assert response.status_code == 302

    def test_borrow_book_max_rentals_reached(self, client, user, book_factory, book_copy_factory, book_rental_factory):
        # Arrange
        client.force_login(user)
        book_rental_factory.create_batch(3, user=user, rented=True)
        book = book_factory()
        book_copy_factory(book=book, is_available=True)

        # Act
        response = client.post(reverse('borrow_book', kwargs={'pk': book.pk}))

        # Assert
        assert response.status_code == 302

    def test_borrow_book_creates_rental(self, client, user, book_factory, book_copy_factory):
        # Arrange
        client.force_login(user)
        book = book_factory()
        book_copy_factory(book=book, is_available=True)

        # Act
        initial_count = BookRental.objects.filter(user=user).count()
        client.post(reverse('borrow_book', kwargs={'pk': book.pk}))

        # Assert
        assert BookRental.objects.filter(user=user).count() == initial_count + 1

    def test_borrow_book_grants_first_book_badge(self, client, user, book_factory, book_copy_factory):
        # Arrange
        client.force_login(user)
        book = book_factory()
        book_copy_factory(book=book, is_available=True)

        # Act
        client.post(reverse('borrow_book', kwargs={'pk': book.pk}))

        # Assert
        badge = Badge.objects.get(user=user)
        assert badge.first_book is True


@pytest.mark.django_db
class TestReturnBookView:
    def test_return_book_changes_status_to_pending(self, client, user, book_rental_factory):
        # Arrange
        client.force_login(user)
        rental = book_rental_factory(user=user, rented=True)

        # Act
        client.post(reverse('return_book', kwargs={'pk': rental.pk}))

        # Assert
        rental.refresh_from_db()
        assert rental.status == 'pending'

    def test_return_book_other_user_rental(self, client, user, other_user, book_rental_factory):
        # Arrange
        client.force_login(user)
        rental = book_rental_factory(user=other_user, rented=True)

        # Act
        response = client.post(reverse('return_book', kwargs={'pk': rental.pk}))

        # Assert
        rental.refresh_from_db()
        assert response.status_code == 302
        assert rental.status == 'rented'


@pytest.mark.django_db
class TestExtendRentalPeriodView:
    def test_extend_rental_adds_7_days(self, client, user, book_rental_factory):
        # Arrange
        client.force_login(user)
        rental = book_rental_factory(user=user, rented=True)
        original_due_date = rental.due_date

        # Act
        client.post(reverse('extend_book', kwargs={'pk': rental.pk}))

        # Assert
        rental.refresh_from_db()
        assert rental.due_date == original_due_date + timedelta(days=7)
        assert rental.is_extended is True

    def test_extend_rental_cannot_extend_twice(self, client, user, book_rental_factory):
        # Arrange
        client.force_login(user)
        rental = book_rental_factory(user=user, rented=True)
        rental.is_extended = True
        rental.save()
        original_due_date = rental.due_date

        # Act
        response = client.post(reverse('extend_book', kwargs={'pk': rental.pk}))

        # Assert
        rental.refresh_from_db()
        assert response.status_code == 302
        assert rental.due_date == original_due_date


@pytest.mark.django_db
class TestListBooksView:
    def test_list_books_returns_books(self, client, user, book_factory):
        # Arrange
        client.force_login(user)
        book1 = book_factory(title='Władca Pierścieni')
        book2 = book_factory(title='Hobbit')

        # Act
        response = client.get(reverse('list_books'))

        # Assert
        assert response.status_code == 200
        books = response.context['books']
        assert book1 in books
        assert book2 in books

    def test_list_books_search_by_title(self, client, user, book_factory):
        # Arrange
        client.force_login(user)
        book1 = book_factory(title='Władca Pierścieni')
        book2 = book_factory(title='Hobbit')

        # Act
        response = client.get(reverse('list_books'), {'q': 'Władca'})

        # Assert
        books = response.context['books']
        assert book1 in books
        assert book2 not in books

    def test_list_books_search_by_author(self, client, user, book_factory):
        # Arrange
        client.force_login(user)
        book1 = book_factory(author='J.R.R. Tolkien')
        book2 = book_factory(author='Stephen King')

        # Act
        response = client.get(reverse('list_books'), {'q': 'Tolkien'})

        # Assert
        books = response.context['books']
        assert book1 in books
        assert book2 not in books

    def test_list_books_available_copies_count(self, client, user, book_factory, book_copy_factory):
        # Arrange
        client.force_login(user)
        book = book_factory()
        book_copy_factory(book=book, is_available=True)
        book_copy_factory(book=book, is_available=True)
        book_copy_factory(book=book, is_available=False)

        # Act
        response = client.get(reverse('list_books'))

        # Assert
        books = list(response.context['books'])
        book_from_context = next(b for b in books if b.id == book.id)
        assert book_from_context.available_copies == 2


@pytest.mark.django_db
class TestDetailBookView:
    def test_detail_book_returns_book(self, client, user, book_factory):
        # Arrange
        client.force_login(user)
        book = book_factory()

        # Act
        response = client.get(reverse('detail_book', kwargs={'pk': book.pk}))

        # Assert
        assert response.status_code == 200
        assert response.context['book'] == book

    def test_detail_book_shows_opinions(self, client, user, book_factory, opinion_factory):
        # Arrange
        client.force_login(user)
        book = book_factory()
        opinion = opinion_factory(book=book)

        # Act
        response = client.get(reverse('detail_book', kwargs={'pk': book.pk}))

        # Assert
        assert opinion in response.context['opinions']

    def test_detail_book_shows_comment_form_when_user_rented(self, client, user, book_rental_factory):
        # Arrange
        client.force_login(user)
        rental = book_rental_factory(user=user, rented=True)
        book = rental.book_copy.book

        # Act
        response = client.get(reverse('detail_book', kwargs={'pk': book.pk}))

        # Assert
        assert 'comment_form' in response.context

    def test_detail_book_no_comment_form_when_user_not_rented(self, client, user, book_factory):
        # Arrange
        client.force_login(user)
        book = book_factory()

        # Act
        response = client.get(reverse('detail_book', kwargs={'pk': book.pk}))

        # Assert
        assert 'comment_form' not in response.context

    def test_detail_book_available_copies_count(self, client, user, book_factory, book_copy_factory):
        # Arrange
        client.force_login(user)
        book = book_factory()
        book_copy_factory(book=book, is_available=True)
        book_copy_factory(book=book, is_available=False)

        # Act
        response = client.get(reverse('detail_book', kwargs={'pk': book.pk}))

        # Assert
        assert response.context['available_copies'] == 1
        assert response.context['copies_available'] is True


@pytest.mark.django_db
class TestSubscribeBookView:
    def test_subscribe_creates_notification(self, client, user, book_factory):
        # Arrange
        client.force_login(user)
        book = book_factory()

        # Act
        from books.models import Notification
        initial_count = Notification.objects.filter(user=user, book=book).count()
        client.post(reverse('subscribe_book', kwargs={'pk': book.pk}))

        # Assert
        assert Notification.objects.filter(user=user, book=book).count() == initial_count + 1

    def test_subscribe_does_not_duplicate(self, client, user, book_factory, notification_factory):
        # Arrange
        client.force_login(user)
        book = book_factory()
        notification_factory(user=user, book=book, is_available=False)

        # Act
        from books.models import Notification
        initial_count = Notification.objects.filter(user=user, book=book).count()
        client.post(reverse('subscribe_book', kwargs={'pk': book.pk}))

        # Assert
        assert Notification.objects.filter(user=user, book=book).count() == initial_count


@pytest.mark.django_db
class TestDashboardEmployeeView:
    def test_employee_can_access_dashboard(self, client, employee_user):
        # Arrange
        client.force_login(employee_user)

        # Act
        response = client.get(reverse('dashboard_employee', kwargs={'pk': employee_user.pk}))

        # Assert
        assert response.status_code == 200

    def test_regular_user_cannot_access_dashboard(self, client, user):
        # Arrange
        client.force_login(user)

        # Act
        response = client.get(reverse('dashboard_employee', kwargs={'pk': user.pk}))

        # Assert
        assert response.status_code == 302

    def test_context_contains_rented_books(self, client, employee_user, book_rental_factory):
        # Arrange
        client.force_login(employee_user)
        rental = book_rental_factory(rented=True)

        # Act
        response = client.get(reverse('dashboard_employee', kwargs={'pk': employee_user.pk}))

        # Assert
        assert rental in response.context['rented_books']

    def test_context_contains_overdue_rentals(self, client, employee_user, book_rental_factory):
        # Arrange
        client.force_login(employee_user)
        overdue = book_rental_factory(overdue=True)

        # Act
        response = client.get(reverse('dashboard_employee', kwargs={'pk': employee_user.pk}))

        # Assert
        assert overdue in response.context['overdue_rentals']

    def test_context_contains_pending_returns(self, client, employee_user, book_rental_factory):
        # Arrange
        client.force_login(employee_user)
        pending = book_rental_factory(pending=True)

        # Act
        response = client.get(reverse('dashboard_employee', kwargs={'pk': employee_user.pk}))

        # Assert
        assert pending in response.context['returns_to_approve']

    def test_context_contains_customers(self, client, employee_user, custom_user_factory):
        # Arrange
        client.force_login(employee_user)
        customer = custom_user_factory(user=True)

        # Act
        response = client.get(reverse('dashboard_employee', kwargs={'pk': employee_user.pk}))

        # Assert
        assert customer in response.context['customers']

    def test_most_rented_books_aggregation(self, client, employee_user, book_rental_factory, book_factory, book_copy_factory):
        # Arrange
        client.force_login(employee_user)
        book1 = book_factory(title='Popularna książka')
        book2 = book_factory(title='Mniej popularna')
        copy1 = book_copy_factory(book=book1)
        copy2 = book_copy_factory(book=book2)
        book_rental_factory.create_batch(5, book_copy=copy1)
        book_rental_factory.create_batch(2, book_copy=copy2)

        # Act
        response = client.get(reverse('dashboard_employee', kwargs={'pk': employee_user.pk}))

        # Assert
        most_rented = list(response.context['most_rented_books'])
        assert most_rented[0]['book_copy__book__title'] == 'Popularna książka'
        assert most_rented[0]['rental_count'] == 5

    def test_total_rentals_count(self, client, employee_user, book_rental_factory):
        # Arrange
        client.force_login(employee_user)
        book_rental_factory.create_batch(7)

        # Act
        response = client.get(reverse('dashboard_employee', kwargs={'pk': employee_user.pk}))

        # Assert
        assert response.context['total_rentals'] == 7

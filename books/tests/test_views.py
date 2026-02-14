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

    def test_total_rentals_count(self, client, employee_user, book_rental_factory, book_copy_factory):
        # Arrange
        client.force_login(employee_user)
        book_copy = book_copy_factory()
        book_rental_factory.create_batch(7, book_copy=book_copy)

        # Act
        response = client.get(reverse('dashboard_employee', kwargs={'pk': employee_user.pk}))

        # Assert
        assert response.context['total_rentals'] == 7


@pytest.mark.django_db
class TestAddBookFormView:
    @pytest.fixture(autouse=True)
    def mock_ai_description(self):
        with patch('books.views.get_ai_generated_description', return_value='Opis wygenerowany przez AI') as mock:
            yield mock

    def test_employee_can_access_form(self, client, employee_user):
        # Arrange
        client.force_login(employee_user)

        # Act
        response = client.get(reverse('add_book_form'))

        # Assert
        assert response.status_code == 200

    def test_regular_user_cannot_access_form(self, client, user):
        # Arrange
        client.force_login(user)

        # Act
        response = client.get(reverse('add_book_form'))

        # Assert
        assert response.status_code == 302

    def test_form_valid_saves_data_to_session(self, client, employee_user, category_factory):
        # Arrange
        client.force_login(employee_user)
        category = category_factory()

        # Act
        response = client.post(reverse('add_book_form'), {
            'title': 'Testowa książka',
            'author': 'Jan Kowalski',
            'category': category.pk,
            'isbn': '1234567890123',
            'published_date': '2020-01-01',
            'total_copies': 5,
        })

        # Assert
        session = client.session
        assert session['book_form_data']['title'] == 'Testowa książka'
        assert session['book_form_data']['author'] == 'Jan Kowalski'
        assert session['ai_description'] == 'Opis wygenerowany przez AI'

    def test_form_valid_redirects_to_confirm(self, client, employee_user, category_factory):
        # Arrange
        client.force_login(employee_user)
        category = category_factory()

        # Act
        response = client.post(reverse('add_book_form'), {
            'title': 'Testowa książka',
            'author': 'Jan Kowalski',
            'category': category.pk,
            'isbn': '1234567890123',
            'published_date': '2020-01-01',
            'total_copies': 5,
        })

        # Assert
        assert response.status_code == 302
        assert 'confirm-description' in response.url


@pytest.mark.django_db
class TestConfirmBookDescriptionView:
    @pytest.fixture(autouse=True)
    def mock_generate_image(self):
        with patch('books.models.generate_and_save_image', return_value=None):
            yield

    def test_redirects_when_no_session_data(self, client, employee_user):
        # Arrange
        client.force_login(employee_user)

        # Act
        response = client.get(reverse('confirm_book_description'))

        # Assert
        assert response.status_code == 302
        assert 'book/add' in response.url

    def test_displays_book_data_from_session(self, client, employee_user, category_factory):
        # Arrange
        client.force_login(employee_user)
        category = category_factory()
        session = client.session
        session['book_form_data'] = {
            'title': 'Testowa książka',
            'author': 'Jan Kowalski',
            'category': category.pk,
            'isbn': '1234567890123',
            'published_date': '2020-01-01',
            'total_copies': 5,
        }
        session['ai_description'] = 'Opis AI'
        session.save()

        # Act
        response = client.get(reverse('confirm_book_description'))

        # Assert
        assert response.status_code == 200
        assert response.context['book_data']['title'] == 'Testowa książka'

    def test_form_valid_creates_book(self, client, employee_user, category_factory):
        # Arrange
        client.force_login(employee_user)
        category = category_factory()
        session = client.session
        session['book_form_data'] = {
            'title': 'Nowa książka',
            'author': 'Adam Nowak',
            'category': category.pk,
            'isbn': '9876543210123',
            'published_date': '2021-05-15',
            'total_copies': 3,
        }
        session['ai_description'] = 'Opis AI'
        session.save()

        # Act
        from books.models import Book
        initial_count = Book.objects.count()
        client.post(reverse('confirm_book_description'), {'description': 'Finalny opis książki'})

        # Assert
        assert Book.objects.count() == initial_count + 1
        book = Book.objects.get(title='Nowa książka')
        assert book.description == 'Finalny opis książki'

    def test_form_valid_creates_copies(self, client, employee_user, category_factory):
        # Arrange
        client.force_login(employee_user)
        category = category_factory()
        session = client.session
        session['book_form_data'] = {
            'title': 'Książka z kopiami',
            'author': 'Autor',
            'category': category.pk,
            'isbn': '1111111111111',
            'published_date': '2022-01-01',
            'total_copies': 4,
        }
        session['ai_description'] = 'Opis'
        session.save()

        # Act
        from books.models import Book, BookCopy
        client.post(reverse('confirm_book_description'), {'description': 'Opis'})

        # Assert
        book = Book.objects.get(title='Książka z kopiami')
        assert BookCopy.objects.filter(book=book).count() == 4

    def test_form_valid_clears_session(self, client, employee_user, category_factory):
        # Arrange
        client.force_login(employee_user)
        category = category_factory()
        session = client.session
        session['book_form_data'] = {
            'title': 'Książka',
            'author': 'Autor',
            'category': category.pk,
            'isbn': '2222222222222',
            'published_date': '2022-01-01',
            'total_copies': 1,
        }
        session['ai_description'] = 'Opis'
        session.save()

        # Act
        client.post(reverse('confirm_book_description'), {'description': 'Opis'})

        # Assert
        session = client.session
        assert 'book_form_data' not in session
        assert 'ai_description' not in session


@pytest.mark.django_db
class TestEditBookView:
    def test_employee_can_access_edit_form(self, client, employee_user, book_factory):
        # Arrange
        client.force_login(employee_user)
        book = book_factory()

        # Act
        response = client.get(reverse('edit_book', kwargs={'pk': book.pk}))

        # Assert
        assert response.status_code == 200

    def test_regular_user_cannot_access_edit_form(self, client, user, book_factory):
        # Arrange
        client.force_login(user)
        book = book_factory()

        # Act
        response = client.get(reverse('edit_book', kwargs={'pk': book.pk}))

        # Assert
        assert response.status_code == 302

    def test_edit_book_updates_title(self, client, employee_user, book_factory, category_factory):
        # Arrange
        client.force_login(employee_user)
        category = category_factory()
        book = book_factory(title='Stary tytuł', category=category, total_copies=2)

        # Act
        client.post(reverse('edit_book', kwargs={'pk': book.pk}), {
            'title': 'Nowy tytuł',
            'author': book.author,
            'category': category.pk,
            'isbn': book.isbn,
            'published_date': book.published_date,
            'total_copies': 2,
            'description': book.description,
        })

        # Assert
        book.refresh_from_db()
        assert book.title == 'Nowy tytuł'

    def test_edit_book_adds_copies(self, client, employee_user, book_factory, book_copy_factory, category_factory):
        # Arrange
        client.force_login(employee_user)
        category = category_factory()
        book = book_factory(category=category, total_copies=2)
        book_copy_factory(book=book)
        book_copy_factory(book=book)

        # Act
        from books.models import BookCopy
        initial_count = BookCopy.objects.filter(book=book).count()
        client.post(reverse('edit_book', kwargs={'pk': book.pk}), {
            'title': book.title,
            'author': book.author,
            'category': category.pk,
            'isbn': book.isbn,
            'published_date': book.published_date,
            'total_copies': 5,
            'description': book.description,
        })

        # Assert
        assert BookCopy.objects.filter(book=book).count() == initial_count + 3

    def test_edit_book_removes_available_copies(self, client, employee_user, book_factory, book_copy_factory, category_factory):
        # Arrange
        client.force_login(employee_user)
        category = category_factory()
        book = book_factory(category=category, total_copies=4)
        book_copy_factory(book=book, is_available=True)
        book_copy_factory(book=book, is_available=True)
        book_copy_factory(book=book, is_available=True)
        book_copy_factory(book=book, is_available=True)

        # Act
        from books.models import BookCopy
        client.post(reverse('edit_book', kwargs={'pk': book.pk}), {
            'title': book.title,
            'author': book.author,
            'category': category.pk,
            'isbn': book.isbn,
            'published_date': book.published_date,
            'total_copies': 2,
            'description': book.description,
        })

        # Assert
        assert BookCopy.objects.filter(book=book).count() == 2

    def test_edit_book_cannot_remove_borrowed_copies(self, client, employee_user, book_factory, book_copy_factory, category_factory):
        # Arrange
        client.force_login(employee_user)
        category = category_factory()
        book = book_factory(category=category, total_copies=3)
        book_copy_factory(book=book, is_available=True)
        book_copy_factory(book=book, is_available=False)
        book_copy_factory(book=book, is_available=False)

        # Act
        from books.models import BookCopy
        response = client.post(reverse('edit_book', kwargs={'pk': book.pk}), {
            'title': book.title,
            'author': book.author,
            'category': category.pk,
            'isbn': book.isbn,
            'published_date': book.published_date,
            'total_copies': 1,
            'description': book.description,
        })

        # Assert
        assert BookCopy.objects.filter(book=book).count() == 3


@pytest.mark.django_db
class TestDeleteBookView:
    def test_employee_can_access_delete_page(self, client, employee_user, book_factory):
        # Arrange
        client.force_login(employee_user)
        book = book_factory()

        # Act
        response = client.get(reverse('delete_book', kwargs={'pk': book.pk}))

        # Assert
        assert response.status_code == 200

    def test_regular_user_cannot_access_delete_page(self, client, user, book_factory):
        # Arrange
        client.force_login(user)
        book = book_factory()

        # Act
        response = client.get(reverse('delete_book', kwargs={'pk': book.pk}))

        # Assert
        assert response.status_code == 302

    def test_delete_book_removes_book(self, client, employee_user, book_factory):
        # Arrange
        client.force_login(employee_user)
        book = book_factory()
        book_pk = book.pk

        # Act
        from books.models import Book
        client.post(reverse('delete_book', kwargs={'pk': book.pk}))

        # Assert
        assert not Book.objects.filter(pk=book_pk).exists()

    def test_delete_book_redirects(self, client, employee_user, book_factory):
        # Arrange
        client.force_login(employee_user)
        book = book_factory()

        # Act
        response = client.post(reverse('delete_book', kwargs={'pk': book.pk}))

        # Assert
        assert response.status_code == 302


@pytest.mark.django_db
class TestApproveReturnView:
    def test_approve_return_changes_status(self, client, employee_user, book_rental_factory):
        # Arrange
        client.force_login(employee_user)
        rental = book_rental_factory(pending=True)

        # Act
        client.post(reverse('approve_return', kwargs={'pk': rental.pk}))

        # Assert
        rental.refresh_from_db()
        assert rental.status == 'returned'
        assert rental.return_date is not None

    def test_approve_return_makes_copy_available(self, client, employee_user, book_rental_factory):
        # Arrange
        client.force_login(employee_user)
        rental = book_rental_factory(pending=True)
        book_copy = rental.book_copy

        # Act
        client.post(reverse('approve_return', kwargs={'pk': rental.pk}))

        # Assert
        book_copy.refresh_from_db()
        assert book_copy.is_available is True
        assert book_copy.borrower is None

    def test_approve_return_creates_notification_for_user(self, client, employee_user, book_rental_factory):
        # Arrange
        client.force_login(employee_user)
        rental = book_rental_factory(pending=True)
        rental_user = rental.user
        book = rental.book_copy.book

        # Act
        from books.models import Notification
        client.post(reverse('approve_return', kwargs={'pk': rental.pk}))

        # Assert
        assert Notification.objects.filter(user=rental_user, book=book, is_available=True).exists()

    def test_approve_return_updates_waiting_notifications(self, client, employee_user, book_rental_factory, notification_factory, custom_user_factory):
        # Arrange
        client.force_login(employee_user)
        rental = book_rental_factory(pending=True)
        book = rental.book_copy.book
        waiting_user = custom_user_factory(user=True)
        notification = notification_factory(user=waiting_user, book=book, is_available=False)

        # Act
        client.post(reverse('approve_return', kwargs={'pk': rental.pk}))

        # Assert
        notification.refresh_from_db()
        assert notification.is_available is True

    def test_regular_user_cannot_approve_return(self, client, user, book_rental_factory):
        # Arrange
        client.force_login(user)
        rental = book_rental_factory(pending=True)

        # Act
        response = client.post(reverse('approve_return', kwargs={'pk': rental.pk}))

        # Assert
        assert response.status_code == 302
        rental.refresh_from_db()
        assert rental.status == 'pending'


@pytest.mark.django_db
class TestListBorrowsView:
    def test_employee_can_access_list(self, client, employee_user):
        # Arrange
        client.force_login(employee_user)

        # Act
        response = client.get(reverse('list_borrows'))

        # Assert
        assert response.status_code == 200

    def test_regular_user_cannot_access_list(self, client, user):
        # Arrange
        client.force_login(user)

        # Act
        response = client.get(reverse('list_borrows'))

        # Assert
        assert response.status_code == 302

    def test_list_contains_rentals(self, client, employee_user, book_rental_factory):
        # Arrange
        client.force_login(employee_user)
        rental = book_rental_factory(rented=True)

        # Act
        response = client.get(reverse('list_borrows'))

        # Assert
        assert rental in response.context['object_list']

    def test_rentals_sorted_by_status_priority(self, client, employee_user, book_rental_factory):
        # Arrange
        client.force_login(employee_user)
        returned = book_rental_factory(returned=True)
        overdue = book_rental_factory(overdue=True)
        rented = book_rental_factory(rented=True)

        # Act
        response = client.get(reverse('list_borrows'))

        # Assert
        rentals = list(response.context['object_list'])
        rented_index = rentals.index(rented)
        overdue_index = rentals.index(overdue)
        returned_index = rentals.index(returned)
        assert rented_index < overdue_index < returned_index


@pytest.mark.django_db
class TestListUsersView:
    def test_employee_can_access_list(self, client, employee_user):
        # Arrange
        client.force_login(employee_user)

        # Act
        response = client.get(reverse('list_users'))

        # Assert
        assert response.status_code == 200

    def test_regular_user_cannot_access_list(self, client, user):
        # Arrange
        client.force_login(user)

        # Act
        response = client.get(reverse('list_users'))

        # Assert
        assert response.status_code == 302

    def test_list_contains_only_customers(self, client, employee_user, custom_user_factory):
        # Arrange
        client.force_login(employee_user)
        customer = custom_user_factory(user=True)
        employee = custom_user_factory(employee=True)

        # Act
        response = client.get(reverse('list_users'))

        # Assert
        users = response.context['object_list']
        assert customer in users
        assert employee not in users

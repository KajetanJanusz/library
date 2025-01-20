from datetime import date, timedelta
from typing import Any
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView

from django.contrib import messages
from django.db.models.query import QuerySet
from django.shortcuts import redirect, render, get_object_or_404
from django.http import HttpRequest, HttpResponse
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import DetailView, ListView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count, Case, When, Value, IntegerField, Sum
from django.contrib.auth.views import (
    PasswordResetView, PasswordResetDoneView, 
    PasswordResetConfirmView, PasswordResetCompleteView
)
from django.contrib.auth.forms import PasswordResetForm
from django.core.exceptions import ValidationError

from books.models import Badge, Book, BookRental, BookCopy, Category, Notification, Opinion
from books import forms
from books.mixins import AdminMixin, CustomerMixin, EmployeeMixin
from books.models import CustomUser
from books.helpers import get_five_book_articles
from books.ai import get_ai_book_recommendations, get_ai_generated_description

class DashboardClient(LoginRequiredMixin, CustomerMixin, DetailView):
    """
    Widok pulpitu klienta wyświetlający spersonalizowane informacje użytkownika.

        Funkcje:
        - Wyświetla wypożyczone książki
        - Pokazuje nieprzeczytane powiadomienia
        - Prezentuje opinie użytkownika o książkach
        - Udostępnia rekomendacje książek

        Wymaga logowania i dostępu klienta.
    """
    model = CustomUser
    template_name = "dashboard_client.html"
    context_object_name = "user"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if request.user.is_admin:
            return redirect('dashboard_employee', pk=request.user.id)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.get_object()
        if 'ai_recommendations' in self.request.session:
            ai_recommendations = self.request.session['ai_recommendations']
        else:
            self.request.session['ai_recommendations'] = ai_recommendations = get_ai_book_recommendations(list(BookRental.objects.filter(user=user))) 
        context.update({
            'rented_books': BookRental.objects.filter(Q(user=user.id) & (Q(status='rented') | Q(status='pending') | Q(status='overdue'))),
            'rented_books_old': BookRental.objects.filter(user=user, status='returned'),
            'notifications': Notification.objects.filter(user=user, is_read=False, is_available=True),
            'opinions': Opinion.objects.filter(user=user),
            'ai_recommendations': ai_recommendations,
            'badges': Badge.objects.get(user=user),
            'avarage_user_rents': BookRental.objects.exclude(user=user).count()/(CustomUser.objects.exclude(id=self.request.user.id)).count(),
            'all_my_rents': BookRental.objects.filter(user=user).count(),
            'books_in_categories': BookRental.objects\
                                    .filter(user=user)\
                                    .values('book_copy__book__category__name')\
                                    .annotate(count=Count('book_copy__book__category'))\
                                    .order_by('book_copy__book__category__name')
        })
        return context
    
class ArticlesView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, *args: Any, **kwargs: Any):
        if 'articles' in self.request.session:
            articles = self.request.session['articles']
        else:
            self.request.session['articles'] = articles = get_five_book_articles()

        return render(request, "articles.html", {"articles": articles})

class MarkNotificationAsReadView(LoginRequiredMixin, CustomerMixin, View):
    def post(self, request, *args, **kwargs):
        notification = get_object_or_404(Notification, id=self.kwargs.get('pk'))

        notification.is_read = True
        notification.save()
        return redirect('dashboard_client', pk=request.user.id)

class BorrowBook(LoginRequiredMixin, CustomerMixin, View):
    """
    Widok obsługujący proces wypożyczania książek.
        
        Funkcje:
        - Sprawdza dostępność książki
        - Ogranicza użytkownika do 3 jednoczesnych wypożyczeń
        - Tworzy nowe wypożyczenie
        - Aktualizuje status egzemplarza książki
        
        Wymaga logowania i dostępu klienta.
    """

    def post(self, request, *args, **kwargs):
        book = get_object_or_404(Book, id=self.kwargs.get('pk'))
        user = request.user

        available_copy = BookCopy.objects.select_related('book').filter(book=book, is_available=True).first()
        user_rentals_count = BookRental.objects.filter(Q(user=user.id) & (Q(status='rented') | Q(status='pending'))).count()

        if not available_copy:
            messages.warning(request, "Nie ma wolnych egzemplarzy")
            return redirect('dashboard_client', pk=request.user.id)
        
        if user_rentals_count >= 3:
            messages.warning(request, f"Zwróć inną książkę, żeby wypożyczyć {book.title}")
            return redirect('dashboard_client', pk=request.user.id)

        available_copy.is_available = False
        available_copy.borrower = user
        available_copy.save()

        BookRental.objects.create(
            book_copy=available_copy,
            user=user,
            rental_date=date.today(),
            status='rented'
        )

        rented_books = BookRental.objects.filter(user=user).count()
        categories_read = BookRental.objects.filter(user=user).values('book_copy__book__category').distinct().count()
        if rented_books >= 1 or categories_read >= 3:
            badge, _ = Badge.objects.get_or_create(user=user)

            if rented_books >= 1 and not badge.first_book:
                badge.first_book = True
            elif rented_books >= 10 and not badge.ten_books:
                badge.ten_books = True
            elif rented_books >= 20 and not badge.twenty_books:
                badge.twenty_books = True
            elif rented_books >= 100 and not badge.hundred_books:
                badge.hundred_books = True

            if categories_read >= 3:
                badge.three_categories = True

            badge.save()

        messages.success(request, "Książka wypożyczona")
        return redirect('dashboard_client', pk=request.user.id)

class ReturnBook(LoginRequiredMixin, CustomerMixin, View):
    """
    Widok obsługujący zwrot książki.

        Funkcje:
        - Zmienia status wypożyczenia na 'zwrócony'
        - Wyświetla potwierdzenie zwrotu
        - Przywraca dostępność egzemplarza książki
        - Aktualizuje powiadomienia
        
        Wymaga logowania i dostępu klienta.
    """
    def get(self, request, *args, **kwargs):
        rental = get_object_or_404(BookRental, id=self.kwargs['pk'])
        return render(request, 'confirm_return.html', {'rental': rental})

    def post(self, request, *args, **kwargs):
        rental = get_object_or_404(BookRental, id=self.kwargs['pk'])
        
        rental.status = 'pending'
        rental.save()

        messages.info(request, "Zwrot oczekuje na zatwierdzenie")
        return redirect("dashboard_client", pk=request.user.id)
    
class ExtendRentalPeriodView(LoginRequiredMixin, CustomerMixin, View):
    """
    Widok umożliwiający przedłużenie okresu wypożyczenia.

        Funkcje:
        - Pozwala na jednorazowe przedłużenie wypożyczenia o 7 dni
        - Aktualizuje datę zwrotu
        - Oznacza wypożyczenie jako przedłużone
    
        Wymaga logowania i dostępu klienta.
    """
    def get(self, request, *args, **kwargs):
        rental = get_object_or_404(BookRental, id=self.kwargs['pk'])
        return render(request, 'extend_rental.html', {'rental': rental})

    def post(self, request, *args, **kwargs):
        rental = get_object_or_404(BookRental, id=self.kwargs['pk'])
        
        if not rental.is_extended:
            rental.due_date += timedelta(days=7)
            rental.is_extended = True
            rental.save()

        messages.success(request, "Wypożyczenie przedłużone")
        return redirect("dashboard_client", pk=request.user.id)

class ListBooksView(LoginRequiredMixin, ListView):
    """
    Widok wyświetlający listę książek.

        Funkcje:
        - Wyświetla książki z liczbą dostępnych egzemplarzy
        - Umożliwia wyszukiwanie książek
        - Umożliwia filtrowanie książek po tytule, autorze lub kategorii
        
        Wymaga logowania.
    """
    model = Book
    template_name = "list_books.html"
    context_object_name = "books"
    paginate_by = 8

    def get_queryset(self) -> QuerySet[Any]:
        queryset = Book.objects.prefetch_related('copies')
        query = self.request.GET.get('q')

        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | 
                Q(author__icontains=query) | 
                Q(category__name__icontains=query)
            )

        return queryset.order_by('title')

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['categories'] = list(Category.objects.all())
        
        for book in context['books']:
            book.available_copies = book.copies.filter(is_available=True).count()
        
        return context
    
class DetailBookView(LoginRequiredMixin, DetailView):
    """
    Widok szczegółów książki.

        Funkcje:
        - Wyświetla informacje o konkretnej książce
        - Pokazuje opinie o książce
        - Umożliwia dodanie własnej opinii, jeżeli mamy lub mieliśmy wypożyczoną tę książkę
        - Umożliwia włączenie powiadomień

        Wymaga logowania.
    """
    model = Book
    template_name = 'detail_book.html'
    context_object_name = 'book'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        book = self.get_object()
        
        context.update({
            'opinions': Opinion.objects.filter(book=book),
            'copies': BookCopy.objects.filter(book=book),
            'copies_available': BookCopy.objects.filter(book=book, is_available=True).exists(),
            'available_copies': BookCopy.objects.filter(book=book, is_available=True).count()
        })

        if (BookRental.objects.filter(book_copy__book=book, user=self.request.user).exists() and 
            not Opinion.objects.filter(book=book, user=self.request.user).exists()):
            context['comment_form'] = forms.OpinionForm()
        
        return context
    
    def post(self, request, *args, **kwargs):
        book = self.get_object()
        form = forms.OpinionForm(request.POST)
        
        if form.is_valid():
            try:
                comment = form.save(commit=False)
                comment.book = book
                comment.user = self.request.user
                comment.full_clean()
                comment.save()
                return redirect('detail_book', pk=book.id)
            except ValidationError:
                messages.error(self.request, "Nieprawidłowa ocena")
        
        messages.error(self.request, "Ocena musi być od 0 do 5")
        return redirect('detail_book', pk=book.id)
    
class SubscribeBookView(LoginRequiredMixin, CustomerMixin, View):
    """
    Widok obsługujący subskrypcję powiadomień o książce.

        Funkcje:
        - Włącza powiadomienia o dostępności książki
        - Zapobiega wielokrotnemu dodaniu powiadomienia

        Wymaga logowania i dostępu klienta.
    """
    def post(self, request, *args, **kwargs):
        user = self.request.user
        book = get_object_or_404(Book, id=self.kwargs['pk'])

        _, created = Notification.objects.get_or_create(
            user=user, 
            book=book, 
            is_available=False
        )

        if not created:
            messages.info(request, "Już masz włączone powiadomienia odnośnie tej książki")
        else:
            messages.success(request, "Powiadomienia włączone pomyślnie")
        
        return redirect('dashboard_client', pk=user.id)

class DashboardEmployeeView(LoginRequiredMixin, EmployeeMixin, DetailView):
    """
    Widok pulpitu pracownika.

        Funkcje:
        - Wyświetla statystyki wypożyczeń
        - Pokazuje listę użytkowników
        - Prezentuje najczęściej wypożyczane książki
        - Wyświetla powiadomienia

        Wymaga logowania i dostępu pracownika.
    """
    model = CustomUser
    template_name = "dashboard_employee.html"
    context_object_name = "user"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.get_object()
        
        most_rented_books = (
            BookRental.objects.values('book_copy__book__title')
            .annotate(rental_count=Count('id'))
            .order_by('-rental_count')[:3]
        )
        
        context.update({
            'users_rented_books': BookRental.objects.filter(user=user, status='rented'),
            'rented_books': BookRental.objects.filter(status='rented'),
            'rented_books_old': BookRental.objects.filter(user=user, status='returned'),
            'notifications': Notification.objects.filter(user=user, is_read=False, is_available=True),
            'customers': CustomUser.objects.filter(is_employee=False),
            'all_users': CustomUser.objects.all(),
            'overdue_rentals': BookRental.objects.filter(status='overdue'),
            'most_rented_books': most_rented_books,
            'total_rentals': most_rented_books.aggregate(total=Sum('rental_count'))['total'] or 0,
            'returns_to_approve': BookRental.objects.filter(status='pending')
        })
        
        return context

class AddBookView(LoginRequiredMixin, EmployeeMixin, CreateView):
    """
    Widok dodawania nowej książki.

        Funkcje:
        - Umożliwia wprowadzenie danych nowej książki
        - Tworzy nowe egzemplarze książki

        Wymaga logowania i dostępu pracownika.
    """
    template_name = "add_books.html"
    form_class = forms.AddBookForm
    success_url = reverse_lazy('list_books')

    def form_valid(self, form):
        book = form.save(commit=False)
        total_copies = form.cleaned_data['total_copies']
        title = form.cleaned_data['title']
        author = form.cleaned_data['author']

        ai_description = get_ai_generated_description(title, author)
        book.description = ai_description
        book.save()

        BookCopy.objects.bulk_create([
            BookCopy(book=book) for _ in range(total_copies)
        ])

        messages.success(self.request, "Pomyślnie dodano książkę")

        return super().form_valid(form)


class EditBookView(LoginRequiredMixin, EmployeeMixin, UpdateView):
    """
    Widok edycji książki.

        Funkcje:
        - Pozwala modyfikować dane książki
        - Obsługuje dodawanie i usuwanie egzemplarzy

        Wymaga logowania i dostępu pracownika.
    """
    model = Book
    form_class = forms.EditBookForm
    template_name = "edit_books.html"
    context_object_name = 'book'
    success_url = reverse_lazy('list_books')

    def form_valid(self, form):
        book = self.get_object()
        old_total_copies = book.total_copies
        new_total_copies = form.cleaned_data["total_copies"]
        
        copies_difference = old_total_copies - new_total_copies

        if copies_difference > 0:
            available_copies_count = BookCopy.objects.filter(
                book=book, 
                is_available=True
            ).count()

            borrowed_copies_count = BookCopy.objects.filter(
                book=book, 
                is_available=False
            ).count()

            if copies_difference > available_copies_count:
                messages.error(
                    self.request, 
                    f"Nie można usunąć {copies_difference} egzemplarzy. "
                    f"Dostępnych jest tylko {available_copies_count} egzemplarzy, "
                    f"a {borrowed_copies_count} jest aktualnie wypożyczonych."
                )
                return self.form_invalid(form)
            
            copies_to_delete_pks = BookCopy.objects.filter(
                book=book, 
                is_available=True
            ).values_list('pk', flat=True)[:copies_difference]
            
            BookCopy.objects.filter(pk__in=copies_to_delete_pks).delete()
        
        elif copies_difference < 0:
            BookCopy.objects.bulk_create([
                BookCopy(book=book, is_available=True) 
                for _ in range(abs(copies_difference))
            ])
        
        Book.objects.filter(pk=book.pk).update(**form.cleaned_data)

        return redirect(self.success_url)


class DeleteBookView(LoginRequiredMixin, EmployeeMixin, View):
    """
    Widok usuwania książki.

        Funkcje:
        - Wyświetla potwierdzenie usunięcia
        - Usuwa książkę z systemu

        Wymaga logowania i dostępu pracownika.
    """
    def get(self, request, pk):
        book = Book.objects.get(pk=pk)
        return render(request, 'delete_books.html', {'book': book})

    def post(self, request, pk):
        book = Book.objects.get(pk=pk)
        book.delete()

        messages.success(request, "Książka usunięta")
        return redirect("dashboard_client", pk=request.user.id)

class ApproveReturnView(LoginRequiredMixin, EmployeeMixin, View):
    def post(self, request, *args, **kwargs):
        rental = get_object_or_404(BookRental, id=self.kwargs['pk'])
        
        rental.status = 'returned'
        rental.return_date = date.today()
        rental.save()
        
        book_copy = rental.book_copy
        book_copy.is_available = True
        book_copy.borrower = None
        book_copy.save()

        book = rental.book_copy.book

        Notification.objects.filter(book=book.id, is_available=False).update(
            is_available=True,
            message=f"Książka {book.title} jest gotowa do wypożyczenia"
        )

        Notification.objects.create(user=rental.user, book=book, is_available=True,
            message=f"Zwrot książki {book.title} został zatwierdzony"
        )

        messages.success(request, "Zwrot przetworzony")
        return redirect("dashboard_employee", pk=request.user.id)


class ListBorrowsView(LoginRequiredMixin, EmployeeMixin, ListView):
    """
    Widok listy wypożyczeń.

        Funkcje:
        - Wyświetla wszystkie wypożyczenia
        - Sortuje wypożyczenia według statusu

        Wymaga logowania i dostępu pracownika.
    """
    model = BookRental
    template_name = "list_borrows.html"
    paginate_by = 4
    
    def get_queryset(self):
        status_order = Case(
            When(status='rented', then=Value(1)),
            When(status='overdue', then=Value(2)),
            When(status='returned', then=Value(3)),
            default=Value(4),
            output_field=IntegerField()
        )
        
        return BookRental.objects.annotate(
            status_priority=status_order
        ).order_by('status_priority', '-rental_date')


class ListUsersView(LoginRequiredMixin, EmployeeMixin, ListView):
    """
    Widok listy użytkowników.
        
        Funkcje:
        - Wyświetla wszystkich użytkowników systemu
        
        Wymaga logowania i dostępu pracownika.
    """
    model = CustomUser
    template_name = "list_users.html"


class DetailUserView(LoginRequiredMixin, EmployeeMixin, DetailView):
    """
    Widok szczegółów użytkownika.

        Funkcje:
        - Wyświetla szczegółowe informacje o użytkowniku

        Wymaga logowania i dostępu pracownika.
    """
    model = CustomUser
    template_name = "detail_user.html"
    context_object_name = 'user'


class EditUserView(LoginRequiredMixin, UpdateView):
    """
    Widok edycji użytkownika.

        Funkcje:
        - Umożliwia modyfikację danych użytkownika
        - Przekierowuje do odpowiedniego pulpitu po zapisie

        Wymaga logowania.
    """
    model = CustomUser
    form_class = forms.EditUserForm
    template_name = "edit_user.html"

    def get_success_url(self):
        user = self.object
        return reverse(
            "dashboard_employee" if user.is_employee else "dashboard_client", 
            kwargs={'pk': user.id}
        )
    
    def form_valid(self, form):
        messages.success(self.request, "Dane zmienione poprawnie.")
        return super().form_valid(form)


class ActiveUserView(LoginRequiredMixin, AdminMixin, View):
    """
    Widok zmiany statusu aktywności użytkownika.

        Funkcje:
        - Włącza/wyłącza konto użytkownika

        Wymaga logowania i dostępu administratora.
    """
    def post(self, request, pk):
        user = CustomUser.objects.get(pk=pk)
        user.is_active = not user.is_active
        user.save()
        return redirect('detail_user', pk=pk)


class DeleteUserView(LoginRequiredMixin, AdminMixin, View):
    """
    Widok usuwania użytkownika.

        Funkcje:
        - Wyświetla potwierdzenie usunięcia
        - Usuwa użytkownika z systemu

        Wymaga logowania i dostępu administratora.
    """
    def get(self, request, pk):
        user = CustomUser.objects.get(pk=pk)
        return render(request, 'delete_user.html', {'user': user})

    def post(self, request, pk):
        user = CustomUser.objects.get(pk=pk)
        user.delete()

        messages.success(request, "Użytkownik usunięty")
        return redirect("list_users")


class AddUserView(LoginRequiredMixin, AdminMixin, CreateView):
    """
    Widok dodawania nowego użytkownika.

        Funkcje:
        - Umożliwia utworzenie nowego konta użytkownika

        Wymaga logowania i dostępu administratora.
    """
    template_name = "add_user.html"
    form_class = forms.AdminUserForm
    success_url = reverse_lazy('list_users')


class CustomPasswordResetView(PasswordResetView):
    """
    Widok resetowania hasła.

        Funkcje:
        - Inicjuje proces resetowania hasła
        - Wysyła email z instrukcjami
    """
    template_name = 'password_reset.html' 
    email_template_name = 'password_reset_email.html' 
    success_url = reverse_lazy('password_reset_done')
    form_class = PasswordResetForm


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'password_reset_complete.html'

class UserRegistrationView(SuccessMessageMixin, CreateView):
    """
    Widok rejestracji użytkownika.

        Funkcje:
        - Wyświetla formularz rejestracji
        - Przekierowuje zalogowanych użytkowników
    """
    form_class = forms.UserRegistrationForm
    template_name = 'register.html'
    success_message = "Konto zostało utworzone pomyślnie! Możesz się teraz zalogować."
   
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['username'].label = 'Nazwa użytkownika'
        form.fields['password1'].label = 'Hasło'
        form.fields['password2'].label = 'Powtórz hasło'
        
        return form

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_employee:
            return redirect('dashboard_employee', pk=request.user.id)
        elif request.user.is_authenticated and not request.user.is_employee:
            return redirect('dashboard_client', pk=request.user.id)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy('login')

class UserLoginView(SuccessMessageMixin, LoginView):
    """
    Widok logowania użytkownika.

        Funkcje:
        - Umożliwia zalogowanie się do systemu
        - Przekierowuje do odpowiedniego pulpitu
        - Obsługuje błędy logowania
    """
    form_class = forms.UserLoginForm
    template_name = 'login.html'
    success_message = "Zostałeś pomyślnie zalogowany!"
   
    def get_success_url(self):
           return reverse('dashboard_client', kwargs={'pk': self.request.user.id})
   
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['username'].label = 'Nazwa użytkownika'
        form.fields['password'].label = 'Hasło'
        
        return form
    
    def form_invalid(self, form):
        messages.error(self.request,'Dane są nieprawidłowe lub twoje konto jest zablokowane.')
        return redirect('login')
        
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_employee and request.user.is_active:
            return redirect('dashboard_employee', pk=request.user.id)
        elif request.user.is_authenticated and not request.user.is_employee and request.user.is_active:
            return redirect('dashboard_client', pk=request.user.id)
        return super().dispatch(request, *args, **kwargs)

class UserLogoutView(View):
    """
    Widok wylogowania użytkownika.

        Funkcje:
        - Kończy sesję użytkownika
        - Przekierowuje do strony logowania
    """
    def get(self, request):
        logout(request)
        return redirect('login')
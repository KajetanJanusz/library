from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any
from django.contrib import messages
from django.db.models.query import QuerySet
from django.shortcuts import redirect, render
from django.http import HttpRequest, HttpResponse
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import DetailView, ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count, Case, When, Value, IntegerField, Sum

from books.models import Book, BookRental, BookCopy, Category, Notification, Opinion
from books import forms
from books.mixins import AdminMixin, CustomerMixin, EmployeeMixin
from users.models import CustomUser
from books.helpers import recommend_books_for_user

class DashboardClient(LoginRequiredMixin, CustomerMixin, DetailView):
    model = CustomUser
    template_name = "dashboard_client.html"
    context_object_name = "user"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        response = super().get(request, *args, **kwargs)
        if self.request.user.is_admin:
            return redirect('dashboard_employee', pk=self.request.user.id)
        return response

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.get_object()
        rented_books = BookRental.objects.filter(user=user, status='rented')
        rented_books_old = BookRental.objects.filter(user=user, status='returned')
        notifications = Notification.objects.filter(user=user, is_read=False, is_available=True)
        opinions = Opinion.objects.filter(user=user)
        recommended_books = recommend_books_for_user(user)
        context['rented_books'] = rented_books
        context['rented_books_old'] = rented_books_old
        context['notifications'] = notifications
        context['opinions'] = opinions
        context['recommended_books'] = recommended_books
        return context

class BorrowBook(LoginRequiredMixin, CustomerMixin, View):
    def post(self, request, *args, **kwargs):
        book_id = self.kwargs.get('pk')
        user = request.user

        book = Book.objects.get(id=book_id)
        available_copy = BookCopy.objects.filter(book=book, is_available=True).first()
        user_rentals = BookRental.objects.filter(user=user.id, status='rented').count()

        if not available_copy:
            messages.warning(request, "Nie ma wolnych egzemplarzy")
            return redirect('dashboard_client', pk=request.user.id)
        
        if user_rentals >= 3:
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

        messages.success(request, "Książka wypożyczona")
        return redirect('dashboard_client', pk=request.user.id)

class ReturnBook(LoginRequiredMixin, CustomerMixin, View):

    def get(self, request, *args, **kwargs):
        rental = BookRental.objects.get(id=self.kwargs['pk'])
        return render(request, 'confirm_return.html', {'rental': rental})

    def post(self, request, *args, **kwargs):
        rental = BookRental.objects.get(id=self.kwargs['pk'])
        
        rental.status = 'returned'
        rental.return_date = date.today()
        rental.save()
        
        book_copy = rental.book_copy
        book_copy.is_available = True
        book_copy.borrower = None
        book_copy.save()

        book = rental.book_copy.book

        notifications = Notification.objects.filter(book=book.id, is_available=False)

        if notifications.exists():
            for notification in notifications:
                notification.is_available = True
                notification.message = f"Książka {book.title} jest gotowa do wypożyczenia"
                notification.save()

        messages.success(request, "Książka zwrócona")
        return redirect("dashboard_client", pk=request.user.id)
    
class ExtendRentalPeriodView(LoginRequiredMixin, CustomerMixin, View):
    model = BookRental
    template_name = 'extend_rental.html'
    context_object_name = 'book'

    def get(self, request, *args, **kwargs):
        rental = BookRental.objects.get(id=self.kwargs['pk'])
        return render(request, 'extend_rental.html', {'rental': rental})

    def post(self, request, *args, **kwargs):
        rental = BookRental.objects.get(id=self.kwargs['pk'])
        
        if not rental.is_extended:
            rental.due_date += timedelta(days=7)
            rental.is_extended = True
            rental.save()

        messages.success(request, "Wypożyczenie przedłużone")
        return redirect("dashboard_client", pk=request.user.id)
    

class ListBooksView(LoginRequiredMixin, ListView):
    model = Book
    template_name = "list_books.html"
    context_object_name = "books"

    def get_queryset(self) -> QuerySet[Any]:
        queryset = super().get_queryset()
        query = self.request.GET.get('q')

        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | Q(author__icontains=query) | Q(category__name__icontains=query)
            )

        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['categories'] = [category for category in Category.objects.all()]
        for book in context['books']:
            available_copies = book.copies.filter(is_available=True).count()
            book.available_copies = available_copies
        
        return context
    
class DetailBookView(LoginRequiredMixin, DetailView):
    model = Book
    template_name = 'detail_book.html'
    context_object_name = 'book'

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        response = super().get(request, *args, **kwargs)
        if Notification.objects.filter(user=self.request.user, book=self.get_object(), is_read=False, is_available=True).exists():
            notification = Notification.objects.get(user=self.request.user, book=self.get_object(), is_read=False)
            notification.is_read = True
            notification.save()

        return response

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        book = self.get_object()
        if BookRental.objects.filter(book_copy__book=book, user=self.request.user).exists() and not Opinion.objects.filter(book=book, user=self.request.user).exists():
            context['comment_form'] = forms.OpinionForm()
        context['opinions'] = Opinion.objects.filter(book=book)
        context['copies'] = BookCopy.objects.filter(book=book)
        context['copies_available'] = BookCopy.objects.filter(book=book, is_available=True).exists()
        context['available_copies'] = BookCopy.objects.filter(book=book, is_available=True).count()
        return context
    
    def post(self, request, *args, **kwargs):
        book = self.get_object()
        form = forms.OpinionForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.book = book
            comment.user = self.request.user
            comment.save()
            return redirect('detail_book', pk=book.id)
        messages.error(self.request, "Nie udało się dodać komentarza")
        return redirect('detail_book', pk=book.id)
    
class SubscribeBookView(LoginRequiredMixin, CustomerMixin, View):
    def post(self, request, *args, **kwargs):
        user = self.request.user
        book = Book.objects.get(id=self.kwargs['pk'])

        _, created = Notification.objects.get_or_create(user=user, book=book, is_available=False)

        if not created:
            messages.info(request, "Już masz włączone powiadomienia odnośnie tej książki")
        else:
            messages.success(request, "Powiadomienia włączone pomyślnie")
        return redirect('dashboard_client', pk=user.id)

class DashboardEmployeeView(LoginRequiredMixin, EmployeeMixin, DetailView):
    model = CustomUser
    template_name = "dashboard_employee.html"
    context_object_name = "user"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        all_users = CustomUser.objects.all()
        customers = CustomUser.objects.filter(is_employee=False)
        overdue_rentals = BookRental.objects.filter(status='overdue')
        user = self.get_object()
        rented_books = BookRental.objects.filter(status='rented')[:3]
        users_rented_books = BookRental.objects.filter(user=user, status='rented')
        rented_books_old = BookRental.objects.filter(user=user, status='returned')
        notifications = Notification.objects.filter(user=user, is_read=False, is_available=True)
        most_rented_books = (
            BookRental.objects.values('book_copy__book__title')
            .annotate(rental_count=Count('id'))
            .order_by('-rental_count')
        )[:3]
        total_rentals = most_rented_books.aggregate(total=Sum('rental_count'))['total'] or 0
        context['users_rented_books'] = users_rented_books
        context['rented_books'] = rented_books
        context['rented_books_old'] = rented_books_old
        context['notifications'] = notifications
        context['customers'] = customers
        context['all_users'] = all_users
        context['overdue_rentals'] = overdue_rentals
        context['most_rented_books'] = most_rented_books
        context['total_rentals'] = total_rentals
        return context

class AddBookView(LoginRequiredMixin, EmployeeMixin, CreateView):
    template_name = "add_books.html"
    form_class = forms.BookForm
    success_url = reverse_lazy('list_books')

    def form_valid(self, form):
        book = form.save()

        total_copies = form.cleaned_data['total_copies']

        book_copies = [BookCopy(book=book) for _ in range(total_copies)]
        BookCopy.objects.bulk_create(book_copies)

        return super().form_valid(form)



class EditBookView(LoginRequiredMixin, EmployeeMixin, UpdateView):
    model = Book
    form_class = forms.BookForm
    template_name = "edit_books.html"
    context_object_name = 'book'
    success_url = reverse_lazy('list_books')

    def form_valid(self, form):
        book = Book.objects.get(id=self.kwargs['pk'])
        old_total_copies = book.total_copies
        new_total_copies = form.cleaned_data["total_copies"]
        
        copies_difference = old_total_copies - new_total_copies

        if copies_difference > 0:
            available_copies = BookCopy.objects.filter(
                book=book, 
                is_available=True
            )
            
            removable_copies_count = min(
                copies_difference,
                available_copies.count()
            )

            for copy in available_copies[:removable_copies_count]:
                copy.delete()
        
        elif copies_difference < 0:
            new_copies_to_add = abs(copies_difference)
            
            for _ in range(new_copies_to_add):
                BookCopy.objects.create(
                    book=book, 
                    is_available=True
                )
        
        book.total_copies = new_total_copies
        book.save()

        Book.objects.filter(id=self.kwargs['pk']).update(**form.cleaned_data)

        return redirect(self.success_url)

class DeleteBookView(LoginRequiredMixin, EmployeeMixin, View):
    model = Book
    template_name = "delete_books.html"
    success_url = reverse_lazy('list_books')

    def get(self, request, *args, **kwargs):
        book = Book.objects.get(id=self.kwargs['pk'])
        return render(request, 'delete_books.html', {'book': book})

    def post(self, request, *args, **kwargs):
        book = Book.objects.get(id=self.kwargs['pk'])
        
        book.delete()

        messages.success(request, "Książka usunięta")
        return redirect("dashboard_client", pk=request.user.id)
    

class ListBorrowsView(LoginRequiredMixin, EmployeeMixin, ListView):
    model = BookRental
    template_name = "list_borrows.html"
    
    def get_queryset(self):
        status_order = Case(
            When(status='rented', then=Value(1)),
            When(status='overdue', then=Value(2)),
            When(status='returned', then=Value(3)),
            default=Value(4),
            output_field=IntegerField()
        )
        
        # Order the rentals by the custom status priority and then by most recent rental date
        return BookRental.objects.annotate(
            status_priority=status_order
        ).order_by('status_priority', '-rental_date')

class ListUsersView(LoginRequiredMixin, EmployeeMixin, ListView):
    model = CustomUser
    template_name = "list_users.html"

class DetailUserView(LoginRequiredMixin, EmployeeMixin, DetailView):
    model = CustomUser
    template_name = "detail_user.html"
    context_object_name = 'user'


class EditUserView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    form_class = forms.UserForm
    template_name = "edit_user.html"

    def get_success_url(self) -> str:
        user = self.object  # Zaktualizowany użytkownik dostępny przez self.object
        if user.is_employee:
            return reverse("dashboard_employee", kwargs={'pk': user.id})
        else:
            return reverse("dashboard_client", kwargs={'pk': user.id})

class ActiveUserView(LoginRequiredMixin, AdminMixin, View):
    model = CustomUser
    success_url = reverse_lazy('list_users')

    def post(self, request, *args, **kwargs):
        user = CustomUser.objects.get(id=self.kwargs['pk'])
        if user.is_active:
            user.is_active = False
        else:
            user.is_active = True
        user.save()
        return redirect('detail_user', pk=user.id)

class DeleteUserView(LoginRequiredMixin, AdminMixin, View):
    model = CustomUser
    success_url = reverse_lazy('list_users')

    def get(self, request, *args, **kwargs):
        user = CustomUser.objects.get(id=self.kwargs['pk'])
        return render(request, 'delete_user.html', {'user': user})

    def post(self, request, *args, **kwargs):
        user = CustomUser.objects.get(id=self.kwargs['pk'])
        
        user.delete()

        messages.success(request, "Książka usunięta")
        return redirect("list_books")
    
class AddUserView(LoginRequiredMixin, AdminMixin, CreateView):
    template_name = "add_user.html"
    form_class = forms.CustomUserForm
    success_url = reverse_lazy('list_users')


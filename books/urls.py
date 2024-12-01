from django.contrib import admin
from django.urls import path

from books import views


urlpatterns = [
    path('dashboard/client/<int:pk>', views.DashboardClient.as_view(), name='dashboard_client'),
    path('<int:pk>/borrow/', views.BorrowBook.as_view(), name='borrow_book'),
    path('<int:pk>/return/', views.ReturnBook.as_view(), name='return_book'),
    path('<int:pk>/extend/', views.ExtendRentalPeriodView.as_view(), name='extend_book'),

    path('', views.ListBooksView.as_view(), name='list_books'),
    path('<int:pk>', views.DetailBookView.as_view(), name='detail_book'),
    path('<int:pk>/notification', views.SubscribeBookView.as_view(), name='subscribe_book'),

    path('dashboard/employee/<int:pk>', views.DashboardEmployeeView.as_view(), name='dashboard_employee'),
    path('add/', views.AddBookView.as_view(), name='add_book'),
    path('<int:pk>/edit/', views.EditBookView.as_view(), name='edit_book'),
    path('<int:pk>/delete/', views.DeleteBookView.as_view(), name='delete_book'),
    path('borrows/', views.ListBorrowsView.as_view(), name='list_borrows'),
    path('users/', views.ListUsersView.as_view(), name='list_users'),
    path('users/<int:pk>', views.DetailUserView.as_view(), name='detail_user'),
    path('users/add', views.AddUserView.as_view(), name='add_user'),
    path('users/<int:pk>/edit', views.EditUserView.as_view(), name='edit_user'),
    path('users/<int:pk>/delete', views.DeleteUserView.as_view(), name='delete_user'),
    path('users/<int:pk>/active', views.ActiveUserView.as_view(), name='active_user'),
]

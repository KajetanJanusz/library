from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from books import views


urlpatterns = [
     path('qr_code/', include('qr_code.urls', namespace='qr_code')),
     
     path('', views.UserLoginView.as_view(), name='login'),
     path('register/', views.UserRegistrationView.as_view(), name='register'),
     path('logout/', views.UserLogoutView.as_view(), name='logout'),
     path('dashboard/client/<int:pk>', views.DashboardClient.as_view(), name='dashboard_client'),
     path('articles/', views.ArticlesView.as_view(), name='articles'),
     path('<int:pk>/borrow/', views.BorrowBook.as_view(), name='borrow_book'),
     path('<int:pk>/return/', views.ReturnBook.as_view(), name='return_book'),
     path('<int:pk>/extend/', views.ExtendRentalPeriodView.as_view(), name='extend_book'),
     path('<int:pk>/approve_return/', views.ApproveReturnView.as_view(), name='approve_return'),
     path('<int:pk>/mark_as_read/', views.MarkNotificationAsReadView.as_view(), name='mark_as_read'),

     path('books/', views.ListBooksView.as_view(), name='list_books'),
     path('<int:pk>', views.DetailBookView.as_view(), name='detail_book'),
     path('<int:pk>/notification', views.SubscribeBookView.as_view(), name='subscribe_book'),

     path('dashboard/employee/<int:pk>', views.DashboardEmployeeView.as_view(), name='dashboard_employee'),
     path('book/add/', views.AddBookFormView.as_view(), name='add_book_form'),
     path('book/confirm-description/', views.ConfirmBookDescriptionView.as_view(), name='confirm_book_description'),
     path('<int:pk>/edit/', views.EditBookView.as_view(), name='edit_book'),
     path('<int:pk>/delete/', views.DeleteBookView.as_view(), name='delete_book'),
     path('borrows/', views.ListBorrowsView.as_view(), name='list_borrows'),
     path('users/', views.ListUsersView.as_view(), name='list_users'),
     path('users/<int:pk>', views.DetailUserView.as_view(), name='detail_user'),
     path('users/add', views.AddUserView.as_view(), name='add_user'),
     path('users/<int:pk>/edit', views.EditUserView.as_view(), name='edit_user'),
     path('users/<int:pk>/delete', views.DeleteUserView.as_view(), name='delete_user'),
     path('users/<int:pk>/active', views.ActiveUserView.as_view(), name='active_user'),

     path('reset-password/', 
          views.CustomPasswordResetView.as_view(), 
          name='password_reset'),
     
     path('reset-password/done/', 
          views.CustomPasswordResetDoneView.as_view(), 
          name='password_reset_done'),
     
     path('reset-password/confirm/<uidb64>/<token>/', 
          views.CustomPasswordResetConfirmView.as_view(), 
          name='password_reset_confirm'),
     
     path('reset-password/complete/', 
          views.CustomPasswordResetCompleteView.as_view(), 
          name='password_reset_complete'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

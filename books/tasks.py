from library.celery import app
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
from decimal import Decimal

from .models import BookRental

@app.task
def check_overdue_books():
    '''
    Sprawdza raz dziennie czy są jakieś przeterminowane książki
    oraz czy są książki ze zbiliżającym się terminem zwrotu i wysyła maile informacyjne.
    '''
    today = timezone.now().date()
    week_from_now = today + timedelta(days=7)
    
    overdue_rentals = BookRental.objects.filter(
        status='rented',
        due_date__lt=today,
        return_date__isnull=True
    )
    
    for rental in overdue_rentals:
        rental.status = 'overdue'
        days_overdue = (today - rental.due_date).days
        rental.fine = Decimal(days_overdue * 0.50)
        rental.save()
        
        send_overdue_notification(rental)

    upcoming_due_rentals = BookRental.objects.filter(
        status='rented',
        due_date=week_from_now,
        return_date__isnull=True
    )
    
    for rental in upcoming_due_rentals:
        send_upcoming_due_notification(rental)

def send_overdue_notification(rental):
    subject = 'Przekroczono termin zwrotu książki'
    message = f"""
    Szanowny/a {rental.user.get_full_name()},
    
    Informujemy, że przekroczono termin zwrotu książki:
    "{rental.book_copy.book.title}"
    
    Termin zwrotu: {rental.due_date}
    Naliczona kara: {rental.fine} PLN
    
    Prosimy o niezwłoczny zwrot książki do biblioteki.
    
    Z poważaniem,
    Zespół Biblioteki
    """
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [rental.user.email],
        fail_silently=False,
    )

def send_upcoming_due_notification(rental):

    subject = 'Przypomnienie o terminie zwrotu książki'
    message = f"""
    Szanowny/a {rental.user.get_full_name()},
    
    Przypominamy, że za tydzień ({rental.due_date}) upływa termin zwrotu książki:
    "{rental.book_copy.book.title}"
    
    Jeśli potrzebujesz więcej czasu, możesz przedłużyć wypożyczenie w systemie bibliotecznym.
    
    Z poważaniem,
    Zespół Biblioteki
    """
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [rental.user.email],
        fail_silently=False,
    )
    
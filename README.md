# Dokumentacja Projektu Biblioteki
## Opis modułów
### Aplikacja Books
`views.py`
Zawiera widoki aplikacji, które przekazują dane do frontend-u w celu wyświetlenia ich na odpowiednich ekranach, np. ekranie Dashboardu. Obsługuje również dostęp do poszczególnych linków w aplikacji.

`tasks.py`
Zawiera funkcje asynchroniczne, które realizują zadania takie jak:

- Przypominanie o zbliżającym się terminie zwrotu książki.
- Powiadomienie o przekroczeniu terminu zwrotu książki.

`models.py`
Definiuje modele bazy danych używane w aplikacji.

`urls.py`
Określa linki i ścieżki do zasobów aplikacji Books.

`mixins.py`
Zawiera klasy pomocnicze do sprawdzania, czy użytkownik jest:

- Klientem,
- Adminem,
- Pracownikiem.

`helpers.py`
Zawiera funkcje pomocnicze, w tym funkcję tworzącą rekomendacje książek dla użytkownika.

`forms.py`
Formularze służące do tworzenia obiektów, takich jak książki czy użytkownicy.

### Aplikacja Library
`urls.py`
Główne linki aplikacji, w których są zintegrowane ścieżki (URL-e) z aplikacji Books.

`celery.py`
Konfiguracja narzędzia Celery (kolejki zadań), umożliwiającego wykonywanie zadań asynchronicznych, takich jak wysyłanie maili z powiadomieniami.

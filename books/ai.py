import requests
import google.generativeai as genai_text
import requests
from django.core.files.base import ContentFile
import re

genai_text.configure(api_key="AIzaSyDbJ3KSu9oQo8KrkwP0wyNJSZv2iMiKxXg")
model = genai_text.GenerativeModel("gemini-1.5-flash")


def get_ai_book_recommendations(rentals, available_books):
    if len(rentals) < 3:
        return ["Musisz przeczytać więcej niż 3 książki, aby otrzymać rekomendacje AI."]
    
    prompt = (
        "Mam bibliotekę z następującymi książkami: \n"
        + "\n".join(f"- {rental.book_copy.book.title}" for rental in rentals)
        + "\nNa podstawie tych książek zaproponuj mi 3 inne tytuły, które mogłyby mnie zainteresować.\n"
        + "Odpowiedz daj w takiej formie 1. *Tytuł* - *powód* itd., pisz do mnie w pierwszej osobie po imieniu."
        + "Wybierz z tej listy " + "\n".join(f"- {book.title}" for book in available_books)
    )

    try:
        response = model.generate_content(prompt)
        pattern = pattern = r"^(.*?)\s1\.\s\*(.*?)\*\s-\s(.*?)\s2\.\s\*(.*?)\*\s-\s(.*?)\s3\.\s\*(.*?)\*\s-\s(.*)$"
        match = re.match(pattern, response.text, re.DOTALL)

        if match:
            propozycja_1 = f"{match.group(2).strip("*")} - {match.group(3).strip().replace("*", "")}"
            propozycja_2 = f"{match.group(4).strip("*")} - {match.group(5).strip().replace("*", "")}"
            propozycja_3 = f"{match.group(6).strip("*")} - {match.group(7).strip().replace("*", "")}"

        return [propozycja_1, propozycja_2, propozycja_3]
    except Exception as e:
        return ["Rekomendacje AI są w tym momencie niedostępne, z powodów połączenia z serwerem", "Spróbuj ponownie później.", "Przepraszamy!"]


def get_ai_generated_fun_fact():
    prompt = f"Wygeneruj krótką ciekawostkę po polsku ze świata książek, musi być ona sprawdzona i prawdziwa."

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Wystąpił błąd podczas komunikacji z Gemini: {e}"


def get_ai_generated_description(title, author):
    prompt = f"Wygeneruj po polsku krótki 3 zdaniowy opis książki {title} autora {author}"

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Wystąpił błąd podczas komunikacji z Gemini: {e}"

import google.generativeai as genai
import re

genai.configure(api_key="AIzaSyDbJ3KSu9oQo8KrkwP0wyNJSZv2iMiKxXg")
model = genai.GenerativeModel("gemini-1.5-flash")


def get_ai_book_recommendations(book_list):
    prompt = (
        "Mam bibliotekę z następującymi książkami: \n"
        + "\n".join(f"- {book}" for book in book_list)
        + "\nNa podstawie tych książek zaproponuj mi 3 inne tytuły, które mogłyby mnie zainteresować.\n"
        + "Odpowiedz daj w takiej formie 1. *Tytuł* - *powód* itd., pisz do mnie w pierwszej osobie po imieniu"
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
        return f"Wystąpił błąd podczas komunikacji z Gemini: {e}"

def get_ai_generated_description(title, author):
    prompt = f"Wygeneruj krótki 3 zdaniowy opis książki {title} autora {author}"

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Wystąpił błąd podczas komunikacji z Gemini: {e}"

    

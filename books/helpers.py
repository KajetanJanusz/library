import requests
from bs4 import BeautifulSoup

def get_five_book_articles():
    urls = [
        "https://zacofany-w-lekturze.pl",
        "https://lubimyczytac.pl/aktualnosci"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    
    results = []
    
    try:
        for url in urls:

            try:
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                if "lubimyczytac" in url:

                    articles = soup.find_all('a', class_='authorAllBooks__singleTextTitle')
                    for article in articles[:3]:
                        try:
                            title = article.get_text(strip=True)
                            link = article['href']
                            description = article.find_next('p', class_='around-book__text')
                            description_text = description.get_text(strip=True) if description else ""
                            description_text = description_text.split("Czytaj więcej")[0].strip()
                            
                            if not link.startswith('http'):
                                link = f"https://lubimyczytac.pl{link}"
                            
                            results.append({
                                'source': 'lubimyczytac.pl',
                                'title': title,
                                'description': description_text,
                                'link': link
                            })
                        except Exception as e:
                            print(f"Błąd przy przetwarzaniu artykułu z lubimyczytac.pl: {e}")
                
                elif "zacofany-w-lekturze" in url:

                    articles = soup.find_all('h2', class_='entry-title')
                    for article in articles[:2]:
                        try:
                            link_element = article.find('a')
                            title = link_element.get_text(strip=True)
                            link = link_element['href']
                            
                            content_div = article.find_next('div', class_='entry-content')
                            if content_div:
                                paragraphs = content_div.find_all('p')
                                description_text = paragraphs[1].get_text(strip=True) if paragraphs else ""
                                description_text = paragraphs[2].get_text(strip=True) if description_text == "" else description_text
                            else:
                                description_text = ""
                            
                            results.append({
                                'source': 'zacofany-w-lekturze.pl',
                                'title': title,
                                'description': description_text,
                                'link': link
                            })
                        except Exception as e:
                            print(f"Błąd przy przetwarzaniu artykułu z zacofany-w-lekturze.pl: {e}")
            
            except requests.RequestException as e:
                print(f"Błąd podczas pobierania strony {url}: {e}")
                if 'response' in locals():
                    print("Kod statusu:", response.status_code)
                continue
    
    except Exception as e:
        print(f"Wystąpił błąd podczas pobierania danych: {e}")
    return results

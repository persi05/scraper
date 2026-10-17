# Laboratorium 1 — katalog produktów i scraper

Projekt zawiera serwis z katalogiem produktów oraz scraper napisany w Pythonie. Scraper korzysta z Selenium: odwiedza kolejne strony katalogu, doładowuje oferty i otwiera szczegóły produktów. Zebrane dane czyści i sprawdza, a wyniki zapisuje w formatach CSV i JSON.

## Wymagania

- Python 3.10 lub nowszy.
- Zainstalowany Google Chrome lub Microsoft Edge.
- Biblioteki z `requirements.txt`: Selenium, Requests i BeautifulSoup.

Selenium automatycznie dobiera sterownik przeglądarki. Przy pierwszym uruchomieniu może potrzebować dostępu do internetu, aby go pobrać. Można też wskazać własny plik sterownika parametrem `--driver`.

## Przygotowanie środowiska

W folderze projektu wykonaj następujące polecenia w PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Jeśli środowisko `.venv` już istnieje, wystarczy drugie polecenie. Podane polecenia wskazują interpreter tego środowiska bezpośrednio, więc nie trzeba go aktywować.

## Uruchomienie serwisu

W pierwszym terminalu uruchom serwis:

```powershell
python app.py
```

Katalog jest dostępny pod adresem `http://127.0.0.1:8000/page/1` i korzysta z danych zapisanych w `public/catalog.json`. Ma pięć stron, a oferty przedstawia w tabelach i na kartach. Każdy produkt ma też własny adres strony szczegółów. JavaScript dodaje oferty do dokumentu porcjami po 20.

## Uruchomienie scrapera

Pozostaw serwis uruchomiony i w drugim terminalu uruchom scraper:

```powershell
.\.venv\Scripts\python.exe scraper.py
```

Domyślnie scraper uruchamia Chrome bez widocznego okna i zapisuje wyniki w `output/`. Odwiedza wszystkie strony katalogu oraz szczegóły każdego unikalnego produktu. Doładowywanie ofert i przerwy między operacjami sprawiają, że pełny przebieg może potrwać kilka minut.

Aby wykonać krótką próbę z widocznym oknem przeglądarki, użyj:

```powershell
.\.venv\Scripts\python.exe scraper.py --headed --pages 1 --limit 5 --output output/proba
```

Program doładuje wszystkie oferty z pierwszej strony katalogu i pobierze szczegóły maksymalnie pięciu produktów. W podsumowaniu oznaczy taki przebieg jako częściowy.

Przykład uruchomienia w Edge z podanymi parametrami:

```powershell
.\.venv\Scripts\python.exe scraper.py --browser edge --base-url http://127.0.0.1:8000 --output output/edge --delay 0.5 --timeout 20 --attempts 3
```

Pełną listę opcji wyświetla polecenie:

```powershell
.\.venv\Scripts\python.exe scraper.py --help
```

## Parametry

| Parametr | Domyślnie | Znaczenie |
| --- | --- | --- |
| `--base-url` | `http://127.0.0.1:8000` | Adres serwisu. |
| `--output` | `output` | Folder wyników. |
| `--pages` | Bez limitu | Maksymalna liczba odwiedzanych stron katalogu. |
| `--limit` | Bez limitu | Maksymalna liczba produktów, których szczegóły zostaną pobrane. |
| `--browser` | `chrome` | Przeglądarka: `chrome` lub `edge`. |
| `--driver` | Dobór automatyczny | Ścieżka do pliku `chromedriver.exe` lub `msedgedriver.exe`. |
| `--headed` | Wyłączone | Pokazuje okno przeglądarki. |
| `--delay` | `0.5` | Minimalny odstęp w sekundach między operacjami, których tempo ogranicza scraper. Musi wynosić co najmniej 0,5 s. |
| `--timeout` | `20` | Maksymalny czas w sekundach na żądanie HTTP, załadowanie strony lub pojedyncze oczekiwanie na warunek. |
| `--attempts` | `3` | Maksymalna liczba prób operacji łącznie z pierwszą; dopuszczalny zakres 1–8. |

Po nieudanej operacji scraper czeka przed kolejną próbą. Przerwy rosną wykładniczo: 1, 2, 4… s. Domyślne trzy próby obejmują pierwszą próbę i maksymalnie dwa ponowienia po 1 i 2 s.

Na gotowość elementów strony scraper czeka za pomocą `WebDriverWait`. Osobny mechanizm, limiter, pilnuje odstępów przed otwieraniem stron, pomocniczymi żądaniami HTTP i kliknięciami przycisku doładowania. Zasoby strony przeglądarka pobiera samodzielnie.

## Pliki scrapera

| Plik | Rola |
| --- | --- |
| `scraper.py` | Sterowanie przeglądarką, odczyt DOM, paginacja, szczegóły, deduplikacja, ponawianie operacji, kontrola kompletności i eksport. |
| `cleaning.py` | Wspólny schemat pól, normalizacja tekstów, cen, liczb i dat oraz walidacja wartości. |
| `requirements.txt` | Zależności Pythona potrzebne do uruchomienia scrapera. |

Scraper sprowadza dane z tabel i kart do wspólnego formatu. Usuwa duplikaty według ID, zanim przejdzie do szczegółów produktów. Na stronie szczegółów rozwija sekcję z ukrytym atrybutem, odczytuje dodatkowe pola i łączy je z ofertą z katalogu. Sprawdza przy tym, czy wartości pól obecnych w obu miejscach są zgodne.

Ceny zapisuje jako liczby, a walutę w osobnym polu. Braki danych oznacza przez `null` w JSON i puste komórki w CSV. Plik CSV ma kodowanie UTF-8 z BOM.

Do kontroli odczytanych danych scraper wykorzystuje źródłowy JSON, którego adres wykrywa w logu sieciowym przeglądarki. Dane produktów zbiera z DOM przez Selenium. Requests pobiera surowy HTML, który następnie odczytuje BeautifulSoup. Requests służy też do pobrania wykrytego JSON-a.

## Wyniki

Scraper zapisuje wyniki w folderze wskazanym przez `--output`:

| Plik | Zawartość |
| --- | --- |
| `products.csv` | Gotowe produkty: jeden wiersz na produkt, jedna kolumna na pole. |
| `products.json` | Te same produkty z typami liczbowymi i `null` dla braków. |
| `raw_listings.json` | Oferty odczytane z katalogu przed deduplikacją, z oznaczeniem tabeli lub karty. |
| `products.partial.json` | Dotychczas zebrane produkty ze szczegółami, zapisywane na bieżąco. |
| `run_summary.json` | Ustawienia, status, liczniki stron i rekordów, duplikaty, odrzucone wartości, porównanie HTML/DOM, czasy i kompletność przebiegu. |
| `source_comparison.json` | Wykryty adres JSON, różnice względem źródła oraz kontrola ID i liczby ofert. |
| `scraper.log` | Przebieg pracy, błędy i końcowe podsumowanie. |
| `diagnostics/` | Opisy błędów oraz dostępne zrzuty ekranu, HTML i logi przeglądarki. |

Dla dołączonego katalogu pełny przebieg powinien objąć 5 stron, 408 wystąpień ofert i 400 unikalnych produktów. Eksport ma 29 kolumn: 28 pól produktu i URL. Surowy HTML katalogu zawiera 0 rekordów. Po doładowaniu wszystkich ofert DOM zawiera 408 wystąpień: 200 w tabelach i 208 na kartach. W polach sprzedawcy i gwarancji brakuje po 80 wartości.

Po zakończeniu sprawdź `run_summary.json`. Pełny, poprawny przebieg ma oznaczenia `status: "success"`, `integrity_ok: true` i `complete_lab_run: true`. Użycie `--pages` lub `--limit` oznacza przebieg częściowy. Pliki z danymi mogą powstać także wtedy, gdy końcowa kontrola wykaże błąd, dlatego o powodzeniu świadczy status zapisany w podsumowaniu.

Zapis częściowy pozwala zachować zebrane dane po przerwaniu pracy. Przy kolejnym uruchomieniu program zaczyna jednak od początku. Jeśli błąd wystąpi przed uruchomieniem przeglądarki, scraper zapisze jego opis tekstowy i log. Zrzut ekranu oraz HTML można zapisać dopiero wtedy, gdy istnieje sesja przeglądarki.

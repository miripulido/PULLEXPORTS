"""
AutoExport Scraper - 100% gratuito
Fuentes: AutoScout24, mobile.de, Kleinanzeigen, leboncoin.fr
Precios ES: coches.net, wallapop
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import random
import re
from datetime import datetime
from supabase import create_client
import os

# ─── CONFIG ──────────────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

MAX_PRICE_EUR = 30000
EXCLUDE_COUNTRIES = ["IT"]
COST_EXTRA = 6000  # gastos homologación + transporte estimados

# Modelos objetivo: los que en España se venden más caros que en el resto de Europa
TARGET_MODELS = [
    # Muscle americanos
    "Camaro", "Mustang", "Challenger", "Charger", "Corvette",
    # Pickups
    "RAM 1500", "RAM 2500", "F-150", "F-250", "Silverado", "Sierra", "Tundra",
    # SUVs grandes americanos
    "Tahoe", "Suburban", "Escalade", "Navigator", "Expedition",
    "Bronco", "Wrangler",
    # Performance con packs especiales
    "M3", "M4", "M5", "M8", "AMG GT", "C63", "E63", "RS6", "RS7", "RS3",
    # Descapotables
    "Mustang Convertible", "Z4", "SL",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def sleep_random(min_s=1.5, max_s=3.5):
    """Pausa aleatoria para no ser bloqueado"""
    time.sleep(random.uniform(min_s, max_s))


# ─── AUTOSCOUT24 ──────────────────────────────────────────────────────────────

def scrape_autoscout24(model: str, country_code: str = "D") -> list:
    """
    Scraping de AutoScout24.
    country_code: D=Alemania, F=Francia, B=Bélgica, PL=Polonia, P=Portugal
    """
    results = []
    country_map = {"DE": "D", "FR": "F", "BE": "B", "PL": "PL", "PT": "P"}

    for country, code in country_map.items():
        if country in EXCLUDE_COUNTRIES:
            continue

        # Construir URL de búsqueda
        model_slug = model.lower().replace(" ", "-").replace("/", "-")
        url = (
            f"https://www.autoscout24.com/lst/{model_slug}"
            f"?atype=C&cy={code}&damaged_listing=exclude"
            f"&desc=0&ocs_listing=include&priceto={MAX_PRICE_EUR}"
            f"&search_id=&sort=standard&source=listpage_pagination&ustate=N%2CU"
        )

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"[AutoScout24] {country} {model}: HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # Buscar listados de coches en la página
            listings = soup.find_all("article", {"data-item-name": "listing-item"})

            for listing in listings[:10]:  # Máximo 10 por búsqueda
                try:
                    car = parse_autoscout24_listing(listing, country, model)
                    if car:
                        results.append(car)
                except Exception as e:
                    print(f"[AutoScout24] Error parseando listing: {e}")
                    continue

        except Exception as e:
            print(f"[AutoScout24] Error {country} {model}: {e}")

        sleep_random()

    return results


def parse_autoscout24_listing(listing, country: str, model_query: str) -> dict | None:
    """Parsea un listing de AutoScout24 y devuelve dict normalizado"""
    try:
        # Precio
        price_el = listing.find("p", {"data-testid": "price-label"})
        if not price_el:
            price_el = listing.find(class_=re.compile(r"price"))
        if not price_el:
            return None

        price_text = price_el.get_text(strip=True).replace(".", "").replace(",", "").replace("€", "").strip()
        price_match = re.search(r"\d+", price_text.replace(" ", ""))
        if not price_match:
            return None
        price = int(price_match.group())

        if price > MAX_PRICE_EUR or price < 3000:
            return None

        # Título / modelo
        title_el = listing.find("h2") or listing.find("strong")
        title = title_el.get_text(strip=True) if title_el else model_query

        # Año y km
        details = listing.find_all("span", class_=re.compile(r"detail|spec|info"))
        year, km = None, None
        for d in details:
            text = d.get_text(strip=True)
            if re.match(r"^(19|20)\d{2}$", text):
                year = int(text)
            elif "km" in text.lower():
                km_match = re.search(r"[\d.,]+", text)
                if km_match:
                    km = int(km_match.group().replace(".", "").replace(",", ""))

        # URL del anuncio
        link = listing.find("a", href=True)
        url = "https://www.autoscout24.com" + link["href"] if link and link["href"].startswith("/") else (link["href"] if link else "")

        # Extrae CV si aparece
        cv = None
        cv_match = re.search(r"(\d{2,4})\s*(PS|CV|hp|kW)", listing.get_text(), re.IGNORECASE)
        if cv_match:
            val = int(cv_match.group(1))
            unit = cv_match.group(2).lower()
            cv = int(val * 1.36) if unit == "kw" else val

        return {
            "source": "autoscout24",
            "title": title,
            "make": title.split()[0] if title else "",
            "model": " ".join(title.split()[1:3]) if title else model_query,
            "year": year,
            "km": km,
            "price": price,
            "country": country,
            "cv": cv,
            "url": url,
            "scraped_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        print(f"[parse_autoscout24] Error: {e}")
        return None


# ─── MOBILE.DE ────────────────────────────────────────────────────────────────

def scrape_mobile_de(model: str) -> list:
    """Scraping de mobile.de - mayor marketplace alemán"""
    results = []

    # mobile.de usa una API interna JSON que podemos consultar
    # Endpoint de búsqueda
    search_query = model.replace(" ", "+")
    url = (
        f"https://suchen.mobile.de/fahrzeuge/search.html"
        f"?dam=0&isSearchRequest=true&ms=&ocs=&ref=quickSearch"
        f"&s=Car&sb=rel&od=down&maxPrice={MAX_PRICE_EUR}"
        f"&fr=&pw=&dm=&cc=&ml=&fe=&gb=&tr=&fuel=&tec=&zip=&zipr=&lang=de"
        f"&q={search_query}"
    )

    try:
        resp = requests.get(url, headers={**HEADERS, "Accept-Language": "de-DE,de;q=0.9"}, timeout=15)
        if resp.status_code != 200:
            print(f"[mobile.de] {model}: HTTP {resp.status_code}")
            return results

        soup = BeautifulSoup(resp.text, "html.parser")

        # Buscar resultados en la página
        listings = soup.find_all("div", class_=re.compile(r"cBox-body--resultitem|result-item|g-row"))

        for listing in listings[:8]:
            try:
                car = parse_mobile_de_listing(listing, model)
                if car:
                    results.append(car)
            except Exception as e:
                print(f"[mobile.de] Error parseando: {e}")

    except Exception as e:
        print(f"[mobile.de] Error {model}: {e}")

    sleep_random()
    return results


def parse_mobile_de_listing(listing, model_query: str) -> dict | None:
    """Parsea un listing de mobile.de"""
    try:
        text = listing.get_text(" ", strip=True)

        # Precio
        price_match = re.search(r"([\d.]+)\s*€", text)
        if not price_match:
            return None
        price = int(price_match.group(1).replace(".", ""))
        if price > MAX_PRICE_EUR or price < 3000:
            return None

        # Año
        year_match = re.search(r"\b(19|20)\d{2}\b", text)
        year = int(year_match.group()) if year_match else None

        # Km
        km_match = re.search(r"([\d.]+)\s*km", text, re.IGNORECASE)
        km = int(km_match.group(1).replace(".", "")) if km_match else None

        # Título
        title_el = listing.find("span", class_=re.compile(r"headline|title|name"))
        title = title_el.get_text(strip=True) if title_el else model_query

        # CV/PS
        cv = None
        cv_match = re.search(r"(\d{2,4})\s*(PS|KW|CV)", text, re.IGNORECASE)
        if cv_match:
            val = int(cv_match.group(1))
            unit = cv_match.group(2).lower()
            cv = int(val * 1.36) if unit == "kw" else val

        # URL
        link = listing.find("a", href=True)
        url = ""
        if link:
            href = link["href"]
            url = href if href.startswith("http") else "https://suchen.mobile.de" + href

        return {
            "source": "mobile.de",
            "title": title,
            "make": title.split()[0] if title else "",
            "model": " ".join(title.split()[1:3]) if title else model_query,
            "year": year,
            "km": km,
            "price": price,
            "country": "DE",  # mobile.de es mayoritariamente Alemania
            "cv": cv,
            "url": url,
            "scraped_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        print(f"[parse_mobile_de] Error: {e}")
        return None


# ─── KLEINANZEIGEN ────────────────────────────────────────────────────────────

def scrape_kleinanzeigen(model: str) -> list:
    """Kleinanzeigen.de - particulares, precios más bajos"""
    results = []

    search_query = model.replace(" ", "+")
    url = f"https://www.kleinanzeigen.de/s-autos/{search_query}/k0c216+l0"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return results

        soup = BeautifulSoup(resp.text, "html.parser")
        listings = soup.find_all("article", class_=re.compile(r"aditem"))

        for listing in listings[:8]:
            try:
                price_el = listing.find(class_=re.compile(r"price"))
                if not price_el:
                    continue

                price_text = price_el.get_text(strip=True)
                price_match = re.search(r"[\d.]+", price_text.replace(".", ""))
                if not price_match:
                    continue

                price_clean = price_el.get_text(strip=True).replace(".", "").replace("€", "").replace(" ", "")
                p_match = re.search(r"\d+", price_clean)
                if not p_match:
                    continue
                price = int(p_match.group())
                if price > MAX_PRICE_EUR or price < 3000:
                    continue

                title_el = listing.find("h2") or listing.find(class_=re.compile(r"title|headline"))
                title = title_el.get_text(strip=True) if title_el else model

                desc = listing.get_text(" ", strip=True)
                year_match = re.search(r"\b(19|20)\d{2}\b", desc)
                year = int(year_match.group()) if year_match else None
                km_match = re.search(r"([\d.]+)\s*km", desc, re.IGNORECASE)
                km = int(km_match.group(1).replace(".", "")) if km_match else None

                link = listing.find("a", href=True)
                url_car = ""
                if link:
                    href = link["href"]
                    url_car = href if href.startswith("http") else "https://www.kleinanzeigen.de" + href

                results.append({
                    "source": "kleinanzeigen",
                    "title": title,
                    "make": title.split()[0],
                    "model": " ".join(title.split()[1:3]),
                    "year": year,
                    "km": km,
                    "price": price,
                    "country": "DE",
                    "cv": None,
                    "url": url_car,
                    "scraped_at": datetime.utcnow().isoformat(),
                })
            except Exception:
                continue

    except Exception as e:
        print(f"[Kleinanzeigen] Error {model}: {e}")

    sleep_random()
    return results


# ─── PRECIO REFERENCIA ESPAÑA (coches.net) ───────────────────────────────────

def get_spain_reference_price(make: str, model: str, year: int | None) -> int | None:
    """
    Obtiene precio de referencia en España desde coches.net
    Devuelve el precio mediano encontrado o None
    """
    if not make or not model:
        return None

    query = f"{make} {model}".strip()
    search_q = query.replace(" ", "+")
    url = f"https://www.coches.net/segunda-mano/{search_q.lower().replace('+', '-')}/?or=2&pg=1"

    try:
        resp = requests.get(url, headers={**HEADERS, "Accept-Language": "es-ES,es;q=0.9"}, timeout=15)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        prices = []

        # Buscar precios en los resultados
        price_els = soup.find_all(class_=re.compile(r"price|precio"))
        for el in price_els:
            text = el.get_text(strip=True)
            match = re.search(r"([\d.]+)\s*€", text.replace(".", "").replace(",", ""))
            if match:
                p = int(re.search(r"\d+", text.replace(".", "").replace(",", "").replace("€", "")).group())
                if 5000 < p < 200000:
                    prices.append(p)

        if not prices:
            return None

        # Devuelve la mediana para evitar outliers
        prices.sort()
        return prices[len(prices) // 2]

    except Exception as e:
        print(f"[coches.net] Error {make} {model}: {e}")
        return None

    finally:
        sleep_random(1, 2)


# ─── SCORE DE OPORTUNIDAD ─────────────────────────────────────────────────────

def calculate_score(car: dict, spain_price: int | None) -> dict:
    """
    Calcula score de oportunidad (0-100) y margen estimado.
    Factores: margen bruto, CV, rareza del modelo, km bajos.
    """
    score = 50
    margin_pct = 0
    profit = 0
    est_sale = spain_price

    if spain_price and spain_price > 0:
        total_cost = car["price"] + COST_EXTRA
        profit = spain_price - total_cost
        margin_pct = round((profit / spain_price) * 100, 1)

        # Puntuación por margen
        if margin_pct >= 40:
            score += 30
        elif margin_pct >= 30:
            score += 20
        elif margin_pct >= 20:
            score += 10
        elif margin_pct < 10:
            score -= 20

    # Puntuación por CV (más potencia = más vendible en ES)
    cv = car.get("cv") or 0
    if cv >= 600:
        score += 15
    elif cv >= 400:
        score += 10
    elif cv >= 300:
        score += 5

    # Puntuación por km bajos
    km = car.get("km") or 99999
    if km < 20000:
        score += 10
    elif km < 40000:
        score += 5
    elif km > 80000:
        score -= 10

    # Puntuación por origen alemán (más fiable para homologaciones)
    if car.get("country") == "DE":
        score += 5

    # Clamp entre 0-100
    score = max(0, min(100, score))

    return {
        **car,
        "spain_ref_price": spain_price,
        "estimated_profit": profit,
        "margin_pct": margin_pct,
        "opportunity_score": score,
        "total_cost_estimate": car["price"] + COST_EXTRA,
    }


# ─── SUPABASE ─────────────────────────────────────────────────────────────────

def save_to_supabase(cars: list):
    """Guarda coches en Supabase. Hace upsert por URL para no duplicar."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[Supabase] Sin credenciales - guardando en JSON local")
        save_local(cars)
        return

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Filtrar coches con URL (necesaria para upsert)
    valid_cars = [c for c in cars if c.get("url")]

    if not valid_cars:
        print("[Supabase] No hay coches válidos para guardar")
        return

    try:
        result = supabase.table("cars").upsert(valid_cars, on_conflict="url").execute()
        print(f"[Supabase] Guardados {len(valid_cars)} coches")
    except Exception as e:
        print(f"[Supabase] Error: {e}")
        save_local(cars)


def save_local(cars: list):
    """Fallback: guarda en JSON si no hay Supabase"""
    output = {
        "updated_at": datetime.utcnow().isoformat(),
        "total": len(cars),
        "cars": sorted(cars, key=lambda x: x.get("opportunity_score", 0), reverse=True)
    }
    with open("cars_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"[Local] Guardados {len(cars)} coches en cars_data.json")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def run():
    print(f"\n{'='*50}")
    print(f"AutoExport Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}\n")

    all_cars = []

    for model in TARGET_MODELS:
        print(f"\n[→] Buscando: {model}")

        # Scrape todas las fuentes
        cars_as = scrape_autoscout24(model)
        cars_mo = scrape_mobile_de(model)
        cars_kl = scrape_kleinanzeigen(model)

        raw = cars_as + cars_mo + cars_kl
        print(f"    Encontrados: {len(raw)} anuncios ({len(cars_as)} AS24 / {len(cars_mo)} mobile.de / {len(cars_kl)} Klein.)")

        # Para cada coche, obtener precio de referencia en España y calcular score
        for car in raw:
            if not car:
                continue
            spain_price = get_spain_reference_price(car.get("make", ""), car.get("model", ""), car.get("year"))
            scored = calculate_score(car, spain_price)

            # Solo incluir si tiene margen positivo o no tenemos precio ES
            if scored.get("estimated_profit", 0) > 0 or spain_price is None:
                all_cars.append(scored)

    # Eliminar duplicados por URL
    seen_urls = set()
    unique_cars = []
    for car in all_cars:
        url = car.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_cars.append(car)
        elif not url:
            unique_cars.append(car)

    print(f"\n{'='*50}")
    print(f"Total coches únicos con margen positivo: {len(unique_cars)}")
    print(f"{'='*50}\n")

    # Top 5 oportunidades
    top5 = sorted(unique_cars, key=lambda x: x.get("opportunity_score", 0), reverse=True)[:5]
    print("TOP 5 OPORTUNIDADES:")
    for i, car in enumerate(top5, 1):
        print(f"  {i}. {car.get('year','')} {car.get('title','')} - {car.get('price','')}€ ({car.get('country','')}) → +{car.get('estimated_profit',0):.0f}€ beneficio | Score: {car.get('opportunity_score',0)}")

    save_to_supabase(unique_cars)
    print("\n[✓] Scraping completado\n")


if __name__ == "__main__":
    run()

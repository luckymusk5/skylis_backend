"""
Scraper pour NKCLMarket - Récupère les produits depuis le sitemap XML
"""

import asyncio
import httpx
import json
import os
import re
from bs4 import BeautifulSoup
from scraper_utils import (
    fetch_url, get_meta_tag, get_meta_property, extract_price,
    build_product,
    MAX_CONCURRENT_REQUESTS, fetch_sitemap_urls, clean_text, HEADERS
)

OUTPUT_FILE = "nkclmarket_products.jsonl"
SITEMAP_URL = "https://nkclmarket.com/sitemap.xml"


def extract_price_simple(price_text):
    """Extrait le prix simple - enlève juste les caractères non-numériques"""
    if not price_text:
        return 0
    try:
        digits_only = re.sub(r'[^\d]', '', str(price_text).strip())
        return int(digits_only) if digits_only else 0
    except (ValueError, AttributeError):
        return 0


def parse_single_price(text):
    """
    Parse un seul prix FCFA depuis un texte court.

    Règles FCFA :
      - Le point (.) est un séparateur de milliers : 270.000 = 270 000 FCFA
      - La virgule (,) est aussi un séparateur de milliers : 270,000 = 270 000 FCFA
      - L'espace est séparateur de milliers : 270 000 = 270 000 FCFA
      - Il n'y a PAS de décimales en FCFA (monnaie entière)

    Stratégie :
      1. Extraire le pattern prix complet AVANT de supprimer les séparateurs
         → on cherche le motif  digits(sep digits{3})+ pour capturer 270.000 entier
      2. Supprimer tous les séparateurs pour obtenir l'entier
      3. Vérifier la plage plausible (500 – 50 000 000 FCFA)
    """
    if not text:
        return 0

    # ── Étape 1 : capturer un prix avec séparateurs de milliers ──────────────
    # Cherche : un ou plusieurs groupes de chiffres séparés par . , ou espace
    # Exemple : "270.000", "1.500.000", "35 000", "270,000"
    # Le pattern capture le prix COMPLET y compris tous les groupes de milliers
    price_pattern = re.compile(
        r'\b(\d{1,3}(?:[.\s,]\d{3})+)\b'  # 270.000 / 1.500.000 / 35 000
        r'|'
        r'\b(\d+)\b'                        # fallback : nombre simple sans séparateur
    )

    for match in price_pattern.finditer(text):
        raw = match.group(1) or match.group(2)

        # ── Étape 2 : supprimer TOUS les séparateurs (., espace) ─────────────
        # En FCFA, point et virgule sont TOUJOURS des milliers, jamais décimaux
        clean = re.sub(r'[.\s,]', '', raw)

        if not clean.isdigit():
            continue

        value = int(clean)

        # ── Étape 3 : plage plausible pour un produit e-commerce camerounais ─
        # Min : 500 FCFA (petit accessoire)
        # Max : 50 000 000 FCFA (électroménager haut de gamme)
        if 500 <= value <= 50_000_000:
            return value

    return 0


async def extract_price_from_html(soup):
    """
    Extrait le prix depuis la page produit.

    Stratégie : cibler des éléments précis dans l'ordre de fiabilité,
    et traiter chaque élément INDIVIDUELLEMENT (jamais tout le texte de la page).

    Pourquoi le bug précédent apparaissait :
      La Méthode 3 faisait soup.get_text() sur toute la page,
      ce qui collait "235 000" et "290 500" en un seul flux de texte.
      re.findall retournait alors "235000290500" comme premier token.
    """

    # ── Méthode 1 : meta og:price:amount (le plus fiable, prix unique) ───────
    price_text = get_meta_property(soup, 'og:price:amount')
    if price_text:
        p = parse_single_price(price_text)
        if p:
            return p

    # ── Méthode 2 : meta og:price (fallback meta) ────────────────────────────
    price_text = get_meta_property(soup, 'og:price')
    if price_text:
        p = parse_single_price(price_text)
        if p:
            return p

    # ── Méthode 3 : JSON-LD structuré ────────────────────────────────────────
    # Sites e-commerce sérieux exposent le prix en JSON-LD (schema.org/Product)
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            import json as _json
            data = _json.loads(script.string or '')
            # Peut être un dict ou une liste
            if isinstance(data, list):
                data = data[0]
            offers = data.get('offers', {})
            if isinstance(offers, list):
                offers = offers[0]
            price_raw = offers.get('price', '')
            if price_raw:
                p = parse_single_price(str(price_raw))
                if p:
                    return p
        except Exception:
            pass

    # ── Méthode 4 : éléments HTML avec classe prix ───────────────────────────
    # On cible les sélecteurs les plus spécifiques en premier.
    # IMPORTANT : on appelle get_text() sur UN élément à la fois,
    # jamais sur soup entier — c'est ce qui évite la concaténation de prix.
    price_selectors = [
        # Prix courant (souvent dans une balise avec "new" ou "current")
        {'class': re.compile(r'price[-_]?(new|current|sale|final|now)', re.I)},
        {'class': re.compile(r'(new|current|sale|final|now)[-_]?price', re.I)},
        # Prix générique ensuite
        {'class': re.compile(r'\bprice\b|\bprix\b', re.I)},
        {'itemprop': 'price'},
        {'data-price': True},
    ]

    for selector in price_selectors:
        elements = soup.find_all(['span', 'div', 'p', 'strong', 'ins'], attrs=selector)
        for elem in elements:
            # Prend uniquement le texte direct de cet élément (pas ses enfants)
            # pour éviter d'agréger plusieurs prix imbriqués
            own_text = elem.get_text(separator=' ', strip=True)

            # Si l'élément contient lui-même plusieurs sous-éléments de prix,
            # prendre uniquement le premier enfant texte significatif
            children_texts = [
                c.get_text(strip=True)
                for c in elem.find_all(['span', 'strong', 'ins', 'b'], recursive=False)
            ]
            candidates = children_texts if children_texts else [own_text]

            for candidate in candidates:
                p = parse_single_price(candidate)
                if p:
                    return p

    # ── Méthode 5 : input hidden price (certains sites e-commerce) ───────────
    for inp in soup.find_all('input', {'name': re.compile(r'price', re.I)}):
        val = inp.get('value', '')
        p = parse_single_price(val)
        if p:
            return p

    # ── Pas de prix trouvé ────────────────────────────────────────────────────
    return 0


async def fetch_product_details(client, product_url, semaphore):
    """Récupère les détails d'un produit NKCLMarket"""
    content = await fetch_url(client, product_url, semaphore)
    if not content:
        return {}

    soup = BeautifulSoup(content, 'lxml')

    title = get_meta_tag(soup, 'name', 'title')
    title = clean_text(title)

    description = get_meta_property(soup, 'og:description')
    description = clean_text(description)

    image_url = get_meta_property(soup, 'og:image')
    images = [image_url] if image_url else []

    # ← fix : on passe uniquement soup, pas l'URL
    price = await extract_price_from_html(soup)

    return {
        'title': title,
        'description': description,
        'price': price,
        'images': images
    }


async def scrape():
    """Scrape les données de NKCLMarket depuis le sitemap XML"""
    try:
        MAX_PARALLEL_REQUESTS = 30

        print("   📥 Récupération du sitemap NKCLMarket...", flush=True)
        product_urls = fetch_sitemap_urls(SITEMAP_URL)

        print(f"   📊 {len(product_urls)} produits trouvés dans le sitemap", flush=True)

        if not product_urls:
            print("   ⚠️  Aucun produit trouvé pour NKCLMarket", flush=True)
            return 0

        print(f"   💾 Écriture des données dans {OUTPUT_FILE}...", flush=True)
        count = 0
        skipped_price = 0

        if os.path.exists(OUTPUT_FILE):
            os.remove(OUTPUT_FILE)

        print(f"   ⚡ Récupération des détails ({MAX_PARALLEL_REQUESTS} requêtes parallèles)...", flush=True)

        with open(OUTPUT_FILE, 'a', encoding='utf-8', buffering=8192 * 4) as f:
            async with httpx.AsyncClient(
                http2=True,
                limits=httpx.Limits(max_keepalive_connections=200, max_connections=200),
                timeout=5.0
            ) as client:
                for batch_start in range(0, len(product_urls), MAX_PARALLEL_REQUESTS):
                    batch_end = min(batch_start + MAX_PARALLEL_REQUESTS, len(product_urls))
                    batch_urls = product_urls[batch_start:batch_end]

                    semaphore = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)

                    try:
                        tasks = [fetch_product_details(client, url, semaphore) for url in batch_urls]
                        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                        for product_url, product_data in zip(batch_urls, batch_results):
                            if not isinstance(product_data, dict) or not product_data.get('title'):
                                continue

                            price = product_data.get('price', 0)

                            # ── Sanity check prix ─────────────────────────────
                            # Un prix plausible pour un e-commerce camerounais :
                            # entre 500 FCFA et 50 000 000 FCFA
                            if price > 50_000_000:
                                skipped_price += 1
                                # Log pour débogage — utile pour ajuster la limite
                                print(
                                    f"      ⚠️  Prix suspect ignoré : {price:,} FCFA "
                                    f"— {product_url}",
                                    flush=True
                                )
                                price = 0  # on garde le produit mais sans prix

                            final_product = build_product(
                                url=product_url,
                                title=product_data.get('title', ''),
                                images=product_data.get('images', []),
                                price=float(price),
                                description=product_data.get('description', '')
                            )
                            f.write(json.dumps(final_product, ensure_ascii=False) + '\n')
                            count += 1

                    except Exception as batch_error:
                        pass

                    if (batch_start // MAX_PARALLEL_REQUESTS) % 10 == 0:
                        print(
                            f"      ✅ {count} produits sauvegardés "
                            f"({batch_end}/{len(product_urls)})",
                            flush=True
                        )

        print(f"   ✅ {count} produits stockés dans {OUTPUT_FILE}", flush=True)
        if skipped_price:
            print(f"   ⚠️  {skipped_price} produits avec prix suspect (remis à 0)", flush=True)
        return count

    except Exception as e:
        print(f"   ❌ Erreur lors du scraping NKCLMarket: {str(e)}", flush=True)
        return 0


if __name__ == "__main__":
    result = asyncio.run(scrape())
    print(f"Résultat: {result} produits scrappés")
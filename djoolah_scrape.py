"""
Scraper pour Djoolah - Récupère les produits depuis le sitemap XML
"""

import asyncio
import httpx
import json
import os
import re
import requests
from bs4 import BeautifulSoup
from scraper_utils import (
    fetch_url, get_meta_tag, get_meta_property, extract_price, 
    get_images_from_img_tags, build_product,
    MAX_CONCURRENT_REQUESTS, fetch_sitemap_urls, clean_text, HEADERS
)

OUTPUT_FILE = "djoolah_products.jsonl"
SITEMAP_URL = "https://djoolah.com/product-sitemap.xml"


async def extract_price_from_html(soup, product_url):
    """Extrait le prix directement du HTML asynchrone - prend le plus petit prix"""
    try:
        all_prices = []
        
        # Méthode 1: <p class="price">
        prix_tags = soup.find_all("p", class_="price")
        for tag in prix_tags:
            if tag and tag.text:
                extracted = extract_price(tag.text.strip())
                if extracted > 0:
                    all_prices.append(extracted)
        
        # Méthode 2: meta og:price
        if not all_prices:
            price_text = get_meta_property(soup, 'og:price')
            if price_text:
                extracted = extract_price(price_text)
                if extracted > 0:
                    all_prices.append(extracted)
        
        # Méthode 3: Chercher tous les span ou div contenant le prix
        if not all_prices:
            price_elements = soup.find_all(['span', 'div'], class_=re.compile(r'price|prix', re.I))
            for elem in price_elements:
                price_text = elem.get_text(strip=True)
                extracted = extract_price(price_text)
                if extracted > 0:
                    all_prices.append(extracted)
        
        # Retourne le plus petit prix trouvé (meilleure offre)
        return min(all_prices) if all_prices else 0.0
    except Exception as e:
        return 0.0


async def fetch_product_details(client, product_url, semaphore):
    """Récupère les détails d'un produit Djoolah"""
    content = await fetch_url(client, product_url, semaphore)
    if not content:
        return {}
    
    soup = BeautifulSoup(content, 'html.parser')
    
    # Titre depuis title tag
    title_tag = soup.find('title')
    title = title_tag.text.strip() if title_tag else ''
    title = clean_text(title)
    
    # Description depuis og:description
    description = get_meta_property(soup, 'og:description')
    description = clean_text(description)
    
    # Image depuis div spécifique
    images = get_images_from_img_tags(soup, css_class='cgkit-product-image')
    
    # Prix directement du HTML asynchrone
    price = await extract_price_from_html(soup, product_url)
    
    return {
        'title': title,
        'description': description,
        'price': price,
        'images': images
    }


async def scrape_products_async(product_urls):
    """Scrape les détails de tous les produits en parallèle"""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    
    async with httpx.AsyncClient() as client:
        tasks = [fetch_product_details(client, url, semaphore) for url in product_urls]
        return await asyncio.gather(*tasks, return_exceptions=True)


async def scrape():
    """Scrape les données de Djoolah depuis le sitemap XML avec streaming"""
    try:
        # Étape 1: Parser le sitemap
        print("   📥 Récupération du sitemap Djoolah...", flush=True)
        product_urls = fetch_sitemap_urls(SITEMAP_URL)
        print(f"   📊 {len(product_urls)} produits trouvés dans le sitemap", flush=True)
        
        if not product_urls:
            return 0
        
        # Étape 2: Préparer le fichier
        print(f"   💾 Écriture des données dans {OUTPUT_FILE}...", flush=True)
        count = 0
        
        if os.path.exists(OUTPUT_FILE):
            os.remove(OUTPUT_FILE)
        
        # Étape 3: Scraper par batches et écrire immédiatement
        print(f"   ⚡ Récupération des détails ({MAX_CONCURRENT_REQUESTS} requêtes parallèles)...", flush=True)
        
        with open(OUTPUT_FILE, 'a', encoding='utf-8', buffering=8192*4) as f:
            # Crée le client une seule fois pour les connexions persistantes HTTP/2
            async with httpx.AsyncClient(http2=True, limits=httpx.Limits(max_keepalive_connections=200, max_connections=200), timeout=5.0) as client:
                # Traite par batches - batches plus gros pour plus de vitesse
                for batch_start in range(0, len(product_urls), MAX_CONCURRENT_REQUESTS):
                    batch_end = min(batch_start + MAX_CONCURRENT_REQUESTS, len(product_urls))
                    batch_urls = product_urls[batch_start:batch_end]
                    
                    # Scrape ce batch en parallèle
                    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
                    
                    try:
                        tasks = [fetch_product_details(client, url, semaphore) for url in batch_urls]
                        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                        
                        # Écris immédiatement
                        for product_url, product_data in zip(batch_urls, batch_results):
                            if isinstance(product_data, dict):
                                final_product = build_product(
                                    url=product_url,
                                    title=product_data.get('title', ''),
                                    images=product_data.get('images', []),
                                    price=product_data.get('price', 0.0),
                                    description=product_data.get('description', '')
                                )
                                f.write(json.dumps(final_product, ensure_ascii=False) + '\n')
                                count += 1
                    except Exception as batch_error:
                        pass
                    
                    print(f"      ✅ {count}/{len(product_urls)} produits sauvegardés", flush=True)
        
        print(f"   ✅ {count} produits trouvés et stockés dans {OUTPUT_FILE}", flush=True)
        return count
        
    except Exception as e:
        print(f"   ❌ Erreur lors du scraping Djoolah: {str(e)}", flush=True)
        return 0


if __name__ == "__main__":
    result = asyncio.run(scrape())
    print(f"Résultat: {result} produits scrappés")

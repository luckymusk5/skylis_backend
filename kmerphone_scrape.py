"""
Scraper pour KmerPhone - Récupère les produits depuis le sitemap XML
"""

import asyncio
import httpx
import json
import os
from bs4 import BeautifulSoup
from scraper_utils import (
    fetch_url, get_meta_tag, extract_price, 
    extract_sitemap_products, build_product,
    MAX_CONCURRENT_REQUESTS, clean_text
)

OUTPUT_FILE = "kmerphone_products.jsonl"
# URL du sitemap avec tous les produits
SITEMAP_URL = "https://kmerphone.com/sitemap_products_1.xml?from=4531847921751&to=9546644586739"


async def fetch_product_details(client, product_url, semaphore):
    """Récupère la description et le prix d'une page produit"""
    content = await fetch_url(client, product_url, semaphore)
    if not content:
        return {}
    
    soup = BeautifulSoup(content, 'html.parser')
    
    # Titre depuis title tag - prendre avant le " : "
    title = ''
    title_tag = soup.find('title')
    if title_tag:
        full_title = title_tag.text.strip()
        # Extraire la partie avant " : "
        if ' : ' in full_title or ' – ' in full_title:
            title = full_title.split(' : ' if ' : ' in full_title else ' – ')[0].strip()
        else:
            title = full_title
    
    title = clean_text(title)
    
    # Description depuis meta tag
    description = get_meta_tag(soup, 'name', 'description')
    description = clean_text(description)
    
    # Prix depuis span avec id pbb4-price (structure: <span id="pbb4-price">335.000</span>)
    price = 0.0
    price_span = soup.find('span', id='pbb4-price')
    if price_span:
        price = extract_price(price_span.text)
    else:
        # Fallback: chercher par classe
        price_span = soup.find('span', class_='pbb4-price-main')
        if price_span:
            price = extract_price(price_span.text)
    
    return {
        'title': title,
        'description': description,
        'price': price
    }


async def scrape_products_async(product_urls):
    """Scrape les descriptions de tous les produits en parallèle"""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    
    async with httpx.AsyncClient() as client:
        tasks = [fetch_product_details(client, url, semaphore) for url in product_urls]
        return await asyncio.gather(*tasks, return_exceptions=True)


async def scrape():
    """Scrape les données de KmerPhone depuis le sitemap XML"""
    try:
        # Configuration optimisée pour vitesse maximale
        MAX_PARALLEL_REQUESTS = 100  # Requêtes parallèles avec HTTP/2
        
        # Étape 1: Parser le sitemap
        print("   📥 Récupération du sitemap...", flush=True)
        products = extract_sitemap_products(SITEMAP_URL)
        
        print(f"   📊 {len(products)} produits trouvés dans le sitemap", flush=True)
        
        if not products:
            print(f"   ⚠️  Aucun produit trouvé pour KmerPhone", flush=True)
            return 0
        
        # Étape 2: Préparer le fichier
        print(f"   💾 Écriture des données dans {OUTPUT_FILE}...", flush=True)
        count = 0
        
        if os.path.exists(OUTPUT_FILE):
            os.remove(OUTPUT_FILE)
        
        # Étape 3: Scraper par batches et écrire immédiatement
        product_urls = [p['url'] for p in products]
        print(f"   ⚡ Récupération des descriptions ({MAX_PARALLEL_REQUESTS} requêtes parallèles)...", flush=True)
        
        with open(OUTPUT_FILE, 'a', encoding='utf-8', buffering=8192*4) as f:
            # Crée le client une seule fois pour les connexions persistantes HTTP/2
            async with httpx.AsyncClient(http2=True, limits=httpx.Limits(max_keepalive_connections=200, max_connections=200), timeout=5.0) as client:
                # Traite par petits batches pour ne pas surcharger le serveur
                for batch_start in range(0, len(product_urls), MAX_PARALLEL_REQUESTS):
                    batch_end = min(batch_start + MAX_PARALLEL_REQUESTS, len(product_urls))
                    batch_urls = product_urls[batch_start:batch_end]
                    batch_products = products[batch_start:batch_end]
                    
                    # Scrape ce batch en parallèle
                    semaphore = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)
                    
                    try:
                        tasks = [fetch_product_details(client, url, semaphore) for url in batch_urls]
                        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                        
                        # Écris immédiatement
                        for product, desc_data in zip(batch_products, batch_results):
                            if isinstance(desc_data, dict):
                                final_product = build_product(
                                    url=product['url'],
                                    title=desc_data.get('title') or product['title'],
                                    images=product['images'],
                                    price=desc_data.get('price', 0.0),
                                    description=desc_data.get('description', '')
                                )
                                f.write(json.dumps(final_product, ensure_ascii=False) + '\n')
                                count += 1
                    except Exception as batch_error:
                        pass
                    
                    print(f"      ✅ {count}/{len(product_urls)} produits sauvegardés", flush=True)
        
        print(f"   ✅ {count} produits trouvés et stockés dans {OUTPUT_FILE}", flush=True)
        return count
        
    except Exception as e:
        print(f"   ❌ Erreur lors du scraping KmerPhone: {str(e)}", flush=True)
        return 0


if __name__ == "__main__":
    result = asyncio.run(scrape())
    print(f"Résultat: {result} produits scrappés")

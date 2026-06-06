"""
Scraper pour TechDeal - Récupère les produits par ID auto-détection
"""

import asyncio
import httpx
import json
import os
from bs4 import BeautifulSoup
from scraper_utils import (
    fetch_url, get_meta_tag, get_meta_property, extract_price, 
    build_product, MAX_CONCURRENT_REQUESTS, HEADERS, REQUEST_TIMEOUT,
    clean_text
)

OUTPUT_FILE = "techdeal_products.jsonl"
BASE_URL = "https://tdlinkz.com/techdeal/product"


async def fetch_product_details(client, product_id, semaphore):
    """Récupère les détails d'un produit TechDeal par ID"""
    product_url = f"{BASE_URL}/{product_id}"
    content = await fetch_url(client, product_url, semaphore)
    
    if not content:
        return None
    
    soup = BeautifulSoup(content, 'html.parser')
    
    # Titre depuis og:title
    title = get_meta_property(soup, 'og:title')
    title = clean_text(title)
    
    # Image depuis og:image
    images = []
    image_url = get_meta_property(soup, 'og:image')
    if image_url:
        images.append(clean_text(image_url))
    
    # Description depuis og:description
    description = get_meta_property(soup, 'og:description')
    description = clean_text(description)
    
    # Prix depuis tag HTML <p class="m-0 fs-1 fw-semibold text-dark">
    price = 0.0
    price_tag = soup.find('p', class_='m-0 fs-1 fw-semibold text-dark')
    if price_tag and price_tag.text:
        price = extract_price(price_tag.text.strip())
    
    # Retourner None si produit invalide
    if not title or not images:
        return None
    
    return {
        'url': product_url,
        'title': title,
        'images': images,
        'price': price,
        'description': description
    }


async def scrape_products_async(product_ids):
    """Scrape les détails de tous les produits en parallèle"""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    
    async with httpx.AsyncClient() as client:
        tasks = [fetch_product_details(client, pid, semaphore) for pid in product_ids]
        return await asyncio.gather(*tasks, return_exceptions=True)


def determine_product_ids():
    """Les IDs des produits TechDeal sont entre 1 et 136"""
    print("   🔍 Chargement des IDs de produits (1-136)...", flush=True)
    product_ids = list(range(1, 137))
    print(f"   ✅ {len(product_ids)} IDs de produits chargés", flush=True)
    return product_ids


async def scrape():
    """Scrape les données de TechDeal avec streaming (écriture immédiate)"""
    try:
        # Étape 1: Charger les IDs
        product_ids = determine_product_ids()
        
        if not product_ids:
            print("   ⚠️  Aucun produit trouvé sur TechDeal", flush=True)
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
                for batch_start in range(0, len(product_ids), MAX_CONCURRENT_REQUESTS):
                    batch_end = min(batch_start + MAX_CONCURRENT_REQUESTS, len(product_ids))
                    batch_ids = product_ids[batch_start:batch_end]
                    
                    # Scrape ce batch en parallèle
                    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
                    
                    try:
                        tasks = [fetch_product_details(client, pid, semaphore) for pid in batch_ids]
                        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                        
                        # Écris immédiatement
                        for product_data in batch_results:
                            if isinstance(product_data, dict):
                                f.write(json.dumps(product_data, ensure_ascii=False) + '\n')
                                count += 1
                    except Exception as batch_error:
                        pass
                    
                    print(f"      ✅ {count}/{len(product_ids)} produits sauvegardés", flush=True)
        
        print(f"   ✅ {count} produits trouvés et stockés dans {OUTPUT_FILE}", flush=True)
        return count
        
    except Exception as e:
        print(f"   ❌ Erreur lors du scraping TechDeal: {str(e)}", flush=True)
        return 0


if __name__ == "__main__":
    result = asyncio.run(scrape())
    print(f"Résultat: {result} produits scrappés")

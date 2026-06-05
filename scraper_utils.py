"""
Utilitaires communs pour tous les scrapers
Contient les fonctions, constantes et patterns réutilisables
"""

import asyncio
import re
import time
import zlib
import xml.etree.ElementTree as ET
try:
    import lxml.etree
    HAS_LXML = True
except ImportError:
    HAS_LXML = False
try:
    import brotli
    HAS_BROTLI = True
except ImportError:
    HAS_BROTLI = False
from bs4 import BeautifulSoup
import httpx
import requests
import html

# ============= CONSTANTES GLOBALES =============
REQUEST_TIMEOUT = 10  # Timeout par requête (secondes)
SITEMAP_TIMEOUT = 60  # Timeout pour les sitemaps (60 secondes pour sites lents)
SITEMAP_RETRY_DELAY = 2  # Délai entre retries de sitemap
MAX_RETRIES = 4  # Nombre de retries en cas d'erreur
MAX_CONCURRENT_REQUESTS = 200  # Requêtes parallèles max avec HTTP/2 multiplexing
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}


def clean_text(text):
    """
    Nettoie un texte en supprimant:
    - Entités HTML (&nbsp;, &amp;, &eacute;, etc.)
    - Retours à la ligne multiples
    - Espaces multiples
    """
    if not text:
        return ''
    
    # Décoder les entités HTML
    text = html.unescape(text)
    
    # Enlever les retours à la ligne et remplacer par un espace
    text = re.sub(r'\n+', ' ', text)
    
    # Enlever les espaces multiples
    text = re.sub(r'\s+', ' ', text)
    
    # Enlever les espaces au début/fin
    return text.strip()


# ============= FONCTIONS ASYNC GÉNÉRIQUES =============
async def fetch_url(client, url, semaphore, retries=0):
    """
    Récupère le contenu d'une URL avec retry automatique
    Utilise backoff exponentiel pour les retries
    Retourne le contenu HTML/XML ou None en cas d'erreur
    """
    async with semaphore:
        try:
            response = await client.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                return response.text
            elif response.status_code == 404:
                return None
            else:
                if retries < MAX_RETRIES:
                    # Backoff exponentiel: 0.5s, 1s, 2s
                    wait_time = 0.5 * (2 ** retries)
                    await asyncio.sleep(wait_time)
                    return await fetch_url(client, url, semaphore, retries + 1)
                return None
        except asyncio.TimeoutError:
            if retries < MAX_RETRIES:
                wait_time = 0.5 * (2 ** retries)
                await asyncio.sleep(wait_time)
                return await fetch_url(client, url, semaphore, retries + 1)
            return None
        except Exception as e:
            if retries < MAX_RETRIES:
                wait_time = 0.5 * (2 ** retries)
                await asyncio.sleep(wait_time)
                return await fetch_url(client, url, semaphore, retries + 1)
            return None


# ============= FONCTIONS DE PARSING HTML =============
def get_meta_tag(soup, attr_name, attr_value):
    """Récupère la valeur d'une meta tag par attribut"""
    tag = soup.find('meta', attrs={attr_name: attr_value})
    return tag.get('content', '').strip() if tag else ''


def get_meta_property(soup, property_name):
    """Récupère la valeur d'une meta property (og:*)"""
    tag = soup.find('meta', attrs={'property': property_name})
    return tag.get('content', '').strip() if tag else ''


def extract_price(price_text):
    """
    Extrait le prix numérique d'un texte en entier (sans virgule)
    Prend SEULEMENT le PREMIER nombre trouvé
    Enlève les points/virgules mais garde le premier nombre seulement
    """
    if not price_text:
        return 0
    try:
        # Décode les entités HTML (&nbsp; → espace, &amp; → &, etc.)
        decoded = html.unescape(price_text)
        
        # Cherche le PREMIER nombre (avec ou sans séparateurs)
        # Pattern: capture un nombre avec optionnels séparateurs de milliers
        # Ex: "254.000", "254000", "1.234.567", etc.
        match = re.search(r'(\d+(?:[.,]\d+)*)', decoded.strip())
        
        if match:
            price_str = match.group(1)
            # Enlève les séparateurs (points et virgules = milliers, pas décimales)
            price_str = price_str.replace('.', '').replace(',', '')
            return int(price_str) if price_str else 0
        
        return 0
    except (ValueError, AttributeError):
        return 0


def get_image_from_meta(soup):
    """Récupère l'image principale depuis les meta tags og:image"""
    image_url = get_meta_property(soup, 'og:image')
    return [image_url] if image_url else []


def get_images_from_img_tags(soup, css_class=None, selector=None):
    """
    Récupère les images depuis les balises <img> 
    Peut filtrer par classe CSS ou sélecteur
    """
    images = []
    if selector:
        # Recherche dans un container spécifique
        container = soup.select_one(selector)
        if container:
            img_tags = container.find_all('img')
    elif css_class:
        # Recherche par classe CSS
        container = soup.find('div', class_=css_class)
        if container:
            img_tags = container.find_all('img')
        else:
            img_tags = []
    else:
        img_tags = soup.find_all('img')
    
    for img in img_tags:
        src = img.get('src', '').strip()
        if src:
            images.append(src)
    
    return images[:1] if images else []  # Retourne la première image


def extract_images_from_js(html_content, pattern=None):
    """
    Extrait les URLs d'images depuis du JavaScript
    Utilise un pattern regex personnalisé ou un défaut
    """
    if not pattern:
        pattern = r'"productImages"\s*:\s*\[(.*?)\]'
    
    match = re.search(pattern, html_content)
    if match:
        images_str = match.group(1)
        urls = re.findall(r'"(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', images_str)
        return urls[:1] if urls else []  # Première image
    return []


# ============= FONCTIONS DE PARSING SITEMAP =============
def fetch_sitemap_urls(sitemap_url, retries=0):
    """
    Récupère toutes les URLs d'un sitemap XML (synchrone) avec retry automatique
    """
    try:
        # Utilise session pour connection pooling
        session = requests.Session()
        session.headers.update(HEADERS)
        session.headers.update({
            'Accept-Encoding': 'gzip, deflate',
            'Accept': 'application/xml, text/xml, */*'
        })
        
        response = session.get(sitemap_url, timeout=SITEMAP_TIMEOUT, verify=False)
        if response.status_code != 200:
            if retries < MAX_RETRIES:
                wait_time = SITEMAP_RETRY_DELAY * (2 ** retries)
                time.sleep(wait_time)
                return fetch_sitemap_urls(sitemap_url, retries + 1)
            return []
        
        # Décompression manuelle
        raw = response.content
        
        # Tente décompression zlib/gzip
        try:
            raw = zlib.decompress(raw, wbits=47)  # wbits=47 accepte gzip ET zlib
        except Exception:
            pass
        
        # Tente décompression brotli
        if raw == response.content and HAS_BROTLI:
            try:
                raw = brotli.decompress(raw)
            except Exception:
                pass
        
        # Si toujours binaire (non-XML), log et abandon
        if not raw.lstrip()[:5] in (b'<?xml', b'<urls', b'<site'):
            print(f"   DEBUG: Réponse non-XML après décompression : {raw[:100]}", flush=True)
            if retries < MAX_RETRIES:
                wait_time = SITEMAP_RETRY_DELAY * (2 ** retries)
                time.sleep(wait_time)
                return fetch_sitemap_urls(sitemap_url, retries + 1)
            return []
        
        # DEBUG: Affiche les premiers 500 caractères pour voir ce que le serveur retourne
        print(f"   DEBUG: Response content (first 500 chars): {raw[:500]}", flush=True)
        
        # Essaie d'abord avec ElementTree standard
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as pe:
            # Fallback: essaie avec lxml qui répare le XML cassé
            if HAS_LXML:
                print(f"   DEBUG: ET.fromstring failed, trying lxml recovery parser", flush=True)
                try:
                    root = lxml.etree.fromstring(raw, lxml.etree.XMLParser(recover=True))
                except Exception as lxml_error:
                    print(f"   ❌ Lxml parsing also failed: {type(lxml_error).__name__}: {lxml_error}", flush=True)
                    raise pe
            else:
                raise pe
        
        urls = []
        
        # Parsing robuste avec namespaces
        # Namespaces possibles
        ns_uri = 'http://www.sitemaps.org/schemas/sitemap/0.9'
        
        # Cherche les éléments url
        for url_elem in root.findall(f'{{{ns_uri}}}url'):
            # Cherche l'élément loc (avec namespace)
            loc = url_elem.find(f'{{{ns_uri}}}loc')
            if loc is not None and loc.text:
                urls.append(loc.text.strip())
        
        # Si vide, essaie sans namespace
        if not urls:
            for url_elem in root.findall('url'):
                loc = url_elem.find('loc')
                if loc is not None and loc.text:
                    urls.append(loc.text.strip())
        
        session.close()
        return urls
    except (requests.Timeout, requests.ConnectionError) as e:
        if retries < MAX_RETRIES:
            wait_time = SITEMAP_RETRY_DELAY * (2 ** retries)
            print(f"   ⏳ Timeout sitemap: {type(e).__name__}: {e}, tentative {retries + 1}/{MAX_RETRIES} dans {wait_time}s...", flush=True)
            time.sleep(wait_time)
            return fetch_sitemap_urls(sitemap_url, retries + 1)
        return []
    except Exception as e:
        if retries < MAX_RETRIES:
            wait_time = SITEMAP_RETRY_DELAY * (2 ** retries)
            print(f"   ⏳ Erreur sitemap: {type(e).__name__}: {e}, tentative {retries + 1}/{MAX_RETRIES} dans {wait_time}s...", flush=True)
            time.sleep(wait_time)
            return fetch_sitemap_urls(sitemap_url, retries + 1)
        return []


def extract_sitemap_products(sitemap_url, retries=0):
    """
    Récupère les produits d'un sitemap en extrayant :
    - URL (loc)
    - Titre (image:caption ou title tag)
    - Images (image:loc)
    Inclut retry automatique avec backoff
    """
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        session.headers.update({
            'Accept-Encoding': 'gzip, deflate',
            'Accept': 'application/xml, text/xml, */*'
        })
        response = session.get(sitemap_url, timeout=SITEMAP_TIMEOUT, verify=False)
        if response.status_code != 200:
            if retries < MAX_RETRIES:
                wait_time = SITEMAP_RETRY_DELAY * (2 ** retries)
                time.sleep(wait_time)
                return extract_sitemap_products(sitemap_url, retries + 1)
            return []
        session.close()
        
        # Décompression manuelle
        raw = response.content
        
        # Tente décompression zlib/gzip
        try:
            raw = zlib.decompress(raw, wbits=47)  # wbits=47 accepte gzip ET zlib
        except Exception:
            pass
        
        # Tente décompression brotli
        if raw == response.content and HAS_BROTLI:
            try:
                raw = brotli.decompress(raw)
            except Exception:
                pass
        
        # Si toujours binaire (non-XML), log et abandon
        if not raw.lstrip()[:5] in (b'<?xml', b'<urls', b'<site'):
            print(f"   DEBUG: Réponse non-XML après décompression : {raw[:100]}", flush=True)
            if retries < MAX_RETRIES:
                wait_time = SITEMAP_RETRY_DELAY * (2 ** retries)
                time.sleep(wait_time)
                return extract_sitemap_products(sitemap_url, retries + 1)
            return []
        
        # DEBUG: Affiche les premiers 500 caractères pour voir ce que le serveur retourne
        print(f"   DEBUG: Response content (first 500 chars): {raw[:500]}", flush=True)
        
        # Essaie d'abord avec ElementTree standard
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as pe:
            # Fallback: essaie avec lxml qui répare le XML cassé
            if HAS_LXML:
                print(f"   DEBUG: ET.fromstring failed, trying lxml recovery parser", flush=True)
                try:
                    root = lxml.etree.fromstring(raw, lxml.etree.XMLParser(recover=True))
                except Exception as lxml_error:
                    print(f"   ❌ Lxml parsing also failed: {type(lxml_error).__name__}: {lxml_error}", flush=True)
                    raise pe
            else:
                raise pe
        
        products = []
        
        # Namespaces URIs
        ns_sitemap = 'http://www.sitemaps.org/schemas/sitemap/0.9'
        ns_image = 'http://www.google.com/schemas/sitemap-image/1.1'
        
        # Parsing robuste - cherche les éléments url avec namespace
        url_elems = root.findall(f'{{{ns_sitemap}}}url')
        
        # Si vide, essaie sans namespace
        if not url_elems:
            url_elems = root.findall('url')
        
        for url_elem in url_elems:
            # URL - cherche avec namespace d'abord
            loc = url_elem.find(f'{{{ns_sitemap}}}loc')
            if loc is None:
                loc = url_elem.find('loc')
            
            url = loc.text.strip() if loc is not None and loc.text else None
            
            if not url:
                continue
            
            # Titre depuis image:title ou image:caption
            title = ''
            # Cherche d'abord image:title
            title_elem = url_elem.find(f'{{{ns_image}}}title')
            
            # Fallback à image:caption
            if title_elem is None or not title_elem.text:
                title_elem = url_elem.find(f'{{{ns_image}}}caption')
            if title_elem is None:
                title_elem = url_elem.find('caption')
            
            if title_elem is not None and title_elem.text:
                title = title_elem.text.strip()
            
            # Images
            images = []
            # Cherche les éléments image avec namespace
            img_elems = url_elem.findall(f'{{{ns_image}}}image')
            if not img_elems:
                img_elems = url_elem.findall('image')
            
            for img_elem in img_elems:
                img_loc = img_elem.find(f'{{{ns_image}}}loc')
                if img_loc is None:
                    img_loc = img_elem.find('loc')
                if img_loc is not None and img_loc.text:
                    images.append(img_loc.text.strip())
            
            products.append({
                'url': url,
                'title': title,
                'images': images
            })
        
        return products
    except (requests.Timeout, requests.ConnectionError) as e:
        if retries < MAX_RETRIES:
            wait_time = SITEMAP_RETRY_DELAY * (2 ** retries)
            print(f"   ⏳ Timeout parsing sitemap: {type(e).__name__}: {e}, tentative {retries + 1}/{MAX_RETRIES} dans {wait_time}s...", flush=True)
            time.sleep(wait_time)
            return extract_sitemap_products(sitemap_url, retries + 1)
        return []
    except Exception as e:
        if retries < MAX_RETRIES:
            wait_time = SITEMAP_RETRY_DELAY * (2 ** retries)
            print(f"   ⏳ Erreur parsing sitemap: {type(e).__name__}: {e}, tentative {retries + 1}/{MAX_RETRIES} dans {wait_time}s...", flush=True)
            time.sleep(wait_time)
            return extract_sitemap_products(sitemap_url, retries + 1)
        return []


# ============= BUILDERS DE PRODUITS =============
def build_product(url, title='', images=None, price=0.0, description=''):
    """Construit un produit avec le format normalisé"""
    return {
        'url': url,
        'title': title.strip(),
        'images': images or [],
        'price': float(price),
        'description': description.strip()
    }

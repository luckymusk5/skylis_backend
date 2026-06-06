"""
Main scraper orchestrator
Exécute les fonctions de scraping de chaque fichier spécifique à chaque site EN PARALLÈLE
"""

import os
import importlib.util
import asyncio
from pathlib import Path


def load_scraper_module(filepath):
    """
    Charge dynamiquement un module Python à partir d'un fichier.
    """
    module_name = Path(filepath).stem
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def execute_scraper_async(scraper_file, index=0):
    """
    Exécute un scraper dans une coroutine pour exécution parallèle
    Ajoute un petit délai d'attente staggeré pour éviter les contentions de fichiers
    """
    try:
        # Délai staggeré: 0s, 1s, 2s, 3s pour éviter que tous les scrapers accèdent aux fichiers au même moment
        await asyncio.sleep(index * 1.0)
        
        module = load_scraper_module(str(scraper_file))
        
        # Cherche la fonction scrape() ou scraper()
        scrape_func = getattr(module, 'scrape', None) or getattr(module, 'scraper', None)
        
        if scrape_func:
            # Si c'est une coroutine (async), l'await
            result = scrape_func()
            if asyncio.iscoroutine(result):
                result = await result
            
            return {
                'status': 'success',
                'file': scraper_file.name,
                'result': result
            }
        else:
            return {
                'status': 'warning',
                'file': scraper_file.name,
                'message': f"Aucune fonction 'scrape()' ou 'scraper()' trouvée"
            }
            
    except Exception as e:
        return {
            'status': 'error',
            'file': scraper_file.name,
            'error': str(e)
        }


async def execute_all_scrapers_parallel():
    """
    Découvre et exécute toutes les fonctions de scraping EN PARALLÈLE
    Avec délais staggerés pour éviter les contentions de fichiers
    """
    scrape_dir = Path(__file__).parent
    scraper_files = sorted(scrape_dir.glob("*_scrape.py"))
    
    if not scraper_files:
        print("[WARN] Aucun fichier de scraping trouvé (*_scrape.py)")
        return
    
    print(f"[INFO] {len(scraper_files)} fichier(s) de scraping decouverts", flush=True)
    print(f"[INFO] Lancement parallele de tous les scrapers...\n", flush=True)
    
    # Exécute tous les scrapers en parallèle avec délais staggerés
    tasks = [execute_scraper_async(scraper_file, index) for index, scraper_file in enumerate(scraper_files)]
    results = await asyncio.gather(*tasks)
    
    # Affiche les resultats
    print(f"\n{'='*60}", flush=True)
    print("[SUMMARY] RESUME D'EXECUTION", flush=True)
    print(f"{'='*60}\n", flush=True)
    
    success_count = 0
    for result in results:
        if result['status'] == 'success':
            print(f"[OK] {result['file']}: Succes - {result['result']} produits scrapes", flush=True)
            success_count += 1
        elif result['status'] == 'warning':
            print(f"[WARN] {result['file']}: {result['message']}", flush=True)
        else:
            print(f"[ERROR] {result['file']}: Erreur - {result['error']}", flush=True)
    
    print(f"\n{'='*60}", flush=True)
    print(f"Total: {success_count}/{len(scraper_files)} scraper(s) reussi(s)", flush=True)
    print(f"{'='*60}\n", flush=True)


def execute_all_scrapers():
    """
    Wrapper synchrone pour lancer l'exécution parallèle
    """
    asyncio.run(execute_all_scrapers_parallel())


if __name__ == "__main__":
    execute_all_scrapers()

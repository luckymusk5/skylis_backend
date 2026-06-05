import os
import json
import time
import glob
import hashlib
import requests
from pathlib import Path
from dotenv import load_dotenv
import weaviate

# ── Chargement .env ──────────────────────────────────────────────────────────
load_dotenv()

JINA_API_KEY     = os.getenv("JINA_API_KEY")
WEAVIATE_URL     = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY", "")
DATA_PATH        = os.getenv("DATA_PATH", "./data")

# ── Config Jina CLIP v2 ───────────────────────────────────────────────────────
JINA_API_URL   = "https://api.jina.ai/v1/embeddings"
JINA_MODEL     = "jina-clip-v2"
JINA_DIM       = 1024
BATCH_SIZE     = 20
MAX_IMAGES     = 3
TIMEOUT_JINA   = 60
RETRIES        = 3

# ── Schéma Weaviate ───────────────────────────────────────────────────────────
CLASSE = "Produits"

SCHEMA = {
    "class": CLASSE,
    "description": "Produits e-commerce — vecteurs multimodaux jina-clip-v2",
    "vectorizer": "none",
    "properties": [
        {"name": "url",             "dataType": ["text"]},
        {"name": "title",           "dataType": ["text"]},
        {"name": "images",          "dataType": ["text[]"]},
        {"name": "price",           "dataType": ["number"]},
        {"name": "description",     "dataType": ["text"]},
        {"name": "embedding_mode",  "dataType": ["text"]},
        # ── Nouveau : hash du contenu pour détecter les changements ──────────
        # MD5 de (title + price + description) — si différent → le produit a changé
        {"name": "content_hash",    "dataType": ["text"]},
    ],
}


# ── Hash de contenu ───────────────────────────────────────────────────────────

def compute_content_hash(product: dict) -> str:
    """
    Calcule un hash MD5 du contenu significatif du produit.
    Utilisé pour détecter si un produit déjà indexé a été modifié.

    Champs pris en compte : title, price, description
    (l'URL est l'identifiant, les images sont plus volatiles)
    """
    content = "|".join([
        str(product.get("title", "")),
        str(product.get("price", "")),
        str(product.get("description", "")),
    ])
    return hashlib.md5(content.encode("utf-8")).hexdigest()


# ── Lookup Weaviate : chercher un produit par URL ─────────────────────────────

def find_existing_product(client: weaviate.Client, url: str) -> dict | None:
    """
    Cherche un produit dans Weaviate par son URL (identifiant unique).

    Retourne un dict avec les champs {id, content_hash} si trouvé, None sinon.
    L'id Weaviate est nécessaire pour faire un update (upsert).
    """
    try:
        result = (
            client.query
            .get(CLASSE, ["url", "content_hash"])
            .with_where({
                "path": ["url"],
                "operator": "Equal",
                "valueText": url,
            })
            .with_limit(1)
            .with_additional(["id"])   # récupère l'UUID interne Weaviate
            .do()
        )
        hits = result.get("data", {}).get("Get", {}).get(CLASSE, [])
        if hits:
            return {
                "id":           hits[0]["_additional"]["id"],
                "content_hash": hits[0].get("content_hash", ""),
            }
    except Exception as e:
        print(f"  ⚠️  Erreur lookup Weaviate pour {url} : {e}")
    return None


# ── Chargement données ────────────────────────────────────────────────────────

def load_all_products(data_path: str) -> list[dict]:
    """Charge tous les .json et .jsonl avec détection automatique d'encodage."""
    products = []
    for filepath in glob.glob(f"{data_path}/**/*.json*", recursive=True):
        # Essayer utf-8 puis latin-1 comme fallback
        for encoding in ["utf-8", "latin-1", "utf-8-sig"]:
            try:
                with open(filepath, "r", encoding=encoding) as f:
                    if filepath.endswith(".jsonl"):
                        for line in f:
                            line = line.strip()
                            if line:
                                products.append(json.loads(line))
                    else:
                        data = json.load(f)
                        if isinstance(data, list):
                            products.extend(data)
                        else:
                            products.append(data)
                print(f"✅ {filepath} chargé en {encoding}")
                break
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
    return products


# ── Construction des inputs Jina ──────────────────────────────────────────────

# ── Construction des inputs Jina ──────────────────────────────────────────────
def build_jina_inputs(product: dict) -> tuple[list[dict], str]:
    """Texte uniquement, validation stricte."""
    title       = str(product.get("title", "") or "").strip()
    description = str(product.get("description", "") or "").strip()
    price       = str(product.get("price", "") or "").strip()

    parts = [p for p in [title, description, price] if len(p) >= 2]

    if not parts:
        return [], "empty"

    text_combined = " | ".join(parts)
    if len(text_combined) > 8000:
        text_combined = text_combined[:8000]

    return [{"text": text_combined}], "text_only"


# ── Appel API Jina ────────────────────────────────────────────────────────────
def call_jina_api(inputs: list[dict], retries: int = RETRIES) -> list[list[float]] | None:
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {JINA_API_KEY}",
    }
    payload = {
        "model":         JINA_MODEL,
        "input":         inputs,
        "encoding_type": "float",
        "dimensions":    JINA_DIM,
    }

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                JINA_API_URL,
                headers=headers,
                json=payload,
                timeout=TIMEOUT_JINA,
            )

            # Logger le body exact pour diagnostiquer
            if response.status_code != 200:
                print(f"  ❌ Jina {response.status_code} : {response.text[:300]}")

            response.raise_for_status()
            data = response.json()
            vectors = [
                item["embedding"]
                for item in sorted(data["data"], key=lambda x: x["index"])
            ]
            return vectors

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            if status == 429:
                time.sleep(10 * attempt)
            elif status in (400, 422):
                print(f"  ❌ Requête invalide, abandon.")
                return None
            else:
                time.sleep(5 * attempt)

        except Exception as e:
            print(f"  ⚠️  Jina erreur inattendue, tentative {attempt}/{retries} : {e}")
            time.sleep(5 * attempt)

    return None

# ── Moyenne des vecteurs ──────────────────────────────────────────────────────

def average_vectors(vectors: list[list[float]]) -> list[float]:
    if len(vectors) == 1:
        return vectors[0]
    dim = len(vectors[0])
    avg = [0.0] * dim
    for vec in vectors:
        for i, v in enumerate(vec):
            avg[i] += v
    n = len(vectors)
    return [x / n for x in avg]


# ── Vectorisation d'un batch ──────────────────────────────────────────────────

def vectorize_batch(products: list[dict]) -> list[tuple[list[float], str]] | None:
    all_inputs     = []
    product_slices = []
    modes          = []

    for product in products:
        inputs, mode = build_jina_inputs(product)
        start = len(all_inputs)
        all_inputs.extend(inputs)
        product_slices.append((start, start + len(inputs)))
        modes.append(mode)

    if not all_inputs:
        return None

    print(f"    → {len(all_inputs)} inputs envoyés à Jina ({len(products)} produits)")

    all_vectors = call_jina_api(all_inputs)
    if all_vectors is None:
        return None

    results = []
    for (start, end), mode in zip(product_slices, modes):
        product_vectors = all_vectors[start:end]
        if not product_vectors:
            results.append((None, mode))
            continue
        fused_vector = average_vectors(product_vectors)
        results.append((fused_vector, mode))

    return results


# ── Weaviate : schéma ─────────────────────────────────────────────────────────

def ensure_class_exists(client: weaviate.Client):
    existing = [c["class"] for c in client.schema.get().get("classes", [])]
    if CLASSE in existing:
        print(f"✅ Classe '{CLASSE}' existe déjà.")
    else:
        client.schema.create_class(SCHEMA)
        print(f"✅ Classe '{CLASSE}' créée.")


# ── Weaviate : upsert intelligent ─────────────────────────────────────────────

def upsert_batch(
    client: weaviate.Client,
    products: list[dict],
    results: list[tuple],
) -> dict:
    """
    Insère ou met à jour chaque produit dans Weaviate selon son état :

      - Nouveau produit (URL absente)    → INSERT
      - Produit existant + hash changé  → UPDATE (upsert via delete + insert)
      - Produit existant + hash identique → SKIP (aucun appel Weaviate)

    Weaviate v3 ne supporte pas le vrai PATCH vectoriel,
    on simule l'upsert par delete + insert quand nécessaire.

    Retourne un dict de compteurs : inserted, updated, skipped, failed
    """
    counters = {"inserted": 0, "updated": 0, "skipped": 0, "failed": 0}

    for product, (vector, mode) in zip(products, results):
        if vector is None:
            print(f"    ⚠️  Vecteur manquant : {product.get('url', '?')}, ignoré.")
            counters["failed"] += 1
            continue

        url          = product.get("url", "")
        new_hash     = compute_content_hash(product)
        existing     = find_existing_product(client, url)

        props = {
            "url":            url,
            "title":          product.get("title", ""),
            "images":         product.get("images", []),
            "price":          float(product.get("price", 0)),
            "description":    product.get("description", ""),
            "embedding_mode": mode,
            "content_hash":   new_hash,   # ← stocké pour comparaison future
        }

        try:
            if existing is None:
                # ── Nouveau produit ───────────────────────────────────────────
                client.data_object.create(
                    data_object=props,
                    class_name=CLASSE,
                    vector=vector,
                )
                counters["inserted"] += 1

            elif existing["content_hash"] != new_hash:
                # ── Produit modifié → supprimer l'ancien + insérer le nouveau ─
                # (Weaviate v3 ne permet pas de mettre à jour le vecteur via PATCH)
                client.data_object.delete(
                    uuid=existing["id"],
                    class_name=CLASSE,
                )
                client.data_object.create(
                    data_object=props,
                    class_name=CLASSE,
                    vector=vector,
                )
                counters["updated"] += 1

            else:
                # ── Produit inchangé → rien à faire ──────────────────────────
                counters["skipped"] += 1

        except Exception as e:
            print(f"    ❌ Erreur Weaviate pour {url} : {e}")
            counters["failed"] += 1

    return counters


# ── Pipeline principal ────────────────────────────────────────────────────────

def main():
    if not JINA_API_KEY:
        raise ValueError(
            "JINA_API_KEY manquant dans le .env\n"
            "Obtenez une clé gratuite (1M tokens) sur https://jina.ai/embeddings/"
        )
    
    weaviate_client = weaviate.Client(url=WEAVIATE_URL) 
    ensure_class_exists(weaviate_client)

    all_products = load_all_products(DATA_PATH)
    print(f"📦 {len(all_products)} produits chargés depuis '{DATA_PATH}'")

    if not all_products:
        print("Aucun produit trouvé. Vérifiez DATA_PATH dans votre .env")
        return

    # ── Compteurs globaux ─────────────────────────────────────────────────────
    total = {"inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
    pending = all_products.copy()
    processed = 0

    while pending:
        batch_products = pending[:BATCH_SIZE]
        processed += len(batch_products)
        print(f"\n🔄 Batch {processed}/{len(all_products)} "
              f"({len(batch_products)} produits)...")

        # ── Filtrer les produits déjà à jour AVANT de les envoyer à Jina ─────
        # Évite de consommer des tokens Jina pour des produits inchangés
        to_vectorize  = []
        to_skip       = []

        for product in batch_products:
            new_hash = compute_content_hash(product)
            existing = find_existing_product(weaviate_client, product.get("url", ""))

            if existing and existing["content_hash"] == new_hash:
                # Produit identique → pas besoin de vectoriser
                to_skip.append(product)
            else:
                # Nouveau ou modifié → doit être vectorisé
                to_vectorize.append(product)

        total["skipped"] += len(to_skip)
        if to_skip:
            print(f"    ⏭️  {len(to_skip)} produits inchangés, ignorés (tokens économisés).")

        if to_vectorize:
            results = vectorize_batch(to_vectorize)

            if results is None:
                # Batch refusé → diviser
                mid = len(to_vectorize) // 2
                if mid == 0:
                    p = to_vectorize[0]
                    print(f"  ❌ Produit irrécupérable : {p.get('url', '?')}")
                    total["failed"] += 1
                    pending = pending[BATCH_SIZE:]
                    continue
                else:
                    print(f"  ⚠️  Batch refusé, division en {mid} + {len(to_vectorize) - mid}.")
                    pending = (
                        to_vectorize[:mid]
                        + to_vectorize[mid:]
                        + pending[BATCH_SIZE:]
                    )
                    continue

            # ── Upsert dans Weaviate ──────────────────────────────────────────
            try:
                counters = upsert_batch(weaviate_client, to_vectorize, results)
                for k, v in counters.items():
                    total[k] += v

                print(
                    f"  ✅ {counters['inserted']} insérés | "
                    f"{counters['updated']} mis à jour | "
                    f"{counters['skipped']} inchangés | "
                    f"{counters['failed']} échoués"
                )
            except Exception as e:
                print(f"  ❌ Erreur Weaviate batch : {e}")
                total["failed"] += len(to_vectorize)

        pending = pending[BATCH_SIZE:]
        time.sleep(0.5)

    # ── Résumé final ──────────────────────────────────────────────────────────
    print(f"""
╔══════════════════════════════════════════╗
║           RÉSUMÉ DE L'INDEXATION         ║
╠══════════════════════════════════════════╣
║  📦 Total produits   : {len(all_products):<18} ║
║  ✅ Insérés          : {total['inserted']:<18} ║
║  🔄 Mis à jour       : {total['updated']:<18} ║
║  ⏭️  Inchangés        : {total['skipped']:<18} ║
║  ❌ Échoués          : {total['failed']:<18} ║
╠══════════════════════════════════════════╣
║  🧠 Modèle : {JINA_MODEL:<29} ║
║  📐 Dims   : {JINA_DIM:<29} ║
╚══════════════════════════════════════════╝
""")


if __name__ == "__main__":
    main()
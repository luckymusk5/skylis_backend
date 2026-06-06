"""
recherche_vector.py — Moteur de recherche multimodal
Recherche textuelle et par image dans Weaviate + reranking Jina multimodal

Modes de démarrage :
    # Serveur Flask (défaut)
    python recherche_vector.py

    # CLI
    python recherche_vector.py cli text "smartphone samsung 128go"
    python recherche_vector.py cli image https://example.com/phone.jpg
    python recherche_vector.py cli image ./photo.jpg --text "téléphone noir"
"""

import os
import base64
import time
import tempfile
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv
import weaviate
from flask import Flask, request, jsonify

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────
JINA_API_KEY      = os.getenv("JINA_API_KEY")
WEAVIATE_URL      = os.getenv("WEAVIATE_URL", "http://localhost:8080")
FLASK_HOST        = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT        = int(os.getenv("FLASK_PORT", 5000))
FLASK_DEBUG       = os.getenv("FLASK_DEBUG", "false").lower() == "true"

JINA_EMBED_URL    = "https://api.jina.ai/v1/embeddings"
JINA_RERANK_URL   = "https://api.jina.ai/v1/rerank"
JINA_EMBED_MODEL  = "jina-clip-v2"
JINA_RERANK_MODEL = "jina-reranker-v2-base-multilingual"
JINA_DIM          = 1024

CLASSE        = "Produits"
TOP_K_FETCH   = 50
TOP_K_FINAL   = 10
WEIGHT_IMAGE  = 0.7
WEIGHT_TEXT   = 0.3


def _jina_headers() -> dict:
    if not JINA_API_KEY:
        raise ValueError("JINA_API_KEY manquant dans le .env")
    return {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {JINA_API_KEY}",
    }


# ── Embeddings ────────────────────────────────────────────────────────────────

def embed_text(query: str) -> list[float] | None:
    """Vectorise un texte avec jina-clip-v2 (1024 dims)."""
    payload = {
        "model":         JINA_EMBED_MODEL,
        "input":         [{"text": query}],
        "encoding_type": "float",
        "dimensions":    JINA_DIM,
    }
    try:
        r = requests.post(JINA_EMBED_URL, headers=_jina_headers(), json=payload, timeout=30)
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]
    except Exception as e:
        print(f"❌ embed_text : {e}")
        return None


def embed_image(image_input: str) -> list[float] | None:
    """
    Vectorise une image avec jina-clip-v2.
    image_input : URL publique OU chemin local (converti en base64).
    """
    path = Path(image_input)
    if path.exists():
        ext  = path.suffix.lstrip(".").lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png",  "webp": "image/webp"}.get(ext, "image/jpeg")
        b64  = base64.b64encode(path.read_bytes()).decode()
        input_obj = {"image": f"data:{mime};base64,{b64}"}
    else:
        input_obj = {"image": image_input}

    payload = {
        "model":         JINA_EMBED_MODEL,
        "input":         [input_obj],
        "encoding_type": "float",
        "dimensions":    JINA_DIM,
    }
    try:
        r = requests.post(JINA_EMBED_URL, headers=_jina_headers(), json=payload, timeout=60)
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]
    except Exception as e:
        print(f"❌ embed_image : {e}")
        return None


def embed_image_b64(b64_data: str, mime: str = "image/jpeg") -> list[float] | None:
    """Vectorise une image déjà encodée en base64 (pour les uploads Flask)."""
    input_obj = {"image": f"data:{mime};base64,{b64_data}"}
    payload = {
        "model":         JINA_EMBED_MODEL,
        "input":         [input_obj],
        "encoding_type": "float",
        "dimensions":    JINA_DIM,
    }
    try:
        r = requests.post(JINA_EMBED_URL, headers=_jina_headers(), json=payload, timeout=60)
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]
    except Exception as e:
        print(f"❌ embed_image_b64 : {e}")
        return None


def fuse_vectors(img_vec: list[float], txt_vec: list[float]) -> list[float]:
    """Moyenne pondérée : 70% image / 30% texte."""
    return [WEIGHT_IMAGE * iv + WEIGHT_TEXT * tv for iv, tv in zip(img_vec, txt_vec)]


# ── Reranking Jina ────────────────────────────────────────────────────────────

def rerank(query: str, candidates: list[dict], top_n: int = TOP_K_FINAL) -> list[dict]:
    """
    Reranking avec jina-reranker-v2-base-multilingual.
    Retourne les candidats triés par score de pertinence.
    Fallback : top_n premiers sans reranking si erreur.
    """
    if not candidates:
        return []

    passages = []
    for doc in candidates:
        parts = []
        if doc.get("title"):
            parts.append(doc["title"])
        if doc.get("description"):
            parts.append(doc["description"][:400])
        if doc.get("price"):
            parts.append(f"Prix : {int(doc['price'])} FCFA")
        passages.append(" | ".join(parts) or doc.get("url", ""))

    payload = {
        "model":     JINA_RERANK_MODEL,
        "query":     query,
        "documents": passages,
        "top_n":     top_n,
    }

    try:
        r = requests.post(JINA_RERANK_URL, headers=_jina_headers(), json=payload, timeout=30)
        r.raise_for_status()
        reranked = []
        for item in r.json()["results"]:
            doc = candidates[item["index"]].copy()
            doc["rerank_score"] = round(item["relevance_score"], 5)
            reranked.append(doc)
        return reranked
    except Exception as e:
        print(f"⚠️  Rerank échoué ({e}) — retour des résultats bruts.")
        for doc in candidates:
            doc["rerank_score"] = None
        return candidates[:top_n]


# ── Weaviate ──────────────────────────────────────────────────────────────────

def _get_client() -> weaviate.Client:
    return weaviate.Client(url=WEAVIATE_URL)


def _vector_search(vector: list[float], top_k: int = TOP_K_FETCH) -> list[dict]:
    """Recherche ANN par vecteur dans Weaviate."""
    try:
        result = (
            _get_client().query
            .get(CLASSE, ["url", "title", "images", "price", "description"])
            .with_near_vector({"vector": vector})
            .with_limit(top_k)
            .with_additional(["distance"])
            .do()
        )
        hits = result.get("data", {}).get("Get", {}).get(CLASSE, [])
        products = []
        for h in hits:
            p = {k: v for k, v in h.items() if k != "_additional"}
            p["distance"] = round(h.get("_additional", {}).get("distance", 0), 5)
            products.append(p)
        return products
    except Exception as e:
        print(f"❌ Weaviate vector_search : {e}")
        return []


# ── Fonctions de recherche ────────────────────────────────────────────────────

def search_by_text(query: str, top_k: int = TOP_K_FINAL) -> list[dict]:
    """
    Recherche textuelle :
      1. Embed texte → jina-clip-v2
      2. ANN Weaviate (TOP_K_FETCH candidats)
      3. Reranking jina-reranker-v2-base-multilingual
    """
    print(f"\n🔍 Recherche texte : « {query} »")
    t0 = time.time()

    vector = embed_text(query)
    if not vector:
        return []

    candidates = _vector_search(vector, TOP_K_FETCH)
    print(f"   ├─ Weaviate : {len(candidates)} candidats  ({time.time()-t0:.2f}s)")

    results = rerank(query, candidates, top_k)
    print(f"   └─ Rerank   : {len(results)} résultats   ({time.time()-t0:.2f}s total)")
    return results


def search_by_image(
    image_input: str,
    text_query: str | None = None,
    top_k: int = TOP_K_FINAL,
) -> list[dict]:
    """
    Recherche par image (URL ou fichier local) :
      1. Embed image → jina-clip-v2
      2. Fusion optionnelle avec vecteur texte (70/30)
      3. ANN Weaviate (TOP_K_FETCH candidats)
      4. Reranking jina-reranker-v2-base-multilingual
    """
    print(f"\n🖼️  Recherche image : {image_input}")
    t0 = time.time()

    img_vec = embed_image(image_input)
    if not img_vec:
        return []

    if text_query:
        txt_vec = embed_text(text_query)
        vector  = fuse_vectors(img_vec, txt_vec) if txt_vec else img_vec
        print(f"   ├─ Fusion {int(WEIGHT_IMAGE*100)}% image / {int(WEIGHT_TEXT*100)}% texte")
    else:
        vector = img_vec

    candidates = _vector_search(vector, TOP_K_FETCH)
    print(f"   ├─ Weaviate : {len(candidates)} candidats  ({time.time()-t0:.2f}s)")

    rerank_q = text_query or "produit visuellement similaire"
    results  = rerank(rerank_q, candidates, top_k)
    print(f"   └─ Rerank   : {len(results)} résultats   ({time.time()-t0:.2f}s total)")
    return results


def search_by_image_b64(
    b64_data: str,
    mime: str = "image/jpeg",
    text_query: str | None = None,
    top_k: int = TOP_K_FINAL,
) -> list[dict]:
    """Recherche par image base64 (upload navigateur)."""
    t0 = time.time()
    print(f"\n🖼️  Recherche image (base64, mime={mime})")

    img_vec = embed_image_b64(b64_data, mime)
    if not img_vec:
        return []

    if text_query:
        txt_vec = embed_text(text_query)
        vector  = fuse_vectors(img_vec, txt_vec) if txt_vec else img_vec
    else:
        vector = img_vec

    candidates = _vector_search(vector, TOP_K_FETCH)
    print(f"   ├─ Weaviate : {len(candidates)} candidats  ({time.time()-t0:.2f}s)")

    rerank_q = text_query or "produit visuellement similaire"
    results  = rerank(rerank_q, candidates, top_k)
    print(f"   └─ Rerank   : {len(results)} résultats   ({time.time()-t0:.2f}s total)")
    return results


# ── Flask ─────────────────────────────────────────────────────────────────────

app = Flask(__name__)


@app.get("/health")
def health():
    """Healthcheck — vérifie que Flask et Weaviate sont joignables."""
    try:
        _get_client().is_ready()
        weaviate_ok = True
    except Exception:
        weaviate_ok = False
    return jsonify({"status": "ok", "weaviate": weaviate_ok})


@app.post("/search/text")
def route_search_text():
    """
    Recherche textuelle.

    Body JSON :
        { "query": "samsung galaxy", "top_k": 10 }

    Réponse :
        { "query": "...", "count": N, "results": [...] }
    """
    body = request.get_json(silent=True) or {}
    query = body.get("query", "").strip()
    top_k = int(body.get("top_k", TOP_K_FINAL))

    if not query:
        return jsonify({"error": "Paramètre 'query' manquant"}), 400

    results = search_by_text(query, top_k=top_k)
    return jsonify({"query": query, "count": len(results), "results": results})


@app.post("/search/image/url")
def route_search_image_url():
    """
    Recherche par URL d'image.

    Body JSON :
        { "image_url": "https://...", "text": "optionnel", "top_k": 10 }
    """
    body      = request.get_json(silent=True) or {}
    image_url = body.get("image_url", "").strip()
    text      = body.get("text", "").strip() or None
    top_k     = int(body.get("top_k", TOP_K_FINAL))

    if not image_url:
        return jsonify({"error": "Paramètre 'image_url' manquant"}), 400

    results = search_by_image(image_url, text_query=text, top_k=top_k)
    return jsonify({"image_url": image_url, "text": text, "count": len(results), "results": results})


@app.post("/search/image/upload")
def route_search_image_upload():
    """
    Recherche par image uploadée (multipart/form-data).

    Form fields :
        file  : fichier image (jpg, png, webp)
        text  : texte optionnel pour affiner (optionnel)
        top_k : nombre de résultats (optionnel, défaut 10)
    """
    if "file" not in request.files:
        return jsonify({"error": "Champ 'file' manquant"}), 400

    file  = request.files["file"]
    text  = request.form.get("text", "").strip() or None
    top_k = int(request.form.get("top_k", TOP_K_FINAL))

    raw  = file.read()
    ext  = Path(file.filename or "image.jpg").suffix.lstrip(".").lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png",  "webp": "image/webp"}.get(ext, "image/jpeg")
    b64  = base64.b64encode(raw).decode()

    results = search_by_image_b64(b64, mime=mime, text_query=text, top_k=top_k)
    return jsonify({
        "filename": file.filename,
        "text":     text,
        "count":    len(results),
        "results":  results,
    })


# ── Affichage terminal (CLI) ──────────────────────────────────────────────────

def print_results(results: list[dict]) -> None:
    if not results:
        print("   Aucun résultat.\n")
        return
    sep = "─" * 68
    print(sep)
    for i, r in enumerate(results, 1):
        rs = f"rerank={r['rerank_score']:.4f}" if r.get("rerank_score") is not None else "rerank=N/A"
        ds = f"dist={r.get('distance', '?')}"
        print(f" #{i:<2}  {rs}  {ds}")
        print(f"       Titre  : {r.get('title') or 'N/A'}")
        print(f"       Prix   : {int(r.get('price') or 0):,} FCFA")
        print(f"       URL    : {r.get('url') or 'N/A'}")
        desc = (r.get("description") or "")[:120]
        if desc:
            suffix = "..." if len(r.get("description", "")) > 120 else ""
            print(f"       Desc   : {desc}{suffix}")
        imgs = r.get("images") or []
        if imgs:
            print(f"       Image  : {imgs[0]}")
        print()
    print(sep)


# ── Point d'entrée ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Moteur de recherche multimodal — Weaviate + Jina",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes :
  # Serveur Flask (défaut)
  python recherche_vector.py

  # CLI
  python recherche_vector.py cli text "samsung galaxy 128go"
  python recherche_vector.py cli text "casque bluetooth" --top-k 5
  python recherche_vector.py cli image https://example.com/phone.jpg
  python recherche_vector.py cli image ./photo.jpg --text "téléphone noir"
        """
    )

    sub = parser.add_subparsers(dest="mode")

    # ── Sous-commande CLI ─────────────────────────────────────────────────────
    p_cli = sub.add_parser("cli", help="Mode ligne de commande")
    cli_sub = p_cli.add_subparsers(dest="search_mode", required=True)

    p_text = cli_sub.add_parser("text")
    p_text.add_argument("query")
    p_text.add_argument("--top-k", "-n", type=int, default=TOP_K_FINAL)

    p_img = cli_sub.add_parser("image")
    p_img.add_argument("image")
    p_img.add_argument("--text", "-t", default=None)
    p_img.add_argument("--top-k", "-n", type=int, default=TOP_K_FINAL)

    args = parser.parse_args()

    if args.mode == "cli":
        if args.search_mode == "text":
            print_results(search_by_text(args.query, top_k=args.top_k))
        elif args.search_mode == "image":
            print_results(search_by_image(args.image, text_query=args.text, top_k=args.top_k))
    else:
        # ── Mode serveur Flask (défaut) ───────────────────────────────────────
        print(f"🚀 Serveur Flask démarré sur http://{FLASK_HOST}:{FLASK_PORT}")
        print(f"   Routes disponibles :")
        print(f"   GET  /health")
        print(f"   POST /search/text")
        print(f"   POST /search/image/url")
        print(f"   POST /search/image/upload")
        app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
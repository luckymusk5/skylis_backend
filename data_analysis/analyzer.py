"""
analyzer.py — Logique d'analyse des données de recherche.

Lit depuis  : recherche_db (historique des requêtes clients)
Écrit dans  : analyse_db   (rapports, tendances, produits populaires)
"""

import json
import logging
from datetime import date, timedelta
from collections import Counter

from db import get_analyse_conn, get_recherche_conn
from models import (
    RapportQuotidien, TendanceKeyword,
    ProduitPopulaire, SnapshotAnalyse,
)

log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────

def _periode_dates(periode: str) -> tuple[date, date]:
    """Retourne (date_debut, date_fin) selon la période demandée."""
    today = date.today()
    if periode == "jour":
        return today, today
    if periode == "semaine":
        return today - timedelta(days=6), today
    if periode == "mois":
        return today.replace(day=1), today
    raise ValueError(f"Période inconnue : {periode!r}. Valeurs : jour | semaine | mois")


def _tokenize(query: str) -> list[str]:
    """Découpe une requête en mots-clés significatifs (> 2 chars)."""
    stopwords = {
        "le", "la", "les", "de", "du", "des", "un", "une",
        "et", "en", "au", "aux", "pour", "avec", "sur",
        "the", "and", "for", "with",
    }
    tokens = [w.lower().strip(".,;:!?\"'") for w in query.split()]
    return [t for t in tokens if len(t) > 2 and t not in stopwords]


# ── Lecture depuis recherche_db ────────────────────────────────────────────

def _fetch_requetes(date_debut: date, date_fin: date) -> list[dict]:
    """
    Récupère les requêtes effectuées par les clients sur la période.
    Attend une table `search_log` dans recherche_db avec au minimum :
        id, query TEXT, results JSONB, nb_results INT,
        client_ip TEXT, searched_at TIMESTAMPTZ
    """
    sql = """
        SELECT
            id,
            query,
            results,
            nb_results,
            client_ip,
            searched_at
        FROM search_log
        WHERE searched_at::date BETWEEN %s AND %s
        ORDER BY searched_at
    """
    try:
        conn = get_recherche_conn()
        with conn.cursor() as cur:
            cur.execute(sql, (date_debut, date_fin))
            rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        log.warning("⚠️ Impossible de lire recherche_db : %s", e)
        return []


# ── Calculs d'analyse ──────────────────────────────────────────────────────

def _compute_rapport(requetes: list[dict], cible: date) -> RapportQuotidien:
    """Calcule le rapport quotidien pour une date donnée."""
    jour = [r for r in requetes if r["searched_at"].date() == cible]
    nb   = len(jour)
    ips  = {r["client_ip"] for r in jour if r.get("client_ip")}

    counter = Counter()
    for r in jour:
        counter[r["query"]] += 1

    top3 = [q for q, _ in counter.most_common(3)]
    sans = sum(1 for r in jour if r.get("nb_results", 1) == 0)

    return RapportQuotidien(
        date_rapport    = cible,
        nb_requetes     = nb,
        nb_utilisateurs = len(ips),
        requete_top1    = top3[0] if len(top3) > 0 else None,
        requete_top2    = top3[1] if len(top3) > 1 else None,
        requete_top3    = top3[2] if len(top3) > 2 else None,
        taux_sans_result= round(sans / nb * 100, 2) if nb else 0.0,
    )


def _compute_keywords(requetes: list[dict]) -> list[TendanceKeyword]:
    """Agrège les mots-clés par jour."""
    par_jour: dict[date, Counter] = {}
    for r in requetes:
        jour = r["searched_at"].date()
        par_jour.setdefault(jour, Counter())
        for token in _tokenize(r["query"]):
            par_jour[jour][token] += 1

    result = []
    for jour, counter in par_jour.items():
        for kw, nb in counter.items():
            result.append(TendanceKeyword(date_jour=jour, keyword=kw, nb_fois=nb))
    return result


def _compute_produits(requetes: list[dict]) -> list[ProduitPopulaire]:
    """Extrait les produits les plus retournés dans les résultats."""
    par_jour: dict[date, dict[str, list[float]]] = {}

    for r in requetes:
        jour = r["searched_at"].date()
        results = r.get("results") or []
        if isinstance(results, str):
            try:
                results = json.loads(results)
            except Exception:
                continue

        par_jour.setdefault(jour, {})
        for item in results:
            url   = item.get("url", "")
            score = float(item.get("score", 0.0))
            if not url:
                continue
            par_jour[jour].setdefault(url, [])
            par_jour[jour][url].append(score)

    result = []
    for jour, produits in par_jour.items():
        for url, scores in produits.items():
            result.append(ProduitPopulaire(
                date_jour      = jour,
                product_url    = url,
                nb_apparitions = len(scores),
                score_moyen    = round(sum(scores) / len(scores), 4),
            ))
    return result


# ── Écriture dans analyse_db ───────────────────────────────────────────────

def _upsert_rapport(rapport: RapportQuotidien):
    sql = """
        INSERT INTO rapport_quotidien
            (date_rapport, nb_requetes, nb_utilisateurs,
             requete_top1, requete_top2, requete_top3, taux_sans_result)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (date_rapport) DO UPDATE SET
            nb_requetes      = EXCLUDED.nb_requetes,
            nb_utilisateurs  = EXCLUDED.nb_utilisateurs,
            requete_top1     = EXCLUDED.requete_top1,
            requete_top2     = EXCLUDED.requete_top2,
            requete_top3     = EXCLUDED.requete_top3,
            taux_sans_result = EXCLUDED.taux_sans_result
    """
    conn = get_analyse_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                rapport.date_rapport, rapport.nb_requetes,
                rapport.nb_utilisateurs, rapport.requete_top1,
                rapport.requete_top2, rapport.requete_top3,
                rapport.taux_sans_result,
            ))
    conn.close()


def _upsert_keywords(keywords: list[TendanceKeyword]):
    sql = """
        INSERT INTO tendance_keywords (date_jour, keyword, nb_fois)
        VALUES (%s,%s,%s)
        ON CONFLICT (date_jour, keyword) DO UPDATE SET
            nb_fois = EXCLUDED.nb_fois
    """
    conn = get_analyse_conn()
    with conn:
        with conn.cursor() as cur:
            cur.executemany(sql, [(k.date_jour, k.keyword, k.nb_fois) for k in keywords])
    conn.close()


def _upsert_produits(produits: list[ProduitPopulaire]):
    sql = """
        INSERT INTO produits_populaires
            (date_jour, product_url, product_title, nb_apparitions, score_moyen)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (date_jour, product_url) DO UPDATE SET
            nb_apparitions = EXCLUDED.nb_apparitions,
            score_moyen    = EXCLUDED.score_moyen
    """
    conn = get_analyse_conn()
    with conn:
        with conn.cursor() as cur:
            cur.executemany(sql, [
                (p.date_jour, p.product_url, p.product_title,
                 p.nb_apparitions, p.score_moyen)
                for p in produits
            ])
    conn.close()


def _save_snapshot(snap: SnapshotAnalyse):
    sql = """
        INSERT INTO snapshot_analyse (type, periode, date_debut, date_fin, payload)
        VALUES (%s,%s,%s,%s,%s::jsonb)
    """
    conn = get_analyse_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                snap.type, snap.periode,
                snap.date_debut, snap.date_fin,
                json.dumps(snap.payload),
            ))
    conn.close()


# ── API publique de l'analyzer ─────────────────────────────────────────────

def run_analyse(periode: str = "jour") -> dict:
    """
    Lance l'analyse complète pour la période donnée.
    Retourne un résumé JSON.
    """
    date_debut, date_fin = _periode_dates(periode)
    log.info("📊 Analyse %s  du %s au %s", periode, date_debut, date_fin)

    requetes = _fetch_requetes(date_debut, date_fin)
    log.info("   %d requêtes lues depuis recherche_db", len(requetes))

    # ── Rapport quotidien (seulement pour 'jour') ──
    rapport = None
    if periode == "jour":
        rapport = _compute_rapport(requetes, date_fin)
        _upsert_rapport(rapport)
        log.info("   ✅ rapport_quotidien mis à jour")

    # ── Tendances keywords ──
    keywords = _compute_keywords(requetes)
    if keywords:
        _upsert_keywords(keywords)
        log.info("   ✅ %d tendances keywords mises à jour", len(keywords))

    # ── Produits populaires ──
    produits = _compute_produits(requetes)
    if produits:
        _upsert_produits(produits)
        log.info("   ✅ %d produits populaires mis à jour", len(produits))

    # ── Snapshot ──
    payload = {
        "nb_requetes":  len(requetes),
        "nb_keywords":  len(keywords),
        "nb_produits":  len(produits),
        "rapport":      rapport.to_dict() if rapport else None,
        "top_keywords": [k.to_dict() for k in sorted(keywords, key=lambda x: -x.nb_fois)[:20]],
        "top_produits": [p.to_dict() for p in sorted(produits, key=lambda x: -x.nb_apparitions)[:20]],
    }
    snap = SnapshotAnalyse(
        type="global", periode=periode,
        date_debut=date_debut, date_fin=date_fin,
        payload=payload,
    )
    _save_snapshot(snap)

    log.info("   ✅ snapshot sauvegardé")
    return payload


def get_rapport_quotidien(target_date: date) -> dict | None:
    """Récupère le rapport quotidien d'une date depuis analyse_db."""
    sql = "SELECT * FROM rapport_quotidien WHERE date_rapport = %s"
    conn = get_analyse_conn()
    with conn.cursor() as cur:
        cur.execute(sql, (target_date,))
        row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_top_keywords(periode: str = "semaine", limit: int = 20) -> list[dict]:
    """Retourne les mots-clés les plus recherchés sur la période."""
    date_debut, date_fin = _periode_dates(periode)
    sql = """
        SELECT keyword, SUM(nb_fois) AS total
        FROM tendance_keywords
        WHERE date_jour BETWEEN %s AND %s
        GROUP BY keyword
        ORDER BY total DESC
        LIMIT %s
    """
    conn = get_analyse_conn()
    with conn.cursor() as cur:
        cur.execute(sql, (date_debut, date_fin, limit))
        rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_top_produits(periode: str = "semaine", limit: int = 20) -> list[dict]:
    """Retourne les produits les plus populaires sur la période."""
    date_debut, date_fin = _periode_dates(periode)
    sql = """
        SELECT product_url, product_title,
               SUM(nb_apparitions) AS total_apparitions,
               AVG(score_moyen)    AS score_moyen
        FROM produits_populaires
        WHERE date_jour BETWEEN %s AND %s
        GROUP BY product_url, product_title
        ORDER BY total_apparitions DESC
        LIMIT %s
    """
    conn = get_analyse_conn()
    with conn.cursor() as cur:
        cur.execute(sql, (date_debut, date_fin, limit))
        rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_snapshots(type_: str = "global", periode: str = "jour", limit: int = 10) -> list[dict]:
    """Retourne les derniers snapshots d'analyse."""
    sql = """
        SELECT id, type, periode, date_debut, date_fin, payload, created_at
        FROM snapshot_analyse
        WHERE type = %s AND periode = %s
        ORDER BY created_at DESC
        LIMIT %s
    """
    conn = get_analyse_conn()
    with conn.cursor() as cur:
        cur.execute(sql, (type_, periode, limit))
        rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

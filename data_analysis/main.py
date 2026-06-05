"""
main.py — Serveur Flask du service data_analysis
Port : 5001

Routes disponibles :
  GET  /health                          → statut du service
  POST /analyse/run                     → lance une analyse
  GET  /analyse/rapport?date=YYYY-MM-DD → rapport quotidien
  GET  /analyse/keywords?periode=semaine&limit=20
  GET  /analyse/produits?periode=semaine&limit=20
  GET  /analyse/snapshots?type=global&periode=jour&limit=10
"""

import os
import logging
from datetime import date, datetime

from flask import Flask, jsonify, request
from dotenv import load_dotenv

from db import init_db
from analyzer import (
    run_analyse,
    get_rapport_quotidien,
    get_top_keywords,
    get_top_produits,
    get_snapshots,
)

# ── Config ─────────────────────────────────────────────────────────────────

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

app = Flask(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────

def _ok(data, status: int = 200):
    return jsonify({"status": "ok", "data": data}), status


def _err(msg: str, status: int = 400):
    return jsonify({"status": "error", "message": msg}), status


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return _ok({"service": "data_analysis", "timestamp": datetime.utcnow().isoformat()})


@app.post("/analyse/run")
def analyse_run():
    """
    Lance une analyse complète.
    Body JSON (optionnel) : {"periode": "jour" | "semaine" | "mois"}
    """
    body    = request.get_json(silent=True) or {}
    periode = body.get("periode", "jour")

    if periode not in ("jour", "semaine", "mois"):
        return _err("periode invalide — valeurs : jour | semaine | mois")

    try:
        result = run_analyse(periode)
        return _ok(result)
    except Exception as e:
        log.exception("Erreur run_analyse")
        return _err(str(e), 500)


@app.get("/analyse/rapport")
def analyse_rapport():
    """
    Rapport quotidien.
    Query param : date=YYYY-MM-DD  (défaut : aujourd'hui)
    """
    raw  = request.args.get("date")
    cible = _parse_date(raw) or date.today()

    try:
        rapport = get_rapport_quotidien(cible)
        if rapport is None:
            return _err(f"Aucun rapport pour {cible}", 404)
        # Sérialise les dates/decimals
        rapport = {
            k: (v.isoformat() if isinstance(v, date) else float(v) if hasattr(v, "__float__") else v)
            for k, v in rapport.items()
        }
        return _ok(rapport)
    except Exception as e:
        log.exception("Erreur get_rapport_quotidien")
        return _err(str(e), 500)


@app.get("/analyse/keywords")
def analyse_keywords():
    """
    Top mots-clés recherchés.
    Query params :
      periode = jour | semaine | mois  (défaut : semaine)
      limit   = int                    (défaut : 20)
    """
    periode = request.args.get("periode", "semaine")
    limit   = int(request.args.get("limit", 20))

    if periode not in ("jour", "semaine", "mois"):
        return _err("periode invalide — valeurs : jour | semaine | mois")

    try:
        data = get_top_keywords(periode, limit)
        return _ok({"periode": periode, "keywords": data})
    except Exception as e:
        log.exception("Erreur get_top_keywords")
        return _err(str(e), 500)


@app.get("/analyse/produits")
def analyse_produits():
    """
    Top produits populaires.
    Query params :
      periode = jour | semaine | mois  (défaut : semaine)
      limit   = int                    (défaut : 20)
    """
    periode = request.args.get("periode", "semaine")
    limit   = int(request.args.get("limit", 20))

    if periode not in ("jour", "semaine", "mois"):
        return _err("periode invalide — valeurs : jour | semaine | mois")

    try:
        data = get_top_produits(periode, limit)
        # Convertit Decimal → float
        clean = [
            {k: float(v) if hasattr(v, "__float__") and not isinstance(v, int) else v
             for k, v in row.items()}
            for row in data
        ]
        return _ok({"periode": periode, "produits": clean})
    except Exception as e:
        log.exception("Erreur get_top_produits")
        return _err(str(e), 500)


@app.get("/analyse/snapshots")
def analyse_snapshots():
    """
    Derniers snapshots d'analyse.
    Query params :
      type    = global            (défaut : global)
      periode = jour | semaine | mois (défaut : jour)
      limit   = int               (défaut : 10)
    """
    type_   = request.args.get("type",    "global")
    periode = request.args.get("periode", "jour")
    limit   = int(request.args.get("limit", 10))

    try:
        snaps = get_snapshots(type_, periode, limit)
        # Sérialise les dates
        for s in snaps:
            for k in ("date_debut", "date_fin", "created_at"):
                if k in s and hasattr(s[k], "isoformat"):
                    s[k] = s[k].isoformat()
        return _ok(snaps)
    except Exception as e:
        log.exception("Erreur get_snapshots")
        return _err(str(e), 500)


# ── Démarrage ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("🚀 Démarrage data_analysis...")

    # Initialise le schéma PostgreSQL
    init_db()

    host  = os.getenv("FLASK_HOST",  "0.0.0.0")
    port  = int(os.getenv("FLASK_PORT", 5001))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    log.info("🌐 Flask écoute sur %s:%s", host, port)
    app.run(host=host, port=port, debug=debug)

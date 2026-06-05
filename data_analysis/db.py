"""
db.py — Connexions PostgreSQL et initialisation des tables
- analyse_db  : résultats d'analyse (écriture)
- recherche_db: historique des requêtes clients (lecture seule)
"""

import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)


# ── Paramètres de connexion ────────────────────────────────────────────────

ANALYSE_DSN = {
    "host":     os.getenv("ANALYSE_DB_HOST",     "analyse_db"),
    "port":     int(os.getenv("ANALYSE_DB_PORT", 5432)),
    "dbname":   os.getenv("ANALYSE_DB_NAME",     "analyse_db"),
    "user":     os.getenv("ANALYSE_DB_USER",     "analyse_user"),
    "password": os.getenv("ANALYSE_DB_PASSWORD", "analyse_pass"),
}

RECHERCHE_DSN = {
    "host":     os.getenv("RECHERCHE_DB_HOST",     "recherche_db"),
    "port":     int(os.getenv("RECHERCHE_DB_PORT", 5432)),
    "dbname":   os.getenv("RECHERCHE_DB_NAME",     "recherche_db"),
    "user":     os.getenv("RECHERCHE_DB_USER",     "recherche_user"),
    "password": os.getenv("RECHERCHE_DB_PASSWORD", "recherche_pass"),
}


# ── Helpers de connexion ───────────────────────────────────────────────────

def get_analyse_conn():
    """Retourne une connexion à analyse_db (lecture + écriture)."""
    return psycopg2.connect(**ANALYSE_DSN, cursor_factory=RealDictCursor)


def get_recherche_conn():
    """Retourne une connexion à recherche_db (lecture seule)."""
    conn = psycopg2.connect(**RECHERCHE_DSN, cursor_factory=RealDictCursor)
    conn.set_session(readonly=True)
    return conn


# ── Initialisation du schéma de analyse_db ────────────────────────────────

SCHEMA_SQL = """

-- Rapport quotidien global
CREATE TABLE IF NOT EXISTS rapport_quotidien (
    id              SERIAL PRIMARY KEY,
    date_rapport    DATE        NOT NULL UNIQUE,
    nb_requetes     INTEGER     DEFAULT 0,
    nb_utilisateurs INTEGER     DEFAULT 0,
    requete_top1    TEXT,
    requete_top2    TEXT,
    requete_top3    TEXT,
    taux_sans_result NUMERIC(5,2) DEFAULT 0,   -- % requêtes sans résultat
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Tendances par mot-clé (agrégation journalière)
CREATE TABLE IF NOT EXISTS tendance_keywords (
    id          SERIAL PRIMARY KEY,
    date_jour   DATE    NOT NULL,
    keyword     TEXT    NOT NULL,
    nb_fois     INTEGER DEFAULT 1,
    UNIQUE (date_jour, keyword)
);

-- Produits les plus cliqués/retournés dans les recherches
CREATE TABLE IF NOT EXISTS produits_populaires (
    id              SERIAL PRIMARY KEY,
    date_jour       DATE    NOT NULL,
    product_url     TEXT    NOT NULL,
    product_title   TEXT,
    nb_apparitions  INTEGER DEFAULT 1,
    score_moyen     NUMERIC(6,4),
    UNIQUE (date_jour, product_url)
);

-- Snapshots d'analyse à la demande (conservés pour historique)
CREATE TABLE IF NOT EXISTS snapshot_analyse (
    id          SERIAL PRIMARY KEY,
    type        TEXT        NOT NULL,   -- 'keywords' | 'produits' | 'global'
    periode     TEXT        NOT NULL,   -- 'jour' | 'semaine' | 'mois'
    date_debut  DATE        NOT NULL,
    date_fin    DATE        NOT NULL,
    payload     JSONB       NOT NULL,   -- résultat brut JSON
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Index utiles
CREATE INDEX IF NOT EXISTS idx_tendance_date    ON tendance_keywords   (date_jour DESC);
CREATE INDEX IF NOT EXISTS idx_tendance_keyword ON tendance_keywords   (keyword);
CREATE INDEX IF NOT EXISTS idx_produits_date    ON produits_populaires (date_jour DESC);
CREATE INDEX IF NOT EXISTS idx_snapshot_type    ON snapshot_analyse    (type, periode);
"""


def init_db():
    """Crée les tables dans analyse_db si elles n'existent pas."""
    try:
        conn = get_analyse_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_SQL)
        conn.close()
        log.info("✅ analyse_db — schéma initialisé")
    except Exception as e:
        log.error("❌ Erreur init analyse_db : %s", e)
        raise

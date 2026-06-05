"""
models.py — Structures de données utilisées dans data_analysis.
Pas d'ORM lourd : simples dataclasses pour la sérialisation JSON.
"""

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Optional


@dataclass
class RapportQuotidien:
    date_rapport:       date
    nb_requetes:        int         = 0
    nb_utilisateurs:    int         = 0
    requete_top1:       Optional[str] = None
    requete_top2:       Optional[str] = None
    requete_top3:       Optional[str] = None
    taux_sans_result:   float       = 0.0

    def to_dict(self):
        d = asdict(self)
        d["date_rapport"] = self.date_rapport.isoformat()
        return d


@dataclass
class TendanceKeyword:
    date_jour:  date
    keyword:    str
    nb_fois:    int = 1

    def to_dict(self):
        d = asdict(self)
        d["date_jour"] = self.date_jour.isoformat()
        return d


@dataclass
class ProduitPopulaire:
    date_jour:      date
    product_url:    str
    product_title:  Optional[str] = None
    nb_apparitions: int           = 1
    score_moyen:    float         = 0.0

    def to_dict(self):
        d = asdict(self)
        d["date_jour"] = self.date_jour.isoformat()
        return d


@dataclass
class SnapshotAnalyse:
    type:       str         # 'keywords' | 'produits' | 'global'
    periode:    str         # 'jour' | 'semaine' | 'mois'
    date_debut: date
    date_fin:   date
    payload:    dict        = field(default_factory=dict)

    def to_dict(self):
        d = asdict(self)
        d["date_debut"] = self.date_debut.isoformat()
        d["date_fin"]   = self.date_fin.isoformat()
        return d

"""
Step 3 — Crop recommendation engine + Explainable AI (XAI).

Engine: multi-criteria scoring (weighted additive utility), transparan & auditable.
Bukan black-box — ini definisi XAI yang sesungguhnya untuk DSS petani.

Per komoditas, dihitung skor parsial untuk:
  1. Kesesuaian pH         (gaussian membership terhadap rentang optimal)
  2. Defisit Nitrogen      (semakin kecil defisit, semakin baik)
  3. Defisit Fosfor        (idem)
  4. Defisit Kalium        (idem)
  5. Kesesuaian kelembapan (hard threshold)
  6. Kesesuaian suhu       (rentang trapezoid)
  7. Salinitas (EC)        (penalti jika EC > batas)

Output:
  - Rekomendasi rangking komoditas per plot (mean kondisi)
  - Penjelasan: kontribusi tiap faktor + bahasa natural untuk petani
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

import config as C


HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DS = os.path.join(HERE, "output", "datasets")
OUT_REPORTS = os.path.join(HERE, "output", "reports")
OUT_TABLES = os.path.join(HERE, "output", "tables")
os.makedirs(OUT_TABLES, exist_ok=True)


# Bobot kontribusi tiap faktor (jumlah = 1.0)
WEIGHTS = {
    "pH":  0.25,
    "N":   0.15,
    "P":   0.15,
    "K":   0.15,
    "hum": 0.10,
    "temp":0.10,
    "EC":  0.10,
}


def score_ph(value: float, opt_range, tol_range) -> float:
    """1.0 di rentang optimal, turun linear ke 0 di tepi rentang tolerable."""
    lo_opt, hi_opt = opt_range
    lo_tol, hi_tol = tol_range
    if lo_opt <= value <= hi_opt:
        return 1.0
    if value < lo_tol or value > hi_tol:
        return 0.0
    if value < lo_opt:
        return (value - lo_tol) / (lo_opt - lo_tol)
    return (hi_tol - value) / (hi_tol - hi_opt)


def score_deficit(current: float, target: float) -> float:
    """Skor [0..1]: 1.0 jika current >= target; turun linear bila defisit.
    Surplus besar (>3x target) sedikit dipenalti — "luxury consumption" tidak ideal.
    """
    if target <= 0:
        return 1.0
    ratio = current / target
    if ratio >= 1.0:
        if ratio > 3.0:
            return max(0.6, 1.0 - (ratio - 3.0) * 0.1)
        return 1.0
    return max(0.0, ratio)


def score_hum(value: float, min_hum: float) -> float:
    if value >= min_hum:
        return 1.0
    return max(0.0, value / min_hum)


def score_temp(value: float, temp_range) -> float:
    lo, hi = temp_range
    if lo <= value <= hi:
        return 1.0
    # 2 derajat di luar rentang -> 0
    if value < lo:
        return max(0.0, 1.0 - (lo - value) / 2.0)
    return max(0.0, 1.0 - (value - hi) / 2.0)


def score_ec(value: float, ec_max: float) -> float:
    if value <= ec_max:
        return 1.0
    # Penalti linear: di 1.5x ec_max -> skor 0
    return max(0.0, 1.0 - (value - ec_max) / (0.5 * ec_max))


@dataclass
class CropScore:
    crop: str
    total: float
    factors: dict   # {param: (raw_score, weighted)}
    notes: list     # bullet narrative untuk petani

    def as_dict(self):
        return asdict(self)


def evaluate_crop(crop: str, soil: dict) -> CropScore:
    spec = C.CROP_DB[crop]
    f = {}
    f["pH"]  = score_ph(soil["pH"], spec["ph_optimal"], spec["ph_tolerable"])
    f["N"]   = score_deficit(soil["N"], spec["N_target"])
    f["P"]   = score_deficit(soil["P"], spec["P_target"])
    f["K"]   = score_deficit(soil["K"], spec["K_target"])
    f["hum"] = score_hum(soil["hum"], spec["hum_min"])
    f["temp"]= score_temp(soil["temp"], spec["temp_range"])
    f["EC"]  = score_ec(soil["EC"], spec["ec_max"])

    factors = {k: (round(v, 3), round(v * WEIGHTS[k], 3)) for k, v in f.items()}
    total = sum(v * WEIGHTS[k] for k, v in f.items())

    # Bahasa natural — XAI layer
    notes = []
    if f["pH"] >= 0.9:
        notes.append(f"pH lahan ({soil['pH']:.2f}) berada dalam rentang optimal "
                     f"({spec['ph_optimal'][0]}–{spec['ph_optimal'][1]}).")
    elif f["pH"] >= 0.5:
        notes.append(f"pH ({soil['pH']:.2f}) cukup, namun di luar rentang optimal "
                     f"{spec['ph_optimal']}; pertimbangkan pengapuran/sulfur.")
    else:
        notes.append(f"pH ({soil['pH']:.2f}) tidak cocok untuk {crop}; "
                     f"kemungkinan gagal tumbuh tanpa amelioran.")

    for nutrient in ["N", "P", "K"]:
        cur = soil[nutrient]
        tgt = spec[f"{nutrient}_target"]
        if cur >= tgt:
            if cur > 1.5 * tgt:
                notes.append(f"{nutrient} berlebih ({cur:.0f} vs target {tgt:.0f} mg/kg) — "
                             f"hemat pupuk {nutrient} pada penanaman.")
        else:
            deficit = tgt - cur
            notes.append(f"{nutrient} defisit {deficit:.0f} mg/kg "
                         f"(aktual {cur:.0f}, target {tgt:.0f}) — perlu dosis koreksi.")

    if f["EC"] < 1.0:
        notes.append(f"EC ({soil['EC']:.0f} uS/cm) melebihi batas {spec['ec_max']:.0f}; "
                     f"risiko stres salinitas.")
    if f["temp"] < 1.0:
        notes.append(f"Suhu rata-rata ({soil['temp']:.1f} C) di luar rentang ideal "
                     f"{spec['temp_range']}.")

    return CropScore(crop=crop, total=round(total, 4),
                     factors=factors, notes=notes)


def rank_crops(soil: dict) -> list[CropScore]:
    scores = [evaluate_crop(c, soil) for c in C.CROP_DB]
    return sorted(scores, key=lambda s: s.total, reverse=True)


def soil_summary_from_zone_stats(zone_df: pd.DataFrame, plot_id: str) -> dict:
    """Profil tanah representatif plot = mean lintas zona (sudah ter-interpolasi)."""
    sub = zone_df[zone_df.plot_id == plot_id]
    return {p: float(sub[p].mean()) for p in ["N", "P", "K", "pH", "EC", "hum", "temp"]}


def main():
    zone_df = pd.read_csv(os.path.join(OUT_DS, "zone_stats.csv"))

    report = {}
    rec_table_rows = []
    print("=" * 78)
    for plot_id in C.PLOT_SCENARIOS:
        spec = C.PLOT_SCENARIOS[plot_id]
        soil = soil_summary_from_zone_stats(zone_df, plot_id)
        ranked = rank_crops(soil)
        report[plot_id] = {
            "scenario_label": spec["label"],
            "soil_profile": {k: round(v, 2) for k, v in soil.items()},
            "rankings": [s.as_dict() for s in ranked],
        }

        print(f"\n[REC] {plot_id} — {spec['label']}")
        print(f"      Profil: " + ", ".join(f"{k}={v:.1f}" for k, v in soil.items()))
        print(f"      Ranking komoditas:")
        for s in ranked:
            print(f"        {s.total:.3f}  {s.crop}")

        top = ranked[0]
        print(f"\n      >> REKOMENDASI: {top.crop}  (skor {top.total:.3f})")
        print(f"      Penjelasan (XAI):")
        for line in top.notes:
            print(f"        - {line}")

        # Tambahkan ke tabel rekomendasi
        for rank_i, s in enumerate(ranked, start=1):
            rec_table_rows.append({
                "plot_id": plot_id,
                "rank": rank_i,
                "crop": s.crop,
                "total_score": s.total,
                "pH_score":  s.factors["pH"][0],
                "N_score":   s.factors["N"][0],
                "P_score":   s.factors["P"][0],
                "K_score":   s.factors["K"][0],
                "hum_score": s.factors["hum"][0],
                "temp_score":s.factors["temp"][0],
                "EC_score":  s.factors["EC"][0],
            })

    rec_df = pd.DataFrame(rec_table_rows)
    rec_path = os.path.join(OUT_TABLES, "crop_recommendation_ranking.csv")
    rec_df.to_csv(rec_path, index=False)
    print(f"\n[OUT] {rec_path}")

    rep_path = os.path.join(OUT_REPORTS, "crop_recommendation.json")
    with open(rep_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"[OUT] {rep_path}")


if __name__ == "__main__":
    main()

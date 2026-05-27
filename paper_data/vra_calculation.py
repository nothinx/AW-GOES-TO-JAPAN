"""
Step 4 & 5 — Variable Rate Application (VRA) calculation.

Untuk tiap zona dari `zone_stats.csv`:
  1. Pilih target crop (rekomendasi top dari step 3, tingkat plot)
  2. Hitung defisit N, P, K vs target crop
  3. Konversi defisit -> kebutuhan pupuk (kg/ha), dengan formulasi nyata:
       - Urea (46% N)   untuk koreksi N
       - SP-36 (36% P)  untuk koreksi P
       - KCl (60% K)    untuk koreksi K
  4. Hitung total dosis per zona (kg) = dose_kg_ha * zone_area_ha
  5. Hitung biaya per zona (IDR) berdasarkan harga pupuk subsidi

Lalu BANDINGKAN dengan praktik KONVENSIONAL (blanket application):
  - Petani memberikan dosis rekomendasi standar Kementan secara merata
    (dihitung dari defisit MAKSIMUM agar zona terparah tetap tercukupi)
  - Total pupuk konvensional = dose_max * total_area_ha

Output:
  - tables/vra_zone_dosing_<plot>.csv     (tabel VRA per zona, paper-ready)
  - tables/vra_vs_conventional.csv        (summary perbandingan per plot)
  - reports/vra_summary.json              (metrik agregat untuk paper)
"""
from __future__ import annotations

import json
import math
import os

import numpy as np
import pandas as pd

import config as C


HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DS = os.path.join(HERE, "output", "datasets")
OUT_TABLES = os.path.join(HERE, "output", "tables")
OUT_REPORTS = os.path.join(HERE, "output", "reports")


# Konversi mg/kg defisit hara -> kg unsur hara murni per ha tanah olah 20cm
def mgkg_to_kg_per_ha(deficit_mgkg: float) -> float:
    # 1 mg/kg = 1 g/ton = 1e-6 kg/kg; soil mass ha = SOIL_MASS_PER_HA_KG
    return (deficit_mgkg * 1e-6) * C.SOIL_MASS_PER_HA_KG


def fertilizer_kg_per_ha(deficit_mgkg: float, fertilizer: str, nutrient: str) -> float:
    """kg pupuk per ha untuk menutup defisit hara `nutrient`."""
    pure_kg = mgkg_to_kg_per_ha(deficit_mgkg)
    pct = C.FERTILIZER_DB[fertilizer][nutrient] / 100.0
    if pct <= 0:
        raise ValueError(f"{fertilizer} tidak mengandung {nutrient}")
    return pure_kg / pct


# Memilih komoditas target per plot (top-1 dari rekomendasi)
def load_top_crop_per_plot() -> dict:
    rec_path = os.path.join(OUT_REPORTS, "crop_recommendation.json")
    with open(rec_path) as f:
        rec = json.load(f)
    return {pid: rec[pid]["rankings"][0]["crop"] for pid in rec}


def compute_vra(zone_df: pd.DataFrame, top_crops: dict) -> pd.DataFrame:
    rows = []
    for _, z in zone_df.iterrows():
        plot_id = z["plot_id"]
        crop = top_crops[plot_id]
        spec = C.CROP_DB[crop]
        n_def = max(0.0, spec["N_target"] - z["N"])
        p_def = max(0.0, spec["P_target"] - z["P"])
        k_def = max(0.0, spec["K_target"] - z["K"])

        urea_kg_ha  = fertilizer_kg_per_ha(n_def, "Urea",  "N") if n_def > 0 else 0.0
        sp36_kg_ha  = fertilizer_kg_per_ha(p_def, "SP-36", "P") if p_def > 0 else 0.0
        kcl_kg_ha   = fertilizer_kg_per_ha(k_def, "KCl",   "K") if k_def > 0 else 0.0

        urea_kg = urea_kg_ha * z["area_ha"]
        sp36_kg = sp36_kg_ha * z["area_ha"]
        kcl_kg  = kcl_kg_ha  * z["area_ha"]

        cost = (urea_kg * C.FERTILIZER_DB["Urea"]["price_idr_kg"]
                + sp36_kg * C.FERTILIZER_DB["SP-36"]["price_idr_kg"]
                + kcl_kg  * C.FERTILIZER_DB["KCl"]["price_idr_kg"])

        rows.append({
            "plot_id":    plot_id,
            "zone_id":    int(z["zone_id"]),
            "zone_row":   int(z["zone_row"]),
            "zone_col":   int(z["zone_col"]),
            "area_ha":    round(z["area_ha"], 4),
            "target_crop": crop,
            "N_actual":   round(z["N"], 1),
            "P_actual":   round(z["P"], 1),
            "K_actual":   round(z["K"], 1),
            "N_target":   spec["N_target"],
            "P_target":   spec["P_target"],
            "K_target":   spec["K_target"],
            "N_deficit_mgkg":  round(n_def, 1),
            "P_deficit_mgkg":  round(p_def, 1),
            "K_deficit_mgkg":  round(k_def, 1),
            "Urea_kg_per_ha":  round(urea_kg_ha, 2),
            "SP36_kg_per_ha":  round(sp36_kg_ha, 2),
            "KCl_kg_per_ha":   round(kcl_kg_ha, 2),
            "Urea_kg_zone":    round(urea_kg, 2),
            "SP36_kg_zone":    round(sp36_kg, 2),
            "KCl_kg_zone":     round(kcl_kg, 2),
            "cost_idr_zone":   round(cost, 0),
        })
    return pd.DataFrame(rows)


def compute_conventional(vra_df: pd.DataFrame, top_crops: dict) -> pd.DataFrame:
    """Praktik KONVENSIONAL = dosis rekomendasi standar Kementan (one-size-fits-all).

    Petani konvensional mengaplikasikan dosis sesuai panduan BPP/Kementan
    untuk komoditas yang dipilih, **tanpa** memperhitungkan kondisi tanah
    aktual. Ini representasi yang akurat untuk praktik 'pukul rata'.
    """
    rows = []
    for plot_id, sub in vra_df.groupby("plot_id"):
        total_area = sub["area_ha"].sum()
        crop = top_crops[plot_id]
        blanket = C.KEMENTAN_BLANKET_DOSE[crop]

        urea_kg_ha_conv = blanket["Urea"]
        sp36_kg_ha_conv = blanket["SP-36"]
        kcl_kg_ha_conv  = blanket["KCl"]

        urea_total_conv = urea_kg_ha_conv * total_area
        sp36_total_conv = sp36_kg_ha_conv * total_area
        kcl_total_conv  = kcl_kg_ha_conv  * total_area

        cost_conv = (urea_total_conv * C.FERTILIZER_DB["Urea"]["price_idr_kg"]
                     + sp36_total_conv * C.FERTILIZER_DB["SP-36"]["price_idr_kg"]
                     + kcl_total_conv  * C.FERTILIZER_DB["KCl"]["price_idr_kg"])

        # VRA totals
        urea_total_vra = sub["Urea_kg_zone"].sum()
        sp36_total_vra = sub["SP36_kg_zone"].sum()
        kcl_total_vra  = sub["KCl_kg_zone"].sum()
        cost_vra = sub["cost_idr_zone"].sum()

        total_vra = urea_total_vra + sp36_total_vra + kcl_total_vra
        total_conv = urea_total_conv + sp36_total_conv + kcl_total_conv
        savings_kg = total_conv - total_vra
        savings_pct = (savings_kg / total_conv * 100.0) if total_conv > 0 else 0.0
        cost_savings_idr = cost_conv - cost_vra
        cost_savings_pct = (cost_savings_idr / cost_conv * 100.0) if cost_conv > 0 else 0.0

        rows.append({
            "plot_id":   plot_id,
            "target_crop": crop,
            "total_area_ha": round(total_area, 3),
            "n_zones":   len(sub),
            "Urea_kg_VRA":     round(urea_total_vra, 1),
            "SP36_kg_VRA":     round(sp36_total_vra, 1),
            "KCl_kg_VRA":      round(kcl_total_vra,  1),
            "Total_kg_VRA":    round(total_vra,      1),
            "Cost_IDR_VRA":    round(cost_vra,       0),
            "Urea_kg_Conv":    round(urea_total_conv, 1),
            "SP36_kg_Conv":    round(sp36_total_conv, 1),
            "KCl_kg_Conv":     round(kcl_total_conv,  1),
            "Total_kg_Conv":   round(total_conv,      1),
            "Cost_IDR_Conv":   round(cost_conv,       0),
            "Savings_kg":      round(savings_kg,      1),
            "Savings_pct_kg":  round(savings_pct,     1),
            "Cost_Savings_IDR":     round(cost_savings_idr, 0),
            "Cost_Savings_pct":     round(cost_savings_pct, 1),
        })
    return pd.DataFrame(rows)


def main():
    zone_df = pd.read_csv(os.path.join(OUT_DS, "zone_stats.csv"))
    top_crops = load_top_crop_per_plot()
    print(f"[VRA] Komoditas target per plot: {top_crops}")

    vra_df = compute_vra(zone_df, top_crops)

    # Simpan VRA per plot (paper-ready)
    print("\n=== Tabel VRA per Zona ===")
    for plot_id, sub in vra_df.groupby("plot_id"):
        path = os.path.join(OUT_TABLES, f"vra_dosing_{plot_id}.csv")
        sub.to_csv(path, index=False)
        print(f"\n[OUT] {path}")
        # Tampilkan kolom kunci
        cols = ["zone_id", "N_deficit_mgkg", "P_deficit_mgkg", "K_deficit_mgkg",
                "Urea_kg_per_ha", "SP36_kg_per_ha", "KCl_kg_per_ha", "cost_idr_zone"]
        print(sub[cols].to_string(index=False))

    # Simpan VRA gabungan
    vra_all_path = os.path.join(OUT_TABLES, "vra_dosing_all.csv")
    vra_df.to_csv(vra_all_path, index=False)
    print(f"\n[OUT] {vra_all_path}")

    # Compute VRA vs Conventional
    comp_df = compute_conventional(vra_df, top_crops)
    comp_path = os.path.join(OUT_TABLES, "vra_vs_conventional.csv")
    comp_df.to_csv(comp_path, index=False)

    print("\n" + "=" * 78)
    print("KALKULASI VRA vs KONVENSIONAL — Ringkasan")
    print("=" * 78)
    for _, r in comp_df.iterrows():
        print(f"\n[{r['plot_id']}]  Komoditas: {r['target_crop']}  "
              f"Luas: {r['total_area_ha']:.2f} ha  ({r['n_zones']} zona)")
        print(f"  Konvensional : {r['Total_kg_Conv']:>9.1f} kg  | "
              f"Rp {r['Cost_IDR_Conv']:>12,.0f}")
        print(f"  Terra-Agri VRA: {r['Total_kg_VRA']:>9.1f} kg  | "
              f"Rp {r['Cost_IDR_VRA']:>12,.0f}")
        print(f"  Penghematan  : {r['Savings_kg']:>9.1f} kg ({r['Savings_pct_kg']:.1f}%)  | "
              f"Rp {r['Cost_Savings_IDR']:>12,.0f} ({r['Cost_Savings_pct']:.1f}%)")

    # Agregat lintas plot
    total_kg_conv = comp_df["Total_kg_Conv"].sum()
    total_kg_vra  = comp_df["Total_kg_VRA"].sum()
    total_savings_kg = total_kg_conv - total_kg_vra
    total_savings_pct = total_savings_kg / total_kg_conv * 100.0
    total_cost_conv = comp_df["Cost_IDR_Conv"].sum()
    total_cost_vra  = comp_df["Cost_IDR_VRA"].sum()
    total_cost_savings = total_cost_conv - total_cost_vra
    total_cost_pct = total_cost_savings / total_cost_conv * 100.0

    print("\n" + "-" * 78)
    print("AGREGAT LINTAS PLOT")
    print("-" * 78)
    print(f"  Total pupuk Konvensional: {total_kg_conv:>10.1f} kg")
    print(f"  Total pupuk VRA         : {total_kg_vra:>10.1f} kg")
    print(f"  Penghematan total       : {total_savings_kg:>10.1f} kg "
          f"({total_savings_pct:.1f}%)")
    print(f"  Biaya Konvensional      : Rp {total_cost_conv:>14,.0f}")
    print(f"  Biaya VRA               : Rp {total_cost_vra:>14,.0f}")
    print(f"  Penghematan biaya       : Rp {total_cost_savings:>14,.0f} "
          f"({total_cost_pct:.1f}%)")
    print("=" * 78)

    # JSON summary
    summary = {
        "per_plot": comp_df.to_dict(orient="records"),
        "aggregate": {
            "total_kg_conventional": round(total_kg_conv, 1),
            "total_kg_vra":          round(total_kg_vra, 1),
            "savings_kg":            round(total_savings_kg, 1),
            "savings_pct":           round(total_savings_pct, 2),
            "total_cost_idr_conventional": round(total_cost_conv, 0),
            "total_cost_idr_vra":          round(total_cost_vra, 0),
            "cost_savings_idr":            round(total_cost_savings, 0),
            "cost_savings_pct":            round(total_cost_pct, 2),
        },
        "_note": "Synthetic validation dataset. Field deployment is planned as future work.",
    }
    sum_path = os.path.join(OUT_REPORTS, "vra_summary.json")
    with open(sum_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\n[OUT] {sum_path}")


if __name__ == "__main__":
    main()

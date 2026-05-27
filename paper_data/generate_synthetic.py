"""
Step 1 — Synthetic dataset generator untuk Terra-Agri.

Setiap plot dibangun dari:
  - Surface spasial halus (kombinasi 2 fungsi sinus 2D + RBF random)
    -> menjamin auto-korelasi spasial seperti tanah asli
  - Mean spesifik per parameter (sesuai skenario)
  - Sensor noise gaussian (sesuai SENSOR_NOISE_STD)

Output:
  output/datasets/<plot>.csv  -> tabular siap analisis
  output/datasets/<plot>.json -> schema identik Main_Raspi.py (per-titik)
  output/datasets/all_plots.parquet (opsional)
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

import config as C


HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DS = os.path.join(HERE, "output", "datasets")
os.makedirs(OUT_DS, exist_ok=True)


def _plot_bounds(area_ha: float):
    """Compute lat/lng bounding box for a square plot of given area (ha)."""
    side_m = math.sqrt(area_ha * 10_000.0)  # 1 ha = 10_000 m^2
    half_lat = (side_m / 2.0) / C.M_PER_DEG_LAT
    half_lng = (side_m / 2.0) / C.M_PER_DEG_LNG
    return half_lat, half_lng, side_m


def _spatial_surface(xs_norm, ys_norm, amp, rng):
    """Bangun permukaan spasial halus dari kombinasi gelombang + RBF acak.

    xs_norm, ys_norm ada dalam [0,1] (koordinat dinormalisasi pada plot).
    Output dikembalikan dengan magnitudo ~amp (positif & negatif sekitar 0).
    """
    # Komponen gelombang 2D (memberi gradien yang realistis)
    fx = rng.uniform(0.8, 1.8)
    fy = rng.uniform(0.8, 1.8)
    phx = rng.uniform(0, 2 * math.pi)
    phy = rng.uniform(0, 2 * math.pi)
    base = np.sin(fx * math.pi * xs_norm + phx) + np.cos(fy * math.pi * ys_norm + phy)

    # Komponen RBF acak (zona-zona kecil) -> ~3 pusat per plot
    rbf = np.zeros_like(xs_norm)
    n_centers = 3
    for _ in range(n_centers):
        cx = rng.uniform(0.1, 0.9)
        cy = rng.uniform(0.1, 0.9)
        sigma = rng.uniform(0.12, 0.25)
        weight = rng.uniform(-1.0, 1.0)
        d2 = (xs_norm - cx) ** 2 + (ys_norm - cy) ** 2
        rbf += weight * np.exp(-d2 / (2 * sigma ** 2))

    surf = 0.55 * base + 0.45 * rbf
    # Normalisasi -> magnitudo tepat = amp
    surf = surf / (np.max(np.abs(surf)) + 1e-9) * amp
    return surf


def generate_plot(plot_id: str, spec: dict, rng: np.random.Generator) -> pd.DataFrame:
    half_lat, half_lng, side_m = _plot_bounds(spec["area_ha"])

    n = spec["n_samples"]
    # Distribusi sampel: 70% kuasi-random (Halton-like) + 30% acak murni,
    # meniru pola survei petani yang tidak ideal.
    u = rng.uniform(0.0, 1.0, size=n)
    v = rng.uniform(0.0, 1.0, size=n)

    # Dinormalisasi pada [0,1] untuk pembangkitan permukaan
    xs_norm = u
    ys_norm = v

    rows = []
    surfaces = {p: _spatial_surface(xs_norm, ys_norm, spec["spatial_amp"][p], rng)
                for p in spec["mean"].keys()}

    pmin = {k: v[0] for k, v in C.SOIL_PARAM_RANGES.items()}
    pmax = {k: v[1] for k, v in C.SOIL_PARAM_RANGES.items()}

    t0 = datetime(2026, 5, 27, 7, 30, 0)
    for i in range(n):
        lat = C.ANCHOR_LAT + (ys_norm[i] - 0.5) * 2 * half_lat
        lng = C.ANCHOR_LNG + (xs_norm[i] - 0.5) * 2 * half_lng

        row = {
            "plot_id": plot_id,
            "point_id": i + 1,
            "timestamp": (t0 + timedelta(seconds=int(i * 12))).strftime("%Y-%m-%d %H:%M:%S"),
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "x_m": round((xs_norm[i] - 0.5) * side_m, 2),
            "y_m": round((ys_norm[i] - 0.5) * side_m, 2),
        }
        for p, mean_val in spec["mean"].items():
            val = mean_val + surfaces[p][i] + rng.normal(0.0, C.SENSOR_NOISE_STD[p])
            val = float(np.clip(val, pmin[p], pmax[p]))
            # Round sesuai sensor: integer untuk EC, N, P, K; satu desimal lainnya
            if p in ("EC", "N", "P", "K"):
                val = round(val)
            else:
                val = round(val, 2)
            row[p] = val
        rows.append(row)

    return pd.DataFrame(rows)


def df_to_wand_json(df: pd.DataFrame, path: str):
    """Tulis JSON dengan schema identik output Main_Raspi.py."""
    points = []
    for _, r in df.iterrows():
        points.append({
            "timestamp": r["timestamp"],
            "soil": {
                "temp": r["temp"], "hum": r["hum"], "ph": r["pH"],
                "ec": r["EC"], "n": r["N"], "p": r["P"], "k": r["K"],
            },
            "location": {"lat": r["lat"], "lng": r["lng"], "valid": True},
        })
    with open(path, "w") as f:
        json.dump({
            "_meta": {
                "source": "synthetic",
                "generator": "Terra-Agri/paper_data/generate_synthetic.py",
                "note": "Synthetic validation dataset; NOT field-collected.",
            },
            "points": points,
        }, f, indent=2)


def main():
    rng = np.random.default_rng(C.RANDOM_SEED)
    all_frames = []
    for plot_id, spec in C.PLOT_SCENARIOS.items():
        print(f"[GEN] {plot_id} — {spec['label']} | {spec['n_samples']} titik / {spec['area_ha']} ha")
        df = generate_plot(plot_id, spec, rng)
        csv_path = os.path.join(OUT_DS, f"{plot_id}.csv")
        json_path = os.path.join(OUT_DS, f"{plot_id}.json")
        df.to_csv(csv_path, index=False)
        df_to_wand_json(df, json_path)
        all_frames.append(df)
        print(f"       -> {csv_path}")
        print(f"       -> {json_path}")

    combined = pd.concat(all_frames, ignore_index=True)
    combined.to_csv(os.path.join(OUT_DS, "all_plots.csv"), index=False)
    print(f"[GEN] Combined: {len(combined)} titik total -> all_plots.csv")

    # Ringkasan deskriptif per plot
    print("\n=== Ringkasan Statistik ===")
    for plot_id in C.PLOT_SCENARIOS:
        sub = combined[combined.plot_id == plot_id]
        desc = sub[["N", "P", "K", "pH", "EC", "hum", "temp"]].agg(["mean", "std"]).round(2)
        print(f"\n{plot_id}:")
        print(desc.to_string())


if __name__ == "__main__":
    main()

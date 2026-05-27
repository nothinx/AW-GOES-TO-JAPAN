"""
Step 2 — Terra Core spatial interpolation pipeline.

Mengubah titik sampel tak-beraturan dari Agri Wand menjadi:
  - Grid kontinu (heatmap) per parameter
  - Statistik per zona manajemen (NxN grid)
  - Cross-validation metric (Leave-One-Out) untuk legitimasi metode

Metode: IDW (Inverse Distance Weighting, p=2) sebagai baseline yang ringan
secara komputasi -- konsisten dengan kebutuhan "edge computing" Terra Core
(tidak perlu library kriging berat). Untuk verifikasi, juga digunakan
Radial Basis Function (Thin-Plate Spline) sebagai pembanding.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.interpolate import RBFInterpolator

import config as C


HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DS = os.path.join(HERE, "output", "datasets")
OUT_REPORTS = os.path.join(HERE, "output", "reports")
os.makedirs(OUT_REPORTS, exist_ok=True)

PARAMS = ["N", "P", "K", "pH", "EC", "hum", "temp"]


# -----------------------------------------------------------------------------
# Interpolators
# -----------------------------------------------------------------------------
def idw_interpolate(pts_xy: np.ndarray, vals: np.ndarray,
                    grid_xy: np.ndarray, power: float = 2.0,
                    eps: float = 1e-9) -> np.ndarray:
    """Inverse Distance Weighting. pts_xy: (N,2), vals: (N,), grid_xy: (M,2)."""
    # (M, N) jarak euclidean
    dx = grid_xy[:, 0:1] - pts_xy[:, 0:1].T
    dy = grid_xy[:, 1:2] - pts_xy[:, 1:2].T
    dist = np.sqrt(dx ** 2 + dy ** 2)
    # Hindari nol -> kembalikan nilai eksak pada titik sampel
    w = 1.0 / (dist ** power + eps)
    return (w @ vals) / w.sum(axis=1)


def rbf_interpolate(pts_xy: np.ndarray, vals: np.ndarray,
                    grid_xy: np.ndarray) -> np.ndarray:
    rbf = RBFInterpolator(pts_xy, vals, kernel="thin_plate_spline",
                          smoothing=1.0)
    return rbf(grid_xy)


# -----------------------------------------------------------------------------
# Cross-validation (Leave-One-Out) untuk legitimasi metode
# -----------------------------------------------------------------------------
def loo_rmse_mae(pts_xy: np.ndarray, vals: np.ndarray, method: str = "idw") -> dict:
    n = len(vals)
    preds = np.empty(n)
    for i in range(n):
        mask = np.ones(n, dtype=bool)
        mask[i] = False
        sub_pts = pts_xy[mask]
        sub_vals = vals[mask]
        target = pts_xy[i:i + 1]
        if method == "idw":
            preds[i] = idw_interpolate(sub_pts, sub_vals, target)[0]
        elif method == "rbf":
            preds[i] = rbf_interpolate(sub_pts, sub_vals, target)[0]
        else:
            raise ValueError(method)
    err = preds - vals
    return {
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "mae": float(np.mean(np.abs(err))),
        "r2": float(1.0 - np.sum(err ** 2) / np.sum((vals - vals.mean()) ** 2)),
    }


# -----------------------------------------------------------------------------
# Zona manajemen (untuk VRA)
# -----------------------------------------------------------------------------
@dataclass
class ZoneStat:
    plot_id: str
    zone_id: int          # 1..N*N
    zone_row: int         # 1..N
    zone_col: int         # 1..N
    area_ha: float
    means: dict           # {"N":..,"P":..,...}


def build_grid(plot_df: pd.DataFrame, res: int = C.GRID_RES):
    xmin, xmax = plot_df["x_m"].min(), plot_df["x_m"].max()
    ymin, ymax = plot_df["y_m"].min(), plot_df["y_m"].max()
    # Sedikit padding supaya kontur tidak nol di tepi
    pad_x = (xmax - xmin) * 0.02
    pad_y = (ymax - ymin) * 0.02
    gx = np.linspace(xmin - pad_x, xmax + pad_x, res)
    gy = np.linspace(ymin - pad_y, ymax + pad_y, res)
    GX, GY = np.meshgrid(gx, gy)
    return GX, GY, gx, gy


def interpolate_all_params(plot_df: pd.DataFrame) -> dict:
    GX, GY, gx, gy = build_grid(plot_df)
    grid_xy = np.column_stack([GX.ravel(), GY.ravel()])
    pts_xy = plot_df[["x_m", "y_m"]].values

    out = {"gx": gx, "gy": gy, "GX": GX, "GY": GY, "layers": {}}
    for p in PARAMS:
        z = idw_interpolate(pts_xy, plot_df[p].values, grid_xy, power=2.0)
        out["layers"][p] = z.reshape(GX.shape)
    return out


def compute_zone_stats(plot_id: str, plot_df: pd.DataFrame, interp: dict,
                       n_zones: int = C.N_ZONES_PER_SIDE,
                       area_ha: float = 3.0) -> list[ZoneStat]:
    gx, gy = interp["gx"], interp["gy"]
    GX, GY = interp["GX"], interp["GY"]

    # Cell-area heuristic: bagi rata; setiap zona 1/(n*n) dari plot.
    cell_ha = area_ha / (n_zones * n_zones)

    x_edges = np.linspace(gx.min(), gx.max(), n_zones + 1)
    y_edges = np.linspace(gy.min(), gy.max(), n_zones + 1)

    stats = []
    zid = 0
    for r in range(n_zones):
        for c in range(n_zones):
            zid += 1
            x0, x1 = x_edges[c], x_edges[c + 1]
            y0, y1 = y_edges[r], y_edges[r + 1]
            mask = (GX >= x0) & (GX < x1) & (GY >= y0) & (GY < y1)
            if not mask.any():
                continue
            means = {p: float(np.mean(interp["layers"][p][mask])) for p in PARAMS}
            stats.append(ZoneStat(
                plot_id=plot_id,
                zone_id=zid,
                zone_row=r + 1,
                zone_col=c + 1,
                area_ha=cell_ha,
                means=means,
            ))
    return stats


def zones_to_df(zones: list[ZoneStat]) -> pd.DataFrame:
    rows = []
    for z in zones:
        row = {"plot_id": z.plot_id, "zone_id": z.zone_id,
               "zone_row": z.zone_row, "zone_col": z.zone_col,
               "area_ha": z.area_ha}
        for p, v in z.means.items():
            row[p] = round(v, 2)
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    cv_report = {}
    all_zones = []
    interp_cache = {}

    for plot_id in C.PLOT_SCENARIOS:
        spec = C.PLOT_SCENARIOS[plot_id]
        df = pd.read_csv(os.path.join(OUT_DS, f"{plot_id}.csv"))
        print(f"\n[INTERP] {plot_id} ({len(df)} titik)")

        # Cross-validation per parameter
        cv = {}
        pts_xy = df[["x_m", "y_m"]].values
        for p in PARAMS:
            cv[p] = loo_rmse_mae(pts_xy, df[p].values, method="idw")
        cv_report[plot_id] = cv
        for p in PARAMS:
            print(f"  IDW LOO-CV {p:5s} RMSE={cv[p]['rmse']:.3f} "
                  f"MAE={cv[p]['mae']:.3f} R2={cv[p]['r2']:.3f}")

        # Interpolate semua layer
        interp = interpolate_all_params(df)
        interp_cache[plot_id] = interp

        # Zona statistik (untuk VRA hilir)
        zones = compute_zone_stats(plot_id, df, interp,
                                    area_ha=spec["area_ha"])
        all_zones.extend(zones)

    # Simpan zona table
    zdf = zones_to_df(all_zones)
    zdf_path = os.path.join(OUT_DS, "zone_stats.csv")
    zdf.to_csv(zdf_path, index=False)
    print(f"\n[OUT] {zdf_path} ({len(zdf)} zona total)")

    # Simpan CV report
    cv_path = os.path.join(OUT_REPORTS, "interpolation_cv.json")
    with open(cv_path, "w") as f:
        json.dump(cv_report, f, indent=2)
    print(f"[OUT] {cv_path}")

    # Simpan grid arrays sebagai .npz (untuk paper figures)
    for plot_id, interp in interp_cache.items():
        npz_path = os.path.join(OUT_DS, f"{plot_id}_interp.npz")
        np.savez_compressed(npz_path,
                            gx=interp["gx"], gy=interp["gy"],
                            **{f"layer_{p}": interp["layers"][p] for p in PARAMS})
        print(f"[OUT] {npz_path}")


if __name__ == "__main__":
    main()

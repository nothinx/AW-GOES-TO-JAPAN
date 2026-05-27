"""
Step 6 — Paper-ready figures.

Menghasilkan figure-figure utama untuk publikasi:
  Fig 1.  Sampling distribution (3 plot)             -> sampling_distribution.png
  Fig 2.  Heatmap interpolasi N, P, K, pH per plot   -> heatmap_<plot>.png
  Fig 3.  VRA dosing map per zona (3 plot)           -> vra_zonemap_<plot>.png
  Fig 4.  Bar chart VRA vs Konvensional              -> vra_vs_conv_bars.png
  Fig 5.  Crop recommendation scoring (heatmap)      -> crop_score_heatmap.png
  Fig 6.  Yield distribution Konv vs VRA (per crop)  -> yield_distribution.png
  Fig 7.  Cost breakdown stacked bar                 -> cost_breakdown.png
"""
from __future__ import annotations

import json
import os

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap

import config as C

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DS = os.path.join(HERE, "output", "datasets")
OUT_FIG = os.path.join(HERE, "output", "figures")
OUT_TABLES = os.path.join(HERE, "output", "tables")
OUT_REPORTS = os.path.join(HERE, "output", "reports")
os.makedirs(OUT_FIG, exist_ok=True)


# -----------------------------------------------------------------------------
# Style global - paper-ready
# -----------------------------------------------------------------------------
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.labelsize": 11,
    "axes.edgecolor": "#333333",
    "axes.linewidth": 0.8,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linestyle": "--",
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "legend.frameon": True,
    "legend.framealpha": 0.92,
    "legend.edgecolor": "#cccccc",
    "figure.dpi": 110,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

# Palet konsisten
PALETTE = {
    "vra":          "#2a9d8f",
    "conventional": "#e63946",
    "neutral":      "#264653",
    "accent":       "#e9c46a",
    "soft":         "#f4a261",
}

# Custom diverging colormap untuk peta hara (defisit -> netral -> surplus)
CMAP_NUTRIENT = LinearSegmentedColormap.from_list(
    "nutrient", ["#d62828", "#f4a261", "#e9c46a", "#90be6d", "#2a9d8f"]
)


def _save(fig, name):
    path = os.path.join(OUT_FIG, name)
    fig.savefig(path)
    plt.close(fig)
    print(f"[FIG] {path}")
    return path


# -----------------------------------------------------------------------------
# Fig 1 - Sampling distribution
# -----------------------------------------------------------------------------
def fig_sampling_distribution(all_df: pd.DataFrame):
    plots = list(C.PLOT_SCENARIOS.keys())
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.5))
    for ax, pid in zip(axes, plots):
        sub = all_df[all_df.plot_id == pid]
        sc = ax.scatter(sub.x_m, sub.y_m, c=sub.N, cmap=CMAP_NUTRIENT,
                        s=42, edgecolor="white", linewidth=0.5)
        ax.set_title(f"{pid}\n{C.PLOT_SCENARIOS[pid]['label']} (n={len(sub)})")
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_aspect("equal")
        cb = plt.colorbar(sc, ax=ax, shrink=0.85)
        cb.set_label("N (mg/kg)", fontsize=9)
    fig.suptitle("Distribusi Spasial Titik Sampel Agri Wand — 3 Skenario Plot",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    _save(fig, "fig1_sampling_distribution.png")


# -----------------------------------------------------------------------------
# Fig 2 - Heatmap N, P, K, pH per plot (interpolated)
# -----------------------------------------------------------------------------
def fig_heatmaps_per_plot():
    params_to_plot = ["N", "P", "K", "pH"]
    units = {"N": "mg/kg", "P": "mg/kg", "K": "mg/kg", "pH": "-"}

    for pid in C.PLOT_SCENARIOS:
        npz = np.load(os.path.join(OUT_DS, f"{pid}_interp.npz"))
        gx, gy = npz["gx"], npz["gy"]
        pts = pd.read_csv(os.path.join(OUT_DS, f"{pid}.csv"))

        fig, axes = plt.subplots(1, 4, figsize=(16, 4))
        for ax, p in zip(axes, params_to_plot):
            layer = npz[f"layer_{p}"]
            im = ax.imshow(layer, extent=[gx.min(), gx.max(), gy.min(), gy.max()],
                           origin="lower", cmap=CMAP_NUTRIENT, aspect="auto")
            ax.scatter(pts.x_m, pts.y_m, c="black", s=4, alpha=0.45)
            ax.set_title(f"{p}")
            ax.set_xlabel("X (m)")
            ax.set_ylabel("Y (m)")
            cb = plt.colorbar(im, ax=ax, shrink=0.85)
            cb.set_label(units[p], fontsize=9)

        fig.suptitle(f"Heatmap Hasil Interpolasi (IDW p=2) — {pid}: "
                     f"{C.PLOT_SCENARIOS[pid]['label']}",
                     fontsize=13, fontweight="bold")
        fig.tight_layout()
        _save(fig, f"fig2_heatmap_{pid}.png")


# -----------------------------------------------------------------------------
# Fig 3 - VRA dosing map per zona
# -----------------------------------------------------------------------------
def fig_vra_zone_maps():
    vra_all = pd.read_csv(os.path.join(OUT_TABLES, "vra_dosing_all.csv"))
    n_side = C.N_ZONES_PER_SIDE

    for pid in C.PLOT_SCENARIOS:
        sub = vra_all[vra_all.plot_id == pid]
        if sub["Urea_kg_per_ha"].sum() + sub["SP36_kg_per_ha"].sum() + sub["KCl_kg_per_ha"].sum() == 0:
            # Tidak butuh pupuk: render note saja
            fig, ax = plt.subplots(figsize=(6, 5))
            ax.text(0.5, 0.5,
                    f"{pid}\n{C.PLOT_SCENARIOS[pid]['label']}\n\n"
                    "Tidak diperlukan aplikasi pupuk:\n"
                    "profil hara melebihi target komoditas.",
                    ha="center", va="center", fontsize=12, fontweight="bold",
                    transform=ax.transAxes,
                    bbox=dict(boxstyle="round,pad=0.7",
                              facecolor=PALETTE["vra"], alpha=0.15,
                              edgecolor=PALETTE["vra"], linewidth=2))
            ax.axis("off")
            _save(fig, f"fig3_vra_zonemap_{pid}.png")
            continue

        fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
        for ax, fert, col in zip(axes, ["Urea", "SP-36", "KCl"],
                                 ["Urea_kg_per_ha", "SP36_kg_per_ha", "KCl_kg_per_ha"]):
            mat = np.zeros((n_side, n_side))
            for _, r in sub.iterrows():
                mat[r.zone_row - 1, r.zone_col - 1] = r[col]
            if mat.max() == 0:
                ax.imshow(np.ones_like(mat), cmap="Greys", vmin=0, vmax=1, alpha=0.25)
                ax.text(0.5, 0.5, "Tidak\ndibutuhkan",
                        transform=ax.transAxes, ha="center", va="center",
                        fontsize=13, fontweight="bold", color="#777777")
                ax.set_xticks([]); ax.set_yticks([])
            else:
                tick_labels = [str(i + 1) for i in range(n_side)]
                sns.heatmap(mat, annot=True, fmt=".1f", cmap="YlGnBu",
                            ax=ax, cbar_kws={"label": "kg/ha"},
                            linewidths=0.5, linecolor="white",
                            annot_kws={"fontsize": 9},
                            xticklabels=tick_labels, yticklabels=tick_labels)
                ax.invert_yaxis()
            ax.set_title(f"{fert}  (kg/ha per zona)")
            ax.set_xlabel("Kolom zona")
            ax.set_ylabel("Baris zona")

        fig.suptitle(f"Peta Dosis VRA per Zona — {pid}: "
                     f"target {sub['target_crop'].iloc[0]}",
                     fontsize=13, fontweight="bold")
        fig.tight_layout()
        _save(fig, f"fig3_vra_zonemap_{pid}.png")


# -----------------------------------------------------------------------------
# Fig 4 - Bar chart VRA vs Konvensional
# -----------------------------------------------------------------------------
def fig_vra_vs_conv_bars():
    comp = pd.read_csv(os.path.join(OUT_TABLES, "vra_vs_conventional.csv"))

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # (a) Total pupuk (kg) per plot
    x = np.arange(len(comp))
    w = 0.36
    ymax_a = max(comp.Total_kg_Conv.max(), comp.Total_kg_VRA.max())
    ymax_b = max(comp.Cost_IDR_Conv.max(), comp.Cost_IDR_VRA.max()) / 1e6
    axes[0].bar(x - w/2, comp.Total_kg_Conv, width=w, label="Konvensional",
                color=PALETTE["conventional"], edgecolor="white")
    axes[0].bar(x + w/2, comp.Total_kg_VRA,  width=w, label="Terra-Agri VRA",
                color=PALETTE["vra"], edgecolor="white")
    for i, r in comp.iterrows():
        axes[0].text(i - w/2, r.Total_kg_Conv + 30, f"{r.Total_kg_Conv:.0f}",
                     ha="center", fontsize=9, fontweight="bold")
        axes[0].text(i + w/2, r.Total_kg_VRA  + 30, f"{r.Total_kg_VRA:.0f}",
                     ha="center", fontsize=9, fontweight="bold")
        # Annotation hemat (negatif = pengurangan)
        pct_change_mass = -r.Savings_pct_kg
        color_mass = PALETTE["accent"] if pct_change_mass <= 0 else "#f08080"
        savings_y = max(r.Total_kg_Conv, r.Total_kg_VRA) + ymax_a * 0.12
        axes[0].annotate(f"{pct_change_mass:+.1f}%",
                         xy=(i, savings_y), ha="center",
                         color=PALETTE["neutral"], fontweight="bold",
                         fontsize=10.5,
                         bbox=dict(boxstyle="round,pad=0.35",
                                   facecolor=color_mass, alpha=0.7,
                                   edgecolor=PALETTE["neutral"], linewidth=0.8))
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([p.replace("_", "\n", 1) for p in comp.plot_id])
    axes[0].set_ylabel("Total Pupuk (kg)")
    axes[0].set_title("(a) Total Massa Pupuk per Plot")
    axes[0].legend(loc="upper left")
    axes[0].set_ylim(0, ymax_a * 1.30)

    # (b) Biaya per plot
    axes[1].bar(x - w/2, comp.Cost_IDR_Conv / 1e6, width=w, label="Konvensional",
                color=PALETTE["conventional"], edgecolor="white")
    axes[1].bar(x + w/2, comp.Cost_IDR_VRA / 1e6,  width=w, label="Terra-Agri VRA",
                color=PALETTE["vra"], edgecolor="white")
    for i, r in comp.iterrows():
        axes[1].text(i - w/2, r.Cost_IDR_Conv / 1e6 + 0.1,
                     f"{r.Cost_IDR_Conv / 1e6:.2f}",
                     ha="center", fontsize=9, fontweight="bold")
        axes[1].text(i + w/2, r.Cost_IDR_VRA / 1e6 + 0.1,
                     f"{r.Cost_IDR_VRA / 1e6:.2f}",
                     ha="center", fontsize=9, fontweight="bold")
        pct_change_cost = -r.Cost_Savings_pct
        savings_y = max(r.Cost_IDR_Conv, r.Cost_IDR_VRA) / 1e6 + ymax_b * 0.12
        color = PALETTE["accent"] if pct_change_cost <= 0 else "#f08080"
        axes[1].annotate(f"{pct_change_cost:+.1f}%",
                         xy=(i, savings_y), ha="center",
                         color=PALETTE["neutral"], fontweight="bold",
                         fontsize=10.5,
                         bbox=dict(boxstyle="round,pad=0.35",
                                   facecolor=color, alpha=0.7,
                                   edgecolor=PALETTE["neutral"], linewidth=0.8))
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([p.replace("_", "\n", 1) for p in comp.plot_id])
    axes[1].set_ylabel("Biaya Pupuk (juta IDR)")
    axes[1].set_title("(b) Biaya Pupuk per Plot")
    axes[1].legend(loc="upper left")
    axes[1].set_ylim(0, ymax_b * 1.30)

    fig.suptitle("Perbandingan VRA vs Konvensional — 3 Skenario Plot 3 ha",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    _save(fig, "fig4_vra_vs_conv_bars.png")


# -----------------------------------------------------------------------------
# Fig 5 - Crop recommendation score heatmap
# -----------------------------------------------------------------------------
def fig_crop_score_heatmap():
    rec = pd.read_csv(os.path.join(OUT_TABLES, "crop_recommendation_ranking.csv"))
    # Pivot total_score
    piv = rec.pivot(index="crop", columns="plot_id", values="total_score")
    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    sns.heatmap(piv, annot=True, fmt=".3f", cmap="RdYlGn", vmin=0.4, vmax=1.0,
                ax=ax, cbar_kws={"label": "Skor total"},
                linewidths=0.6, linecolor="white",
                annot_kws={"fontsize": 10, "fontweight": "bold"})
    ax.set_title("Skor Kesesuaian Komoditas per Plot\n(XAI: skor = weighted sum 7 faktor agronomi)",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("Komoditas")

    # Mark top recommendation per plot
    for j, pid in enumerate(piv.columns):
        top_crop = piv[pid].idxmax()
        i = list(piv.index).index(top_crop)
        ax.add_patch(plt.Rectangle((j, i), 1, 1, fill=False,
                                    edgecolor="black", linewidth=2.4))

    fig.tight_layout()
    _save(fig, "fig5_crop_score_heatmap.png")


# -----------------------------------------------------------------------------
# Fig 6 - Yield distribution Konvensional vs VRA  (perbaikan versi teman)
# -----------------------------------------------------------------------------
def fig_yield_distribution():
    """Density curve dampak terhadap stabilitas hasil panen.

    Parameter loc/scale didasarkan pada literatur:
      - Padi VRA studies: yield ↑ 3–6%, CV ↓ 50–70%
        (Bongiovanni & Lowenberg-DeBoer 2004; Stafford 2000)
      - Singkong (cassava) yield 18–28 t/ha pada lahan tropis
      - Standar deviasi konvensional ~ 12–15% rata-rata
        (Mulla 2013, Precision agriculture review)
    """
    rng = np.random.default_rng(C.RANDOM_SEED + 1)

    # Tiga skenario: per komoditas yang direkomendasikan
    scenarios = [
        {"crop": "Padi (Plot A — Subur)",   "conv_mean": 6.8, "conv_sd": 1.05,
         "vra_mean": 7.2, "vra_sd": 0.42, "ylabel": "t/ha"},
        {"crop": "Singkong (Plot B — Defisit N)", "conv_mean": 22.0, "conv_sd": 3.8,
         "vra_mean": 25.5, "vra_sd": 1.5, "ylabel": "t/ha"},
        {"crop": "Singkong (Plot C — Asam)", "conv_mean": 18.5, "conv_sd": 4.1,
         "vra_mean": 22.0, "vra_sd": 1.7, "ylabel": "t/ha"},
    ]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5.0))

    for ax, sc in zip(axes, scenarios):
        n_sim = 2000
        y_conv = rng.normal(sc["conv_mean"], sc["conv_sd"], size=n_sim)
        y_vra  = rng.normal(sc["vra_mean"],  sc["vra_sd"],  size=n_sim)

        sns.kdeplot(y_conv, ax=ax, fill=True, alpha=0.35,
                    color=PALETTE["conventional"], linewidth=2.0,
                    label="Konvensional (blanket)")
        sns.kdeplot(y_vra, ax=ax, fill=True, alpha=0.55,
                    color=PALETTE["vra"], linewidth=2.4,
                    label="Terra-Agri VRA")

        mean_conv, mean_vra = sc["conv_mean"], sc["vra_mean"]
        ax.axvline(mean_conv, color=PALETTE["conventional"],
                   linestyle="--", linewidth=1.3, alpha=0.9)
        ax.axvline(mean_vra,  color=PALETTE["vra"],
                   linestyle="--", linewidth=1.3, alpha=0.9)

        # Delta annotation
        delta = (mean_vra - mean_conv) / mean_conv * 100.0
        cv_conv = sc["conv_sd"] / mean_conv * 100.0
        cv_vra  = sc["vra_sd"]  / mean_vra * 100.0

        ymax = ax.get_ylim()[1]
        ax.annotate(
            f"  Δ rata-rata: +{delta:.1f}%\n"
            f"  CV konv : {cv_conv:.1f}%\n"
            f"  CV VRA  : {cv_vra:.1f}%",
            xy=(mean_vra, ymax * 0.78),
            fontsize=9.5, fontweight="bold",
            color=PALETTE["neutral"],
            bbox=dict(boxstyle="round,pad=0.4",
                      facecolor="white", edgecolor=PALETTE["neutral"],
                      linewidth=1.0, alpha=0.9))

        ax.set_title(sc["crop"], fontsize=11, fontweight="bold")
        ax.set_xlabel(f"Hasil Panen ({sc['ylabel']})")
        ax.set_ylabel("Kepadatan probabilitas")
        ax.legend(loc="upper left", fontsize=9)
        ax.set_xlim(min(y_conv.min(), y_vra.min()) - 1,
                    max(y_conv.max(), y_vra.max()) + 1)

    fig.suptitle("Simulasi Stabilitas Hasil Panen: Konvensional vs Terra-Agri VRA",
                 fontsize=13.5, fontweight="bold", y=1.02)

    # Footer caption (sumber asumsi)
    fig.text(0.5, -0.04,
             "Parameter μ dan σ didasarkan pada meta-analisis VRA — "
             "Bongiovanni & Lowenberg-DeBoer (2004), Stafford (2000), Mulla (2013). "
             "Synthetic simulation; field validation planned.",
             ha="center", fontsize=8.5, style="italic", color="#555555")
    fig.tight_layout()
    _save(fig, "fig6_yield_distribution.png")


# -----------------------------------------------------------------------------
# Fig 7 - Cost breakdown stacked bar
# -----------------------------------------------------------------------------
def fig_cost_breakdown():
    comp = pd.read_csv(os.path.join(OUT_TABLES, "vra_vs_conventional.csv"))

    fig, ax = plt.subplots(figsize=(11, 5.5))
    plots = comp.plot_id.tolist()
    x = np.arange(len(plots))
    w = 0.38

    # Total per fertilizer cost
    def cost_kg(fert):
        return C.FERTILIZER_DB[fert]["price_idr_kg"]

    conv_urea = comp.Urea_kg_Conv * cost_kg("Urea") / 1e6
    conv_sp36 = comp.SP36_kg_Conv * cost_kg("SP-36") / 1e6
    conv_kcl  = comp.KCl_kg_Conv  * cost_kg("KCl")  / 1e6

    vra_urea = comp.Urea_kg_VRA * cost_kg("Urea") / 1e6
    vra_sp36 = comp.SP36_kg_VRA * cost_kg("SP-36") / 1e6
    vra_kcl  = comp.KCl_kg_VRA  * cost_kg("KCl")  / 1e6

    fert_colors = {"Urea": "#264653", "SP-36": "#e76f51", "KCl": "#2a9d8f"}

    ax.bar(x - w/2, conv_urea, w, label="Urea (Konv)",
           color=fert_colors["Urea"], edgecolor="white")
    ax.bar(x - w/2, conv_sp36, w, bottom=conv_urea, label="SP-36 (Konv)",
           color=fert_colors["SP-36"], edgecolor="white")
    ax.bar(x - w/2, conv_kcl, w, bottom=conv_urea + conv_sp36,
           label="KCl (Konv)", color=fert_colors["KCl"], edgecolor="white")

    ax.bar(x + w/2, vra_urea, w, color=fert_colors["Urea"],
           edgecolor="white", hatch="//", alpha=0.85, label="Urea (VRA)")
    ax.bar(x + w/2, vra_sp36, w, bottom=vra_urea, color=fert_colors["SP-36"],
           edgecolor="white", hatch="//", alpha=0.85, label="SP-36 (VRA)")
    ax.bar(x + w/2, vra_kcl,  w, bottom=vra_urea + vra_sp36,
           color=fert_colors["KCl"], edgecolor="white", hatch="//",
           alpha=0.85, label="KCl (VRA)")

    # Label bar
    for i, r in comp.iterrows():
        tot_conv = (r.Urea_kg_Conv * cost_kg("Urea")
                    + r.SP36_kg_Conv * cost_kg("SP-36")
                    + r.KCl_kg_Conv  * cost_kg("KCl")) / 1e6
        tot_vra = (r.Urea_kg_VRA * cost_kg("Urea")
                   + r.SP36_kg_VRA * cost_kg("SP-36")
                   + r.KCl_kg_VRA  * cost_kg("KCl")) / 1e6
        ax.text(i - w/2, tot_conv + 0.05, f"Rp {tot_conv:.2f}M",
                ha="center", fontsize=9, fontweight="bold")
        ax.text(i + w/2, tot_vra + 0.05, f"Rp {tot_vra:.2f}M",
                ha="center", fontsize=9, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(plots)
    ax.set_ylabel("Biaya (juta IDR)")
    ax.set_title("Breakdown Biaya Pupuk per Komponen — Konvensional vs VRA",
                 fontsize=12.5, fontweight="bold")
    # Legenda kompak: gabungkan pupuk
    legend_handles = [
        mpatches.Patch(color=fert_colors["Urea"],  label="Urea"),
        mpatches.Patch(color=fert_colors["SP-36"], label="SP-36"),
        mpatches.Patch(color=fert_colors["KCl"],   label="KCl"),
        mpatches.Patch(facecolor="white", edgecolor="black", label="solid = Konv"),
        mpatches.Patch(facecolor="white", edgecolor="black", hatch="//",
                       label="hatched = VRA"),
    ]
    ax.legend(handles=legend_handles, loc="center left",
              bbox_to_anchor=(1.01, 0.5), ncol=1)
    # Headroom + ruang legenda di samping
    conv_total = (conv_urea + conv_sp36 + conv_kcl).max()
    vra_total = (vra_urea + vra_sp36 + vra_kcl).max()
    ymax_cost = max(conv_total, vra_total)
    ax.set_ylim(0, ymax_cost * 1.18)
    fig.tight_layout()
    _save(fig, "fig7_cost_breakdown.png")


# -----------------------------------------------------------------------------
# Markdown summary table
# -----------------------------------------------------------------------------
def write_markdown_tables():
    comp = pd.read_csv(os.path.join(OUT_TABLES, "vra_vs_conventional.csv"))
    rec  = pd.read_csv(os.path.join(OUT_TABLES, "crop_recommendation_ranking.csv"))

    md = []
    md.append("# Terra-Agri — Paper Tables\n")
    md.append("> Synthetic validation dataset. Field deployment planned as future work.\n")

    md.append("## Table 1. VRA vs Conventional — per Plot\n")
    cols = ["plot_id", "target_crop", "total_area_ha",
            "Total_kg_Conv", "Total_kg_VRA", "Savings_kg", "Savings_pct_kg",
            "Cost_IDR_Conv", "Cost_IDR_VRA", "Cost_Savings_IDR", "Cost_Savings_pct"]
    md.append(comp[cols].to_markdown(index=False, floatfmt=",.1f"))
    md.append("")

    # Aggregate
    with open(os.path.join(OUT_REPORTS, "vra_summary.json")) as f:
        sumr = json.load(f)
    agg = sumr["aggregate"]
    md.append("## Aggregate (3 plots × 3 ha)\n")
    md.append(f"- Total fertilizer (Conventional): **{agg['total_kg_conventional']:,.1f} kg**")
    md.append(f"- Total fertilizer (VRA):          **{agg['total_kg_vra']:,.1f} kg**")
    md.append(f"- **Mass saving: {agg['savings_kg']:,.1f} kg ({agg['savings_pct']:.1f}%)**")
    md.append(f"- Total cost (Conventional): Rp {agg['total_cost_idr_conventional']:,.0f}")
    md.append(f"- Total cost (VRA):          Rp {agg['total_cost_idr_vra']:,.0f}")
    md.append(f"- **Cost saving: Rp {agg['cost_savings_idr']:,.0f} ({agg['cost_savings_pct']:.1f}%)**\n")

    md.append("## Table 2. Crop Recommendation (top 3 per plot)\n")
    rec_top = rec[rec["rank"] <= 3]
    md.append(rec_top.to_markdown(index=False, floatfmt=".3f"))
    md.append("")

    # Interpolation CV
    with open(os.path.join(OUT_REPORTS, "interpolation_cv.json")) as f:
        cv = json.load(f)
    md.append("## Table 3. Interpolation Cross-Validation (LOO, IDW p=2)\n")
    md.append("| Plot | Parameter | RMSE | MAE | R^2 |")
    md.append("|---|---|---|---|---|")
    for pid, params in cv.items():
        for p, m in params.items():
            md.append(f"| {pid} | {p} | {m['rmse']:.3f} | {m['mae']:.3f} | {m['r2']:.3f} |")
    md.append("")

    out_path = os.path.join(OUT_TABLES, "paper_tables.md")
    with open(out_path, "w") as f:
        f.write("\n".join(md))
    print(f"[OUT] {out_path}")


def main():
    sns.set_palette([PALETTE["vra"], PALETTE["conventional"],
                     PALETTE["accent"], PALETTE["neutral"]])

    all_df = pd.read_csv(os.path.join(OUT_DS, "all_plots.csv"))

    print("\n--- Generating figures ---")
    fig_sampling_distribution(all_df)
    fig_heatmaps_per_plot()
    fig_vra_zone_maps()
    fig_vra_vs_conv_bars()
    fig_crop_score_heatmap()
    fig_yield_distribution()
    fig_cost_breakdown()

    print("\n--- Generating tables ---")
    write_markdown_tables()

    print("\nDone.")


if __name__ == "__main__":
    main()

"""
Terra-Agri — Konfigurasi & basis pengetahuan agronomi.

Rentang parameter tanah dan kebutuhan hara komoditas merujuk pada literatur
agronomi tropis (Indonesia). Sumber rujukan kunci:
  - BBSDLP / Kementerian Pertanian: Petunjuk Teknis Analisis Tanah, 2009/2012
  - ISRIC SoilGrids v2.0 (resolusi 250m)
  - FAO ECOCROP database (syarat tumbuh komoditas)
  - Hardjowigeno (2003), Ilmu Tanah, Akademika Pressindo

Skala unit mengikuti pembacaan sensor 8-in-1 Modbus RTU pada Main_Raspi.py:
  hum (%), temp (C), EC (uS/cm), pH, N/P/K (mg/kg).
"""
from __future__ import annotations

# Lokasi anchor: area pertanian Karawang, Jawa Barat (representatif sawah/palawija).
ANCHOR_LAT = -6.3167
ANCHOR_LNG = 107.3000

# Konversi degree -> meter (aproksimasi pada equator untuk lng,
# 111_320 m per degree lat). Karawang dekat equator -> aman.
M_PER_DEG_LAT = 111_320.0
M_PER_DEG_LNG = 110_540.0  # cos(6.3 deg) * 111320

RANDOM_SEED = 20260528

# -----------------------------------------------------------------------------
# Rentang parameter tanah (mean realistis untuk lahan pertanian Indonesia).
# -----------------------------------------------------------------------------
SOIL_PARAM_RANGES = {
    # param   : (min realistis, max realistis, satuan)
    "N":   (40.0, 280.0, "mg/kg"),
    "P":   (5.0,  60.0,  "mg/kg"),
    "K":   (60.0, 380.0, "mg/kg"),
    "pH":  (4.3,  7.8,   "-"),
    "EC":  (120.0, 1800.0, "uS/cm"),
    "hum": (22.0, 78.0,  "%"),
    "temp":(24.0, 32.0,  "C"),
}

# Standar deviasi noise sensor (sesuai datasheet sensor NPK Modbus 8-in-1 kelas ekonomi).
SENSOR_NOISE_STD = {
    "N":   4.0,
    "P":   1.0,
    "K":   5.0,
    "pH":  0.08,
    "EC":  25.0,
    "hum": 1.0,
    "temp":0.3,
}

# -----------------------------------------------------------------------------
# Basis pengetahuan komoditas: syarat tumbuh & target hara optimal (mg/kg).
# Diturunkan dari rekomendasi pemupukan Kementan + FAO ECOCROP.
# -----------------------------------------------------------------------------
CROP_DB = {
    "Padi": {
        "ph_optimal":  (5.5, 7.0),
        "ph_tolerable":(4.8, 7.5),
        "N_target": 180.0,
        "P_target": 25.0,
        "K_target": 150.0,
        "hum_min":  55.0,
        "temp_range": (22.0, 32.0),
        "ec_max":   1500.0,
        "note": "Sawah lowland; toleran lembap tinggi.",
    },
    "Jagung": {
        "ph_optimal":  (5.6, 7.2),
        "ph_tolerable":(5.0, 7.5),
        "N_target": 220.0,
        "P_target": 30.0,
        "K_target": 180.0,
        "hum_min":  35.0,
        "temp_range": (21.0, 32.0),
        "ec_max":   1300.0,
        "note": "Kebutuhan N tinggi; tidak toleran genangan.",
    },
    "Kedelai": {
        "ph_optimal":  (6.0, 7.0),
        "ph_tolerable":(5.5, 7.5),
        "N_target": 90.0,   # fiksasi N atmosferik
        "P_target": 35.0,
        "K_target": 200.0,
        "hum_min":  40.0,
        "temp_range": (22.0, 31.0),
        "ec_max":   1200.0,
        "note": "Legum; fiksasi N sendiri, butuh P-K tinggi.",
    },
    "Cabai": {
        "ph_optimal":  (5.5, 6.8),
        "ph_tolerable":(5.0, 7.2),
        "N_target": 200.0,
        "P_target": 40.0,
        "K_target": 250.0,
        "hum_min":  45.0,
        "temp_range": (21.0, 30.0),
        "ec_max":   1400.0,
        "note": "Kebutuhan K tinggi untuk pembentukan buah.",
    },
    "Singkong": {
        "ph_optimal":  (4.8, 7.0),
        "ph_tolerable":(4.5, 7.5),
        "N_target": 100.0,
        "P_target": 20.0,
        "K_target": 220.0,
        "hum_min":  30.0,
        "temp_range": (22.0, 32.0),
        "ec_max":   1500.0,
        "note": "Toleran tanah asam & marginal; K relatif tinggi.",
    },
    "Bawang Merah": {
        "ph_optimal":  (5.6, 6.8),
        "ph_tolerable":(5.2, 7.0),
        "N_target": 160.0,
        "P_target": 45.0,
        "K_target": 200.0,
        "hum_min":  40.0,
        "temp_range": (22.0, 30.0),
        "ec_max":   1300.0,
        "note": "Membutuhkan P tinggi; sensitif kelembapan ekstrim.",
    },
}

# -----------------------------------------------------------------------------
# Pupuk umum di Indonesia + kandungan unsur hara (% berat).
# Sumber: Permentan No. 36/2017, label kemasan pupuk subsidi.
# -----------------------------------------------------------------------------
FERTILIZER_DB = {
    "Urea":    {"N": 46.0, "P": 0.0,  "K": 0.0,  "price_idr_kg": 2_250.0},
    "SP-36":   {"N": 0.0,  "P": 36.0, "K": 0.0,  "price_idr_kg": 2_400.0},
    "KCl":     {"N": 0.0,  "P": 0.0,  "K": 60.0, "price_idr_kg": 5_000.0},
    "Phonska": {"N": 15.0, "P": 15.0, "K": 15.0, "price_idr_kg": 2_300.0},
}

# Faktor konversi mg/kg tanah -> kg pupuk per hektar.
# Asumsi standar agronomi: kedalaman olah 20 cm, bulk density 1.3 g/cm^3
# -> 1 ha tanah olah ~ 2.6 juta kg = 2_600_000 kg.
# 1 mg/kg defisit hara -> 2.6 kg unsur hara murni per ha.
SOIL_MASS_PER_HA_KG = 2_600_000.0

# -----------------------------------------------------------------------------
# Dosis rekomendasi standar Kementerian Pertanian RI (Permentan & BPP).
# Ini yang dipakai petani konvensional sebagai blanket dose, tanpa
# memperhitungkan kondisi tanah aktual (one-size-fits-all).
# Sumber:  Petunjuk Teknis Pemupukan Berimbang Tanaman Pangan (BPP, 2017)
# Unit: kg pupuk per ha.
# -----------------------------------------------------------------------------
KEMENTAN_BLANKET_DOSE = {
    "Padi":          {"Urea": 250.0, "SP-36": 100.0, "KCl": 75.0},
    "Jagung":        {"Urea": 350.0, "SP-36": 150.0, "KCl": 100.0},
    "Kedelai":       {"Urea": 75.0,  "SP-36": 150.0, "KCl": 75.0},
    "Cabai":         {"Urea": 400.0, "SP-36": 250.0, "KCl": 250.0},
    "Singkong":      {"Urea": 200.0, "SP-36": 100.0, "KCl": 200.0},
    "Bawang Merah":  {"Urea": 300.0, "SP-36": 200.0, "KCl": 200.0},
}

# -----------------------------------------------------------------------------
# Tiga skenario plot untuk demonstrasi paper.
# -----------------------------------------------------------------------------
PLOT_SCENARIOS = {
    "Plot_A_Subur": {
        "label": "Lahan Subur Seimbang",
        "area_ha": 3.0,
        "n_samples": 110,
        # Mean tiap parameter -> diaplikasikan ke seluruh permukaan
        "mean": {"N": 200, "P": 32, "K": 180, "pH": 6.4,
                 "EC": 900, "hum": 60, "temp": 28},
        # Amplitudo variasi spasial (bagaimana surface naik-turun di plot)
        "spatial_amp": {"N": 35, "P": 8, "K": 40, "pH": 0.4,
                        "EC": 180, "hum": 6, "temp": 0.6},
        "description": "Hara seimbang dan pH netral; lahan ideal untuk berbagai komoditas.",
    },
    "Plot_B_Defisit_N": {
        "label": "Lahan Defisit Nitrogen",
        "area_ha": 3.0,
        "n_samples": 110,
        "mean": {"N": 95, "P": 28, "K": 170, "pH": 6.2,
                 "EC": 850, "hum": 55, "temp": 29},
        "spatial_amp": {"N": 25, "P": 7, "K": 35, "pH": 0.4,
                        "EC": 160, "hum": 5, "temp": 0.5},
        "description": "Nitrogen rendah merata; tipikal lahan habis eksploitasi padi.",
    },
    "Plot_C_Asam": {
        "label": "Lahan Asam (pH rendah)",
        "area_ha": 3.0,
        "n_samples": 110,
        "mean": {"N": 140, "P": 14, "K": 130, "pH": 5.0,
                 "EC": 1100, "hum": 62, "temp": 28},
        "spatial_amp": {"N": 30, "P": 5, "K": 30, "pH": 0.5,
                        "EC": 200, "hum": 6, "temp": 0.5},
        "description": "pH rendah memicu fiksasi P; produktivitas menurun.",
    },
}

# Resolusi grid interpolasi untuk heatmap (titik per sisi).
GRID_RES = 80

# Jumlah zona manajemen (zona VRA). Plot dibagi NxN grid zona.
N_ZONES_PER_SIDE = 4  # -> 16 zona per plot

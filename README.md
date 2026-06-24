# AW-GOES-TO-JAPAN

Proyek **Terra-Agri / AgriWand** — alat pencatat data pertanian lapangan berbasis
Raspberry Pi, untuk kompetisi di Jepang. Merekam data sensor (Modbus) dan posisi
GPS, dipicu lewat tombol fisik, lalu disimpan sebagai JSON.

## Isi

| Path | Isi |
|---|---|
| `Main_Raspi.py` | Program utama Raspberry Pi: GPS, sensor Modbus, perekaman via tombol |
| `UIAgriWand/` | Antarmuka pengguna AgriWand |
| `data/`, `paper_data/` | Data hasil rekaman / data paper |
| `Terra-Agri_Abstract.docx` | Abstrak |

## Jalankan (di Raspberry Pi)

```bash
pip install RPi.GPIO minimalmodbus pyserial
python Main_Raspi.py
```

Data tersimpan di `~/agri_data/`. Konfigurasi port GPS/Modbus ada di bagian
atas `Main_Raspi.py`.

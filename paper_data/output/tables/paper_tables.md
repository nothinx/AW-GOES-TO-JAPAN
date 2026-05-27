# Terra-Agri — Paper Tables

> Synthetic validation dataset. Field deployment planned as future work.

## Table 1. VRA vs Conventional — per Plot

| plot_id          | target_crop   |   total_area_ha |   Total_kg_Conv |   Total_kg_VRA |   Savings_kg |   Savings_pct_kg |   Cost_IDR_Conv |   Cost_IDR_VRA |   Cost_Savings_IDR |   Cost_Savings_pct |
|:-----------------|:--------------|----------------:|----------------:|---------------:|-------------:|-----------------:|----------------:|---------------:|-------------------:|-------------------:|
| Plot_A_Subur     | Padi          |             3.0 |         1,275.0 |            0.0 |      1,275.0 |            100.0 |     3,532,500.0 |            0.0 |        3,532,500.0 |              100.0 |
| Plot_B_Defisit_N | Singkong      |             3.0 |         1,500.0 |          990.3 |        509.7 |             34.0 |     5,070,000.0 |    4,518,703.0 |          551,297.0 |               10.9 |
| Plot_C_Asam      | Singkong      |             3.0 |         1,500.0 |        1,111.0 |        389.0 |             25.9 |     5,070,000.0 |    5,241,226.0 |         -171,226.0 |               -3.4 |

## Aggregate (3 plots × 3 ha)

- Total fertilizer (Conventional): **4,275.0 kg**
- Total fertilizer (VRA):          **2,101.3 kg**
- **Mass saving: 2,173.7 kg (50.9%)**
- Total cost (Conventional): Rp 13,672,500
- Total cost (VRA):          Rp 9,759,929
- **Cost saving: Rp 3,912,571 (28.6%)**

## Table 2. Crop Recommendation (top 3 per plot)

| plot_id          |   rank | crop     |   total_score |   pH_score |   N_score |   P_score |   K_score |   hum_score |   temp_score |   EC_score |
|:-----------------|-------:|:---------|--------------:|-----------:|----------:|----------:|----------:|------------:|-------------:|-----------:|
| Plot_A_Subur     |      1 | Padi     |         1.000 |      1.000 |     1.000 |     1.000 |     1.000 |       1.000 |        1.000 |      1.000 |
| Plot_A_Subur     |      2 | Jagung   |         0.988 |      1.000 |     0.958 |     0.995 |     0.970 |       1.000 |        1.000 |      1.000 |
| Plot_A_Subur     |      3 | Singkong |         0.969 |      1.000 |     1.000 |     1.000 |     0.793 |       1.000 |        1.000 |      1.000 |
| Plot_B_Defisit_N |      1 | Singkong |         0.943 |      1.000 |     0.910 |     1.000 |     0.709 |       1.000 |        1.000 |      1.000 |
| Plot_B_Defisit_N |      2 | Kedelai  |         0.936 |      1.000 |     1.000 |     0.795 |     0.780 |       1.000 |        1.000 |      1.000 |
| Plot_B_Defisit_N |      3 | Padi     |         0.926 |      1.000 |     0.505 |     1.000 |     1.000 |       1.000 |        1.000 |      1.000 |
| Plot_C_Asam      |      1 | Singkong |         0.906 |      1.000 |     1.000 |     0.721 |     0.654 |       1.000 |        1.000 |      1.000 |
| Plot_C_Asam      |      2 | Padi     |         0.703 |      0.236 |     0.757 |     0.577 |     0.959 |       1.000 |        1.000 |      1.000 |
| Plot_C_Asam      |      3 | Kedelai  |         0.620 |      0.000 |     1.000 |     0.412 |     0.719 |       1.000 |        1.000 |      1.000 |

## Table 3. Interpolation Cross-Validation (LOO, IDW p=2)

| Plot | Parameter | RMSE | MAE | R^2 |
|---|---|---|---|---|
| Plot_A_Subur | N | 6.647 | 5.308 | 0.836 |
| Plot_A_Subur | P | 1.471 | 1.114 | 0.779 |
| Plot_A_Subur | K | 9.242 | 7.291 | 0.769 |
| Plot_A_Subur | pH | 0.109 | 0.092 | 0.719 |
| Plot_A_Subur | EC | 46.107 | 34.145 | 0.648 |
| Plot_A_Subur | hum | 1.364 | 1.093 | 0.743 |
| Plot_A_Subur | temp | 0.361 | 0.290 | 0.266 |
| Plot_B_Defisit_N | N | 7.735 | 5.983 | 0.607 |
| Plot_B_Defisit_N | P | 1.541 | 1.231 | 0.770 |
| Plot_B_Defisit_N | K | 7.415 | 5.707 | 0.759 |
| Plot_B_Defisit_N | pH | 0.094 | 0.076 | 0.768 |
| Plot_B_Defisit_N | EC | 33.163 | 26.418 | 0.764 |
| Plot_B_Defisit_N | hum | 1.203 | 0.980 | 0.327 |
| Plot_B_Defisit_N | temp | 0.341 | 0.265 | -0.026 |
| Plot_C_Asam | N | 6.651 | 5.047 | 0.760 |
| Plot_C_Asam | P | 1.468 | 1.197 | 0.578 |
| Plot_C_Asam | K | 6.487 | 5.375 | 0.675 |
| Plot_C_Asam | pH | 0.123 | 0.094 | 0.565 |
| Plot_C_Asam | EC | 44.390 | 33.476 | 0.774 |
| Plot_C_Asam | hum | 1.423 | 1.125 | 0.698 |
| Plot_C_Asam | temp | 0.291 | 0.232 | 0.175 |

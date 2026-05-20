#include "ExtButton.h"

static bool time_synced = false;  // Flag: waktu sudah disinkronkan dari Raspi
static bool is_recording = false; // Flag: sedang dalam mode recording
static unsigned long recording_start_sec = 0; // Detik saat recording dimulai

HardwareSerial SensorSerial(1);

static int total_pinpoints = 0;  // Raspi tidak kirim ini, hitung lokal
static lv_timer_t *saved_panel_timer = NULL;  // Timer auto-hide SavedPanel

// Callback: auto-hide SavedPanel setelah timeout
static void saved_panel_timer_cb(lv_timer_t *timer) {
  if (ui_SavedPanel) lv_obj_add_flag(ui_SavedPanel, LV_OBJ_FLAG_HIDDEN);
  if (saved_panel_timer) {
    lv_timer_del(saved_panel_timer);
    saved_panel_timer = NULL;
  }
}

// Helper: tampilkan SavedPanel dengan pesan, auto-hide setelah 1.5 detik
static void ShowSavedPanel(const char *msg) {
  if (!ui_SavedPanel || !ui_SavedSuccessLabel) return;
  lv_label_set_text(ui_SavedSuccessLabel, msg);
  lv_obj_clear_flag(ui_SavedPanel, LV_OBJ_FLAG_HIDDEN);
  // Hapus timer lama jika masih aktif
  if (saved_panel_timer) {
    lv_timer_del(saved_panel_timer);
  }
  saved_panel_timer = lv_timer_create(saved_panel_timer_cb, 1500, NULL);
  lv_timer_set_repeat_count(saved_panel_timer, 1);  // Hanya sekali
}

// Helper: ambil nilai dari format "KEY=VALUE" dalam string DATA
// Fixed: cek boundary agar "N=" tidak match "RAIN=" dll
static String parseField(const String& data, const char* key) {
  // Cari "|KEY=" (field di tengah/akhir)
  String pipeSearch = String("|") + key + "=";
  int start = data.indexOf(pipeSearch);
  if (start != -1) {
    start += pipeSearch.length();
  } else {
    // Cari "KEY=" di awal string (field pertama)
    String startSearch = String(key) + "=";
    if (data.startsWith(startSearch)) {
      start = startSearch.length();
    } else {
      return "0";
    }
  }
  int end = data.indexOf('|', start);
  if (end == -1) end = data.length();
  return data.substring(start, end);
}

// Helper: update indikator recording di Overview
static void UpdateRecordingIndicator() {
  if (!ui_PinpointLabel || !ui_OverviewPanel) return;
  if (is_recording) {
    // Single line — clock timer akan update "REC MM:SS" setiap detik
    lv_label_set_text(ui_PinpointLabel, "REC 00:00");
    // Border merah saat recording
    lv_obj_set_style_border_color(ui_OverviewPanel, lv_color_hex(0xDC2626), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_border_width(ui_OverviewPanel, 3, LV_PART_MAIN | LV_STATE_DEFAULT);
  } else {
    lv_label_set_text(ui_PinpointLabel, "Pinpoint(s)\nCreated");
    // Border kembali ke warna background (tidak terlihat)
    lv_obj_set_style_border_color(ui_OverviewPanel, lv_color_hex(0x196B3B), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_border_width(ui_OverviewPanel, 1, LV_PART_MAIN | LV_STATE_DEFAULT);
  }
}

// Helper: update GPS status di Overview
static void UpdateGPSStatus(int gps_valid) {
  if (!ui_GPSStatus) return;
  if (gps_valid) {
    lv_label_set_text(ui_GPSStatus, "GPS OK");
    lv_obj_set_style_text_color(ui_GPSStatus, lv_color_hex(0x10B981), LV_PART_MAIN | LV_STATE_DEFAULT);
  } else {
    lv_label_set_text(ui_GPSStatus, "NO GPS");
    lv_obj_set_style_text_color(ui_GPSStatus, lv_color_hex(0xDC2626), LV_PART_MAIN | LV_STATE_DEFAULT);
  }
}

static void Update_UI(const String& raw) {
  // Guard: jangan update jika widget belum ada / sudah di-destroy
  if (!ui_TempValue || !ui_NBar || !ui_PBar || !ui_KBar) return;

  // Sembunyikan SavedPanel (loading indicator) saat data masuk
  if (ui_SavedPanel) lv_obj_add_flag(ui_SavedPanel, LV_OBJ_FLAG_HIDDEN);

  // Update label nilai sensor di Overview
  String data = raw.substring(5);  // Hapus "DATA:"

  float temp = parseField(data, "T").toFloat();
  float hum = parseField(data, "H").toFloat();
  float ph = parseField(data, "PH").toFloat();
  int ec = parseField(data, "EC").toInt();
  int n = parseField(data, "N").toInt();
  int p = parseField(data, "P").toInt();
  int k = parseField(data, "K").toInt();
  int gps = parseField(data, "GPS").toInt();

  // Update GPS indicator
  UpdateGPSStatus(gps);

  char buf[16];

  snprintf(buf, sizeof(buf), "%.1f°", temp);
  lv_label_set_text(ui_TempValue, buf);
  lv_arc_set_value(ui_TempArc, (int)temp);
  if (temp >= 20.0 && temp < 32.0) {
    lv_obj_set_style_arc_color(ui_TempArc, lv_color_hex(0x10B981), LV_PART_INDICATOR | LV_STATE_DEFAULT);  // Green
  } else if (temp >= 32.0) {
    lv_obj_set_style_arc_color(ui_TempArc, lv_color_hex(0xDC2626), LV_PART_INDICATOR | LV_STATE_DEFAULT);  // Red
  } else {
    lv_obj_set_style_arc_color(ui_TempArc, lv_color_hex(0x3B82F6), LV_PART_INDICATOR | LV_STATE_DEFAULT);  // Blue
  }

  snprintf(buf, sizeof(buf), "%.1f%%", hum);
  lv_label_set_text(ui_HumValue, buf);
  lv_arc_set_value(ui_HumArc, (int)hum);
  if (hum >= 40.0 && hum < 80.0) {
    lv_obj_set_style_arc_color(ui_HumArc, lv_color_hex(0x10B981), LV_PART_INDICATOR | LV_STATE_DEFAULT);
  } else if (hum >= 80.0) {
    lv_obj_set_style_arc_color(ui_HumArc, lv_color_hex(0xDC2626), LV_PART_INDICATOR | LV_STATE_DEFAULT);
  } else if (hum >= 30 && hum < 40) {
    lv_obj_set_style_arc_color(ui_HumArc, lv_color_hex(0xF59E0B), LV_PART_INDICATOR | LV_STATE_DEFAULT);
  } else {
    lv_obj_set_style_arc_color(ui_HumArc, lv_color_hex(0xDC2626), LV_PART_INDICATOR | LV_STATE_DEFAULT);
  }


  snprintf(buf, sizeof(buf), "%.1f", ph);
  lv_label_set_text(ui_pHValue, buf);
  if (ph >= 0 && ph < 0.75) {
    lv_obj_set_style_bg_color(ui_pHPanel, lv_color_hex(0xEF1C23), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_border_color(ui_pHPanel, lv_color_hex(0xDC2626), LV_PART_MAIN | LV_STATE_DEFAULT);
  } else if (ph >= 0.75 && ph < 1.5) {
    lv_obj_set_style_bg_color(ui_pHPanel, lv_color_hex(0xFF7B17), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_border_color(ui_pHPanel, lv_color_hex(0xDC2626), LV_PART_MAIN | LV_STATE_DEFAULT);
  } else if (ph >= 1.5 && ph < 2.5) {
    lv_obj_set_style_bg_color(ui_pHPanel, lv_color_hex(0xF4C714), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_border_color(ui_pHPanel, lv_color_hex(0xDC2626), LV_PART_MAIN | LV_STATE_DEFAULT);
  } else if (ph >= 2.5 && ph < 3.5) {
    lv_obj_set_style_bg_color(ui_pHPanel, lv_color_hex(0xF7E401), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_border_color(ui_pHPanel, lv_color_hex(0xDC2626), LV_PART_MAIN | LV_STATE_DEFAULT);
  } else if (ph >= 3.5 && ph < 4.5) {
    lv_obj_set_style_bg_color(ui_pHPanel, lv_color_hex(0xB8D434), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_border_color(ui_pHPanel, lv_color_hex(0xDC2626), LV_PART_MAIN | LV_STATE_DEFAULT);
  } else if (ph >= 4.5 && ph < 5.5) {
    lv_obj_set_style_bg_color(ui_pHPanel, lv_color_hex(0x86C141), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_border_color(ui_pHPanel, lv_color_hex(0xF59E0B), LV_PART_MAIN | LV_STATE_DEFAULT);
  } else if (ph >= 5.5 && ph < 6.5) {
    lv_obj_set_style_bg_color(ui_pHPanel, lv_color_hex(0x51B94A), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_border_color(ui_pHPanel, lv_color_hex(0x10B981), LV_PART_MAIN | LV_STATE_DEFAULT);
  } else if (ph >= 6.5 && ph < 7.5) {
    lv_obj_set_style_bg_color(ui_pHPanel, lv_color_hex(0x36AA45), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_border_color(ui_pHPanel, lv_color_hex(0x10B981), LV_PART_MAIN | LV_STATE_DEFAULT);
  } else if (ph >= 7.5 && ph < 8.5) {
    lv_obj_set_style_bg_color(ui_pHPanel, lv_color_hex(0x24B46F), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_border_color(ui_pHPanel, lv_color_hex(0xF59E0B), LV_PART_MAIN | LV_STATE_DEFAULT);
  } else if (ph >= 8.5 && ph < 9.5) {
    lv_obj_set_style_bg_color(ui_pHPanel, lv_color_hex(0x0ABAB7), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_border_color(ui_pHPanel, lv_color_hex(0xDC2626), LV_PART_MAIN | LV_STATE_DEFAULT);
  } else if (ph >= 9.5 && ph < 10.5) {
    lv_obj_set_style_bg_color(ui_pHPanel, lv_color_hex(0x4690CD), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_border_color(ui_pHPanel, lv_color_hex(0xDC2626), LV_PART_MAIN | LV_STATE_DEFAULT);
  } else if (ph >= 10.5 && ph < 11.5) {
    lv_obj_set_style_bg_color(ui_pHPanel, lv_color_hex(0x3A54A1), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_border_color(ui_pHPanel, lv_color_hex(0xDC2626), LV_PART_MAIN | LV_STATE_DEFAULT);
  } else if (ph >= 11.5 && ph < 12.5) {
    lv_obj_set_style_bg_color(ui_pHPanel, lv_color_hex(0x59509F), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_border_color(ui_pHPanel, lv_color_hex(0xDC2626), LV_PART_MAIN | LV_STATE_DEFAULT);
  } else if (ph >= 12.5 && ph < 13.25) {
    lv_obj_set_style_bg_color(ui_pHPanel, lv_color_hex(0x63459D), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_border_color(ui_pHPanel, lv_color_hex(0xDC2626), LV_PART_MAIN | LV_STATE_DEFAULT);
  } else {
    lv_obj_set_style_bg_color(ui_pHPanel, lv_color_hex(0x422E83), LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_border_color(ui_pHPanel, lv_color_hex(0xDC2626), LV_PART_MAIN | LV_STATE_DEFAULT);
  }

  snprintf(buf, sizeof(buf), "%d uS/cm", ec);
  lv_label_set_text(ui_ECValue, buf);
  if (ec >= 200 && ec < 800) {
    lv_obj_set_style_outline_color(ui_ECValue, lv_color_hex(0xF59E0B), LV_PART_MAIN | LV_STATE_DEFAULT);
  } else if (ec >= 800 && ec < 1500) {
    lv_obj_set_style_outline_color(ui_ECValue, lv_color_hex(0x10B981), LV_PART_MAIN | LV_STATE_DEFAULT);
  } else if (ec >= 1500) {
    lv_obj_set_style_outline_color(ui_ECValue, lv_color_hex(0xF59E0B), LV_PART_MAIN | LV_STATE_DEFAULT);
  } else {
    lv_obj_set_style_outline_color(ui_ECValue, lv_color_hex(0xDC2626), LV_PART_MAIN | LV_STATE_DEFAULT);
  }

  snprintf(buf, sizeof(buf), "%d mg/kg", n);
  lv_label_set_text(ui_NValue, buf);
  lv_bar_set_value(ui_NBar, n, LV_ANIM_OFF);
  if (n >= 40) {
    lv_obj_set_style_bg_color(ui_NBar, lv_color_hex(0x10B981), LV_PART_INDICATOR | LV_STATE_DEFAULT);
  } else if (n >= 30 && n < 40) {
    lv_obj_set_style_bg_color(ui_NBar, lv_color_hex(0xF59E0B), LV_PART_INDICATOR | LV_STATE_DEFAULT);
  } else {
    lv_obj_set_style_bg_color(ui_NBar, lv_color_hex(0xDC2626), LV_PART_INDICATOR | LV_STATE_DEFAULT);
  }

  snprintf(buf, sizeof(buf), "%d mg/kg", p);
  lv_label_set_text(ui_PValue, buf);
  lv_bar_set_value(ui_PBar, p, LV_ANIM_OFF);
  if (p >= 20) {
    lv_obj_set_style_bg_color(ui_PBar, lv_color_hex(0x10B981), LV_PART_INDICATOR | LV_STATE_DEFAULT);
  } else if (p >= 10 && p < 20) {
    lv_obj_set_style_bg_color(ui_PBar, lv_color_hex(0xF59E0B), LV_PART_INDICATOR | LV_STATE_DEFAULT);
  } else {
    lv_obj_set_style_bg_color(ui_PBar, lv_color_hex(0xDC2626), LV_PART_INDICATOR | LV_STATE_DEFAULT);
  }

  snprintf(buf, sizeof(buf), "%d mg/kg", k);
  lv_label_set_text(ui_KValue, buf);
  lv_bar_set_value(ui_KBar, k, LV_ANIM_OFF);
  if (k >= 30) {
    lv_obj_set_style_bg_color(ui_KBar, lv_color_hex(0x10B981), LV_PART_INDICATOR | LV_STATE_DEFAULT);
  } else if (k >= 20 && k < 30) {
    lv_obj_set_style_bg_color(ui_KBar, lv_color_hex(0xF59E0B), LV_PART_INDICATOR | LV_STATE_DEFAULT);
  } else {
    lv_obj_set_style_bg_color(ui_KBar, lv_color_hex(0xDC2626), LV_PART_INDICATOR | LV_STATE_DEFAULT);
  }

  // Update jumlah pinpoint
  total_pinpoints++;
  lv_label_set_text_fmt(ui_PinpointValue, "%d", total_pinpoints);

  char time_buf[10];
  snprintf(time_buf, sizeof(time_buf), "%02d:%02d:%02d",
           datetime.hour, datetime.minute, datetime.second);
  lv_label_set_text(ui_PinpointTime, time_buf);

  Serial.println("UI updated from latest dataset entry");
}

void ExtButton_ResetPinpoints() {
  total_pinpoints = 0;
}

void ExtButton_Init() {
  SensorSerial.begin(9600, SERIAL_8N1, RX_PIN, TX_PIN);
  SensorSerial.setTimeout(200);  // Cegah 1s freeze jika data corrupt
  Serial.println("ExtButton Serial ready");
}

void ExtButton_Loop() {
  if (SensorSerial.available() > 0) {
    String raw = SensorSerial.readStringUntil('\n');
    raw.trim();

    Serial.printf("[RX] %s\n", raw.c_str());

    // ---- DATA: Recording mode → Update UI + increment pinpoint ----
    if (raw.startsWith("DATA:")) {
      Update_UI(raw);
    }
    // ---- PREVIEW: Live preview mode → Update UI saja, TANPA increment ----
    else if (raw.startsWith("PREVIEW:")) {
      // Reformat menjadi "DATA:" agar Update_UI bisa parse
      String asData = "DATA:" + raw.substring(8);
      // Simpan pinpoint counter, lalu restore setelah Update_UI
      int saved = total_pinpoints;
      Update_UI(asData);
      total_pinpoints = saved;
      lv_label_set_text_fmt(ui_PinpointValue, "%d", total_pinpoints);
      Serial.println("[PREVIEW] UI updated (no pinpoint increment)");
    }
    // ---- MSG:READING → Sedang baca sensor, tampilkan loading ----
    else if (raw == "MSG:READING") {
      ShowSavedPanel("Reading\nsensor...");
    }
    // ---- MSG:BTN_HELD → Tombol ditahan, feedback visual ----
    else if (raw == "MSG:BTN_HELD") {
      if (is_recording) {
        ShowSavedPanel("Hold to\nsave...");
      }
    }
    // ---- MSG:REC_STARTED → Recording berhasil dimulai ----
    else if (raw == "MSG:REC_STARTED") {
      is_recording = true;
      recording_start_sec = (unsigned long)datetime.hour * 3600UL + datetime.minute * 60UL + datetime.second;
      ExtButton_ResetPinpoints();
      lv_label_set_text(ui_PinpointValue, "0");
      UpdateRecordingIndicator();
      // Auto-navigate ke Overview screen
      if (ui_TabViewOverview) lv_tabview_set_act(ui_TabViewOverview, 0, LV_ANIM_OFF);
      if (ui_PageIndicator1) {
        lv_obj_set_style_bg_color(ui_PageIndicator1, lv_color_hex(0xFF6D00), LV_PART_MAIN | LV_STATE_DEFAULT);
        lv_obj_set_style_border_color(ui_PageIndicator1, lv_color_hex(0xFF6D00), LV_PART_MAIN | LV_STATE_DEFAULT);
      }
      if (ui_PageIndicator2) {
        lv_obj_set_style_bg_color(ui_PageIndicator2, lv_color_hex(0xFFFFFF), LV_PART_MAIN | LV_STATE_DEFAULT);
        lv_obj_set_style_border_color(ui_PageIndicator2, lv_color_hex(0xFFFFFF), LV_PART_MAIN | LV_STATE_DEFAULT);
      }
      _ui_screen_change(&ui_Overview, LV_SCR_LOAD_ANIM_FADE_ON, 100, 0, &ui_Overview_screen_init);
      if (ui_SavedPanel) _ui_flag_modify(ui_SavedPanel, LV_OBJ_FLAG_HIDDEN, _UI_MODIFY_FLAG_ADD);
      if (ui_SaveButton) _ui_flag_modify(ui_SaveButton, LV_OBJ_FLAG_HIDDEN, _UI_MODIFY_FLAG_REMOVE);
      ShowSavedPanel("Recording\nStarted!");
      Serial.println("[STATE] Recording started (auto-navigate)");
    }
    // ---- MSG:ALREADY_REC → Start ditolak, sudah recording ---- 1' 
    else if (raw == "MSG:ALREADY_REC") {
      ShowSavedPanel("Already\nRecording!");
      Serial.println("[UX] Already recording, ignored");
    }
    // ---- MSG:FILE_SAVED → File berhasil disimpan ---- 3
    else if (raw == "MSG:FILE_SAVED") {
      // Hitung summary sebelum reset
      unsigned long now_sec = (unsigned long)datetime.hour * 3600UL + datetime.minute * 60UL + datetime.second;
      unsigned long elapsed = now_sec >= recording_start_sec
          ? now_sec - recording_start_sec
          : (86400UL - recording_start_sec) + now_sec;
      int mins = elapsed / 60;
      int secs = elapsed % 60;
      int pts = total_pinpoints;

      is_recording = false;
      ExtButton_ResetPinpoints();
      if (ui_PinpointValue) lv_label_set_text(ui_PinpointValue, "0");
      UpdateRecordingIndicator();

      // Tampilkan summary: "3 pts saved · 05:23"
      char summary[40];
      snprintf(summary, sizeof(summary), "%d pts saved\n%02d:%02d elapsed", pts, mins, secs);
      ShowSavedPanel(summary);

      // Navigate ke MainMenu setelah pesan tampil
      _ui_screen_change(&ui_MainMenu, LV_SCR_LOAD_ANIM_FADE_ON, 100, 1500, &ui_MainMenu_screen_init);
    }
    // ---- MSG:EMPTY_SESSION → Stop tapi tidak ada data ---- 3'
    else if (raw == "MSG:EMPTY_SESSION") {
      is_recording = false;
      UpdateRecordingIndicator();
      ShowSavedPanel("No data\nto save!");
      // Navigate ke MainMenu
      _ui_screen_change(&ui_MainMenu, LV_SCR_LOAD_ANIM_FADE_ON, 100, 1500, &ui_MainMenu_screen_init);
    }
    // ---- MSG:NOT_REC → Stop/Save ditolak, belum recording ----
    else if (raw == "MSG:NOT_REC") {
      ShowSavedPanel("Not recording!\nStart first.");
      Serial.println("[UX] Not recording, ignored");
    }
    // ---- ERR:SOIL_TIMEOUT → Sensor gagal dibaca ----
    else if (raw == "ERR:SOIL_TIMEOUT") {
      ShowSavedPanel("Sensor error!\nRetry.");
    }
    // ---- TIME: → Sinkronisasi waktu dari Raspi ----
    else if (raw.startsWith("TIME:")) {
      // Format: TIME:year,month,day,dotw,hour,minute,second
      String payload = raw.substring(5);
      int values[7] = {0};
      int idx = 0;
      int start = 0;
      for (int i = 0; i <= (int)payload.length() && idx < 7; i++) {
        if (i == (int)payload.length() || payload.charAt(i) == ',') {
          values[idx++] = payload.substring(start, i).toInt();
          start = i + 1;
        }
      }
      if (idx == 7) {
        datetime_t sync_time = {0};
        sync_time.year   = (uint16_t)values[0];
        sync_time.month  = (uint8_t)values[1];
        sync_time.day    = (uint8_t)values[2];
        sync_time.dotw   = (uint8_t)values[3];
        sync_time.hour   = (uint8_t)values[4];
        sync_time.minute = (uint8_t)values[5];
        sync_time.second = (uint8_t)values[6];
        PCF85063_Set_All(sync_time);
        time_synced = true;
        Serial.printf("[RTC] Time synced: %04d-%02d-%02d %02d:%02d:%02d (dotw=%d)\n",
                      sync_time.year, sync_time.month, sync_time.day,
                      sync_time.hour, sync_time.minute, sync_time.second,
                      sync_time.dotw);
      } else {
        Serial.printf("[RTC ERR] Invalid TIME format, got %d fields\n", idx);
      }
    }
    // ---- HIST_START: → Mulai menerima daftar history ----
    else if (raw.startsWith("HIST_START:")) {
      // Bersihkan list lama
      if (ui_HistoryList) {
        lv_obj_clean(ui_HistoryList);
      }
      // Tampilkan status loading
      if (ui_HistoryStatus) {
        ui_HistoryStatus = lv_label_create(ui_HistoryList);
        lv_label_set_text(ui_HistoryStatus, "Loading...");
        lv_obj_set_style_text_color(ui_HistoryStatus, lv_color_hex(0x888888), LV_PART_MAIN | LV_STATE_DEFAULT);
        lv_obj_set_style_text_font(ui_HistoryStatus, &lv_font_montserrat_16, LV_PART_MAIN | LV_STATE_DEFAULT);
      }
      Serial.println("[HIST] List cleared, receiving items...");
    }
    // ---- HIST_ITEM: → Satu item history ----
    // Format: HIST_ITEM:date_str|points|duration_min
    else if (raw.startsWith("HIST_ITEM:")) {
      String payload = raw.substring(10);
      // Parse: "20 May 2026 14:30|5|12"
      int sep1 = payload.indexOf('|');
      int sep2 = payload.lastIndexOf('|');
      if (sep1 != -1 && sep2 != sep1) {
        String dateStr = payload.substring(0, sep1);
        int points = payload.substring(sep1 + 1, sep2).toInt();
        int dur_min = payload.substring(sep2 + 1).toInt();

        // Hapus status label jika masih ada
        if (ui_HistoryStatus) {
          lv_obj_del(ui_HistoryStatus);
          ui_HistoryStatus = NULL;
        }

        // Buat card untuk item ini
        if (ui_HistoryList) {
          lv_obj_t *card = lv_obj_create(ui_HistoryList);
          lv_obj_set_width(card, 290);
          lv_obj_set_height(card, LV_SIZE_CONTENT);
          lv_obj_set_style_radius(card, 10, LV_PART_MAIN | LV_STATE_DEFAULT);
          lv_obj_set_style_bg_color(card, lv_color_hex(0x1A3A2A), LV_PART_MAIN | LV_STATE_DEFAULT);
          lv_obj_set_style_bg_opa(card, 255, LV_PART_MAIN | LV_STATE_DEFAULT);
          lv_obj_set_style_border_color(card, lv_color_hex(0x2F7C4E), LV_PART_MAIN | LV_STATE_DEFAULT);
          lv_obj_set_style_border_width(card, 1, LV_PART_MAIN | LV_STATE_DEFAULT);
          lv_obj_set_style_pad_all(card, 10, LV_PART_MAIN | LV_STATE_DEFAULT);
          lv_obj_clear_flag(card, LV_OBJ_FLAG_SCROLLABLE);
          lv_obj_set_flex_flow(card, LV_FLEX_FLOW_COLUMN);
          lv_obj_set_style_pad_row(card, 4, LV_PART_MAIN | LV_STATE_DEFAULT);

          // Baris 1: Tanggal
          lv_obj_t *dateLabel = lv_label_create(card);
          lv_label_set_text(dateLabel, dateStr.c_str());
          lv_obj_set_style_text_color(dateLabel, lv_color_hex(0xFFFFFF), LV_PART_MAIN | LV_STATE_DEFAULT);
          lv_obj_set_style_text_font(dateLabel, &lv_font_montserrat_16, LV_PART_MAIN | LV_STATE_DEFAULT);

          // Baris 2: Points + Duration
          char infoStr[40];
          snprintf(infoStr, sizeof(infoStr), "%d pts  |  %d min", points, dur_min);
          lv_obj_t *infoLabel = lv_label_create(card);
          lv_label_set_text(infoLabel, infoStr);
          lv_obj_set_style_text_color(infoLabel, lv_color_hex(0x10B981), LV_PART_MAIN | LV_STATE_DEFAULT);
          lv_obj_set_style_text_font(infoLabel, &lv_font_montserrat_16, LV_PART_MAIN | LV_STATE_DEFAULT);
        }
        Serial.printf("[HIST] Item: %s, %d pts, %d min\n", dateStr.c_str(), points, dur_min);
      }
    }
    // ---- HIST_END: → Selesai menerima history ----
    else if (raw.startsWith("HIST_END:")) {
      int total = raw.substring(9).toInt();
      if (total == 0 && ui_HistoryList) {
        // Hapus status loading jika masih ada
        if (ui_HistoryStatus) {
          lv_obj_del(ui_HistoryStatus);
          ui_HistoryStatus = NULL;
        }
        // Tampilkan pesan kosong
        ui_HistoryStatus = lv_label_create(ui_HistoryList);
        lv_label_set_text(ui_HistoryStatus, "No recordings yet");
        lv_obj_set_style_text_color(ui_HistoryStatus, lv_color_hex(0x888888), LV_PART_MAIN | LV_STATE_DEFAULT);
        lv_obj_set_style_text_font(ui_HistoryStatus, &lv_font_montserrat_16, LV_PART_MAIN | LV_STATE_DEFAULT);
      } else {
        // Hapus loading label
        if (ui_HistoryStatus) {
          lv_obj_del(ui_HistoryStatus);
          ui_HistoryStatus = NULL;
        }
      }
      Serial.printf("[HIST] Done, %d items total\n", total);
    }
  }
}

void ExtButton_RequestTimeSync() {
  // Kirim request ke Raspi untuk sinkronisasi waktu
  SensorSerial.println("SYNC_TIME");
  Serial.println("[TX] SYNC_TIME → Requesting time from Raspi");
}

bool ExtButton_IsTimeSynced() {
  return time_synced;
}

bool ExtButton_IsRecording() {
  return is_recording;
}

unsigned long ExtButton_GetRecStartSec() {
  return recording_start_sec;
}
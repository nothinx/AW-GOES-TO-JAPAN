#include "ui_clock.h"
#include "ExtButton.h"
#include "BAT_Driver.h"

// Nama hari dalam bahasa Inggris
static const char* DAY_NAMES[] = {
    "Sunday", "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday"
};

// Nama bulan
static const char* MONTH_NAMES[] = {
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
};

// Timer callback — dipanggil setiap 1 detik oleh LVGL
static void clock_timer_cb(lv_timer_t * timer) {
    // Jika belum sync, tampilkan placeholder
    if (!ExtButton_IsTimeSynced()) {
        if (ui_DigitalClock) lv_label_set_text(ui_DigitalClock, "--:--");
        if (ui_DateLabel)    lv_label_set_text(ui_DateLabel, "Syncing...");
    } else {
        // Format jam: "23:59"
        char clock_buf[10];
        snprintf(clock_buf, sizeof(clock_buf), "%02d:%02d",
                 datetime.hour, datetime.minute);
        if (ui_DigitalClock) lv_label_set_text(ui_DigitalClock, clock_buf);

        // Bounds check untuk menghindari crash jika RTC korup
        uint8_t dotw = datetime.dotw <= 6 ? datetime.dotw : 0;
        uint8_t month = (datetime.month >= 1 && datetime.month <= 12) ? datetime.month : 1;

        // Format tanggal: "Monday, 31 Jan 2026"
        char date_buf[30];
        snprintf(date_buf, sizeof(date_buf), "%s, %d %s %d",
                 DAY_NAMES[dotw],
                 datetime.day,
                 MONTH_NAMES[month],
                 datetime.year);
        if (ui_DateLabel) lv_label_set_text(ui_DateLabel, date_buf);
    }

    // Update battery level (setiap detik)
    if (ui_BatteryLabel) {
        float volts = BAT_analogVolts;  // Dibaca dari Driver_Loop setiap 100ms
        // Estimasi persentase sederhana: 3.0V=0%, 4.2V=100%
        int pct = (int)((volts - 3.0f) / 1.2f * 100.0f);
        if (pct > 100) pct = 100;
        if (pct < 0) pct = 0;

        char bat_buf[16];
        if (volts < 1.0f) {
            // Belum terbaca / tidak ada baterai
            lv_label_set_text(ui_BatteryLabel, "");
        } else {
            snprintf(bat_buf, sizeof(bat_buf), "BAT %d%%", pct);
            lv_label_set_text(ui_BatteryLabel, bat_buf);
            // Warna berdasarkan level
            if (pct > 30) {
                lv_obj_set_style_text_color(ui_BatteryLabel, lv_color_hex(0x888888), LV_PART_MAIN | LV_STATE_DEFAULT);
            } else if (pct > 10) {
                lv_obj_set_style_text_color(ui_BatteryLabel, lv_color_hex(0xF59E0B), LV_PART_MAIN | LV_STATE_DEFAULT);
            } else {
                lv_obj_set_style_text_color(ui_BatteryLabel, lv_color_hex(0xDC2626), LV_PART_MAIN | LV_STATE_DEFAULT);
            }
        }
    }

    // Update elapsed time jika sedang recording
    if (ui_ElapsedLabel) {
        if (ExtButton_IsRecording()) {
            unsigned long now_sec = (unsigned long)datetime.hour * 3600UL + datetime.minute * 60UL + datetime.second;
            unsigned long start_sec = ExtButton_GetRecStartSec();
            unsigned long elapsed = now_sec >= start_sec ? now_sec - start_sec : (86400UL - start_sec) + now_sec;
            int mins = elapsed / 60;
            int secs = elapsed % 60;
            char ebuf[20];
            snprintf(ebuf, sizeof(ebuf), "Elapsed %02d:%02d", mins, secs);
            lv_label_set_text(ui_ElapsedLabel, ebuf);
            lv_obj_clear_flag(ui_ElapsedLabel, LV_OBJ_FLAG_HIDDEN);
        } else {
            lv_obj_add_flag(ui_ElapsedLabel, LV_OBJ_FLAG_HIDDEN);
        }
    }
}

void ui_clock_Init() {
    // Buat LVGL timer tiap 1000ms
    lv_timer_create(clock_timer_cb, 1000, NULL);
}

#include "ui_clock.h"

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
    // Format jam: "23:59"
    char clock_buf[10];
    snprintf(clock_buf, sizeof(clock_buf), "%02d:%02d",
             datetime.hour, datetime.minute);
    lv_label_set_text(ui_DigitalClock, clock_buf);

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
    lv_label_set_text(ui_DateLabel, date_buf);
}

void ui_clock_Init() {
    // Buat LVGL timer tiap 1000ms
    lv_timer_create(clock_timer_cb, 1000, NULL);
}

import RPi.GPIO as GPIO
import minimalmodbus
import serial
import serial.tools.list_ports
import time
import json
import threading
import sys
import os
from datetime import datetime

# ==========================================
# KONFIGURASI GLOBAL
# ==========================================
GPS_PORT = '/dev/ttyS0'  # Port GPS
GPS_BAUD = 9600
BUTTON_PIN = 26
DATA_DIR = os.path.expanduser("~/agri_data")  # Folder penyimpanan data
os.makedirs(DATA_DIR, exist_ok=True)

# Shared Memory untuk GPS (Selalu diupdate dengan data terbaru)
gps_lock = threading.Lock()  # Proteksi akses multi-thread
current_gps = {
    "lat": 0.0,
    "lng": 0.0,
    "speed_kmh": 0.0,
    "valid": False
}

# Variabel State Perekaman
state = 0            # 0: Idle, 1: Recording
session_data = []    # Tempat simpan data JSON
button_state = False # Flag untuk trigger baca data

#===========================================
# BUTTON GPIO SETUP (POLLING + DEBOUNCE)
#===========================================
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

last_button_read = GPIO.HIGH  # Status pembacaan sebelumnya
last_press_time = 0           # Waktu terakhir tombol ditekan (untuk debounce)
DEBOUNCE_MS = 300             # Debounce 300ms

# ==========================================
# FUNGSI BACKGROUND: GPS ANTI-DELAY
# ==========================================
def nmea_to_decimal(value, direction):
    try:
        if not value or value == '': return 0.0
        dot_pos = value.find('.')
        if dot_pos == -1: return 0.0
        minutes = float(value[dot_pos-2:])
        degrees = float(value[:dot_pos-2])
        decimal = degrees + (minutes / 60)
        if direction == 'S' or direction == 'W':
            decimal *= -1
        return round(decimal, 6)
    except:
        return 0.0

def gps_thread_loop():
    global current_gps
    try:
        ser_gps = serial.Serial(GPS_PORT, GPS_BAUD, timeout=1)
        print(f"[GPS] Thread Started on {GPS_PORT} (Anti-Delay Mode)")
        
        while True:
            if ser_gps.in_waiting > 0:
                try:
                    # RAHASIA ANTI DELAY: Baca semua buffer, ambil yang paling akhir
                    data_chunk = ser_gps.read(ser_gps.in_waiting).decode('utf-8', errors='ignore')
                    lines = data_chunk.split('\n')
                    
                    for line in reversed(lines):
                        if "RMC" in line:
                            parts = line.split(',')
                            if len(parts) > 6:
                                status = parts[2]
                                if status == 'A':
                                    # Update global variable dengan data SATU DETIK TERAKHIR
                                    try:
                                        spd = float(parts[7]) if parts[7] else 0.0
                                    except ValueError:
                                        spd = 0.0
                                    with gps_lock:
                                        current_gps["lat"] = nmea_to_decimal(parts[3], parts[4])
                                        current_gps["lng"] = nmea_to_decimal(parts[5], parts[6])
                                        current_gps["speed_kmh"] = spd * 1.852
                                        current_gps["valid"] = True
                                    break # Selesai, hiraukan data lama di atasnya
                                elif status == 'V':
                                    with gps_lock:
                                        current_gps["valid"] = False
                                    break
                except Exception:
                    pass
            time.sleep(0.1)
    except Exception as e:
        print(f"[GPS ERR] {e}")

# ==========================================
# FUNGSI AUTO-DETECT USB (SENSOR & ESP32)
# ==========================================
def get_port_by_keyword(keyword):
    ports = serial.tools.list_ports.comports()
    for port in ports:
        full_info = f"{port.description} {port.hwid}".upper()
        if keyword.upper() in full_info:
            return port.device
    return None

# ==========================================
# SETUP UTAMA
# ==========================================
print("=== AGRI-WAND SYSTEM INITIALIZING ===")

# 1. Jalankan GPS Latar Belakang
t = threading.Thread(target=gps_thread_loop)
t.daemon = True
t.start()

# 2. Cari Port ESP32 & Modbus
LCD_PORT = get_port_by_keyword("CP2102")
SENSOR_PORT = get_port_by_keyword("USB Serial")

if not LCD_PORT:
    print("[FATAL] ESP32 (LCD) tidak ditemukan! Cek kabel.")
    sys.exit()
if not SENSOR_PORT:
    print("[FATAL] Sensor Soil 8-in-1 tidak ditemukan! Cek kabel.")
    sys.exit()

print(f"[OK] ESP32 terdeteksi di {LCD_PORT}")
print(f"[OK] SENSOR terdeteksi di {SENSOR_PORT}")

# 3. Koneksi Alat
try:
    ser_esp = serial.Serial(LCD_PORT, 9600, timeout=1)
    time.sleep(0.1)
    ser_esp.reset_input_buffer()  # Buang data lama/noise di buffer
    
    sensor = minimalmodbus.Instrument(SENSOR_PORT, 1)
    sensor.serial.baudrate = 9600 # Sesuai request Anda sebelumnya
    sensor.serial.bytesize = 8
    sensor.serial.parity = serial.PARITY_NONE
    sensor.serial.stopbits = 1
    sensor.serial.timeout = 0.5
    sensor.mode = minimalmodbus.MODE_RTU
except Exception as e:
    print(f"[CONN ERR] {e}")
    sys.exit()

# ==========================================
# HELPER: KIRIM WAKTU KE ESP32
# ==========================================
def send_time_to_esp():
    """Kirim waktu Raspi ke ESP32 untuk sinkronisasi RTC."""
    now = datetime.now()
    # dotw: 0=Sunday, 1=Monday...6=Saturday (sesuai PCF85063)
    # Python isoweekday(): 1=Monday...7=Sunday
    py_dow = now.isoweekday()  # 1-7
    dotw = 0 if py_dow == 7 else py_dow  # Convert: 7(Sun)->0, 1(Mon)->1...6(Sat)->6
    time_str = f"TIME:{now.year},{now.month},{now.day},{dotw},{now.hour},{now.minute},{now.second}\n"
    ser_esp.write(time_str.encode('utf-8'))
    print(f" [SYNC] Waktu dikirim ke ESP32: {time_str.strip()}")

print("--- SISTEM SIAP MENERIMA PERINTAH DARI ESP32 ---")

# Kirim waktu PROAKTIF ke ESP32 saat Raspi siap
# (ESP32 mungkin sudah boot duluan dan menunggu)
time.sleep(0.3)  # Beri waktu serial stabil
send_time_to_esp()

# ==========================================
# LOOP UTAMA (MENUNGGU COMMAND ESP32)
# ==========================================
try:
    while True:
        # 1. CEK COMMAND DARI SERIAL ESP32
        if ser_esp.in_waiting > 0:
            try:
                cmd = ser_esp.readline().decode('utf-8', errors='ignore').strip()
                print(f">> CMD Diterima: {cmd}")

                # COMMAND 1: START RECORDING
                if cmd == "1":
                    if state == 0:
                        state = 1
                        session_data = []
                        ser_esp.write("MSG:REC_STARTED\n".encode('utf-8'))
                        print(" [STATE] Recording Started")
                    else:
                        # PROTEKSI UX: Cegah start ulang yang menghapus data
                        try:
                            ser_esp.write("MSG:ALREADY_REC\n".encode('utf-8'))
                        except: pass
                        print(" [UX] Command Start diabaikan (sudah recording).")

                # COMMAND 2: MANUAL COLLECT DATA (Sebagai alternatif dari menekan tombol)
                elif cmd == "2":
                    button_state = True  # Memicu pengambilan data

                # COMMAND 3: STOP & SAVE TO FILE
                elif cmd == "3":
                    if state == 1:
                        if len(session_data) > 0:
                            filename = os.path.join(DATA_DIR, f"agri_wand_{int(time.time())}.json")
                            with open(filename, 'w') as f:
                                json.dump(session_data, f, indent=4)
                            
                            ser_esp.write(f"MSG:FILE_SAVED\n".encode('utf-8'))
                            print(f" [STATE] File tersimpan: {filename} ({len(session_data)} titik)")
                        else:
                            ser_esp.write("MSG:EMPTY_SESSION\n".encode('utf-8'))
                            print(" [STATE] Sesi dihentikan (Tidak ada data).")
                        
                        state = 0
                        session_data = []
                    else:
                        ser_esp.write("MSG:NOT_REC\n".encode('utf-8'))

                # COMMAND SYNC_TIME: ESP32 minta waktu dari Raspi
                elif cmd == "SYNC_TIME":
                    send_time_to_esp()

            except Exception as e:
                print(f"[LOOP ERROR] {e}")

        # 2. POLLING TOMBOL FISIK (DETEKSI FALLING EDGE + DEBOUNCE)
        current_read = GPIO.input(BUTTON_PIN)
        now_ms = int(time.time() * 1000)
        if last_button_read == GPIO.HIGH and current_read == GPIO.LOW:
            # Falling edge terdeteksi, cek debounce
            if (now_ms - last_press_time) > DEBOUNCE_MS:
                button_state = True
                last_press_time = now_ms
        last_button_read = current_read

        # 3. CEK TRIGGER TOMBOL FISIK ATAU COMMAND SERIAL
        if button_state:
            button_state = False  # Reset flag secepatnya agar tidak terjadi spam

            # SYNC WAKTU: Kirim waktu terbaru setiap kali tombol ditekan
            send_time_to_esp()
            
            # A. BACA SENSOR TANAH
            try:
                val = sensor.read_registers(0, 7, functioncode=3)
                d_hum  = val[0] * 0.1
                d_temp = val[1] * 0.1
                d_ec   = val[2]
                d_ph   = val[3] * 0.1
                d_n, d_p, d_k = val[4], val[5], val[6]
                soil_valid = True
            except:
                soil_valid = False
                ser_esp.write("ERR:SOIL_TIMEOUT\n".encode('utf-8'))
                print(" [ERR] Gagal baca sensor tanah!")

            # B. AMBIL GPS TERBARU DARI MEMORI
            with gps_lock:
                d_gps = current_gps.copy()

            # C. KIRIM FEEDBACK KE LAYAR ESP32 (Berlaku untuk Record & Live Preview)
            if soil_valid:
                # Tentukan prefix berdasarkan state:
                #   state=1 → "DATA:"    (ESP akan update UI + increment pinpoint)
                #   state=0 → "PREVIEW:" (ESP hanya update UI, tanpa increment)
                values_str = (f"T={d_temp:.1f}|H={d_hum:.1f}|PH={d_ph:.1f}|"
                              f"EC={d_ec}|N={d_n}|P={d_p}|K={d_k}")

                if state == 1:
                    msg_lcd = f"DATA:{values_str}\n"
                    ser_esp.write(msg_lcd.encode('utf-8'))
                    print(f" [LCD] {msg_lcd.strip()} | GPS: {'OK' if d_gps['valid'] else 'WAIT'}")

                    # D. SIMPAN KE JSON
                    point = {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "soil": {
                            "temp": d_temp, "hum": d_hum, "ph": d_ph,
                            "ec": d_ec, "n": d_n, "p": d_p, "k": d_k
                        },
                        "location": {
                            "lat": d_gps["lat"],
                            "lng": d_gps["lng"],
                            "valid": d_gps["valid"]
                        }
                    }
                    session_data.append(point)
                    print(f" [SAVED] Titik ke-{len(session_data)} berhasil disimpan.")
                else:
                    msg_lcd = f"PREVIEW:{values_str}\n"
                    ser_esp.write(msg_lcd.encode('utf-8'))
                    print(f" [PREVIEW] {msg_lcd.strip()} (data TIDAK disimpan)")


        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nProgram Dihentikan.")
finally:
    if 'ser_esp' in locals() and ser_esp.is_open:
        ser_esp.close()
    GPIO.cleanup()

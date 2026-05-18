"""
Robot Kol Ana Entegrasyon
Faster-Whisper (ses) + YOLO (kamera) + Nucleo F401RE (motor)

Kullanım:
  python main_robot.py

Komut örnekleri:
  "şişeyi al"        → YOLO şişeyi bulur, kol oraya gider
  "topu göster"      → YOLO topu bulur, ekranda vurgular
  "home"             → tüm servolar 90°
  "tutucuyu aç"      → gripper açar
  "tutucuyu kapat"   → gripper kapar
  "dur"              → durdur
"""

import cv2
import numpy as np
import urllib.request
import threading
import queue
import time
import sounddevice as sd
from faster_whisper import WhisperModel
from ultralytics import YOLO

# robot_arm.py aynı klasörde olmalı
from robot_arm import RobotArm


# ============================================================
# AYARLAR — KENDİNE GÖRE DÜZENLE
# ============================================================
ESP32_CAM_URL       = "http://192.168.0.13/stream"
NUCLEO_PORT         = "COM3"          # Nucleo'nun COM portu
YOLO_MODEL          = "yolov8n.pt"
WHISPER_MODEL_SIZE  = "small"
WHISPER_LANG        = "tr"
SAMPLE_RATE         = 16000
RECORD_SECONDS      = 3              # Her dinleme penceresi (sn)
CONFIDENCE          = 0.5

# Gripper servo index (robot_arm.py'deki servo numaraları)
SERVO_GRIPPER   = 4   # 0-5 arası, kolunuza göre değiştir
SERVO_SHOULDER  = 1
SERVO_ELBOW     = 2
SERVO_WRIST     = 3
SERVO_WRIST_ROT = 4

# Gripper açı değerleri
GRIPPER_OPEN    = 60
GRIPPER_CLOSE   = 120

# Türkçe ses komutu → YOLO sınıf adı
NESNE_HARITASI = {
    "şişe":     "bottle",
    "sise":     "bottle",
    "top":      "sports ball",
    "bardak":   "cup",
    "kupa":     "cup",
    "telefon":  "cell phone",
    "kitap":    "book",
    "sandalye": "chair",
    "kedi":     "cat",
    "köpek":    "dog",
    "kopek":    "dog",
    "laptop":   "laptop",
    "klavye":   "keyboard",
    "fare":     "mouse",
    "insan":    "person",
    "adam":     "person",
    "kalem":    "pen",
}

EYLEMLER_AL     = ["al", "tut", "getir", "yakala"]
EYLEMLER_GOSTER = ["göster", "goster", "bul", "ara", "nerede"]
EYLEMLER_BIRAK  = ["bırak", "birak", "koy", "bırakk"]


# ============================================================
# GLOBAL DURUM
# ============================================================
hedef_nesne   = None   # YOLO'nun arayacağı sınıf adı
hedef_eylem   = None   # "al", "goster", "birak"
hedef_konum   = None   # Son tespit: (cx, cy)
son_komut_str = ""     # Ekranda gösterilecek metin
komut_queue   = queue.Queue()


# ============================================================
# YOLO
# ============================================================
print("[INFO] YOLO yükleniyor...")
yolo = YOLO(YOLO_MODEL)
print(f"[INFO] YOLO hazır — {len(yolo.names)} sınıf")


def detect(frame):
    """YOLO ile tespit yap, hedef nesneyi vurgula."""
    global hedef_konum

    results = yolo(frame, verbose=False, conf=CONFIDENCE)
    display = frame.copy()
    detections = []

    for result in results:
        if result.boxes is None:
            continue
        for box in result.boxes:
            cls_id    = int(box.cls[0])
            conf      = float(box.conf[0])
            cls_name  = yolo.names[cls_id]
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
            cx, cy    = (x1 + x2) // 2, (y1 + y2) // 2
            is_target = (hedef_nesne and cls_name.lower() == hedef_nesne.lower())

            if is_target:
                color     = (0, 255, 0)
                thickness = 3
                hedef_konum = (cx, cy)
                cv2.putText(display, ">>> HEDEF <<<",
                            (x1, y2 + 25), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (0, 255, 0), 2)
            else:
                seed  = (cls_id * 50) % 255
                color = (int(seed), int(255 - seed), 100)
                thickness = 2

            cv2.rectangle(display, (x1, y1), (x2, y2), color, thickness)
            cv2.circle(display, (cx, cy), 5, (0, 0, 255), -1)

            lbl  = f"{cls_name} {conf:.2f}"
            lsz, _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(display,
                          (x1, y1 - lsz[1] - 10), (x1 + lsz[0], y1),
                          color, -1)
            cv2.putText(display, lbl, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            detections.append({
                "class": cls_name, "conf": conf,
                "center": (cx, cy), "box": (x1, y1, x2, y2),
                "is_target": is_target
            })

    return display, detections


# ============================================================
# ROBOT KOL KONTROL
# ============================================================
arm = RobotArm(port=NUCLEO_PORT)


def robot_baglat():
    if arm.connect():
        print(f"[OK] Nucleo baglandi: {NUCLEO_PORT}")
        # Custom home pozisyonu
        arm.set_servo(0, 90)
        arm.set_servo(1, 180)   # Omuz
        arm.set_servo(2, 105)   # Dirsek
        arm.set_servo(3, 0)     # Bilek
        arm.set_servo(4, 40)    # Gripper
        arm.set_servo(5, 90)
    else:
        print(f"[UYARI] Nucleo baglanamadi ({NUCLEO_PORT}). Sadece goruntu modu.")


def piksel_to_servo(cx, cy, frame_w, frame_h):
    """
    Piksel koordinatını servo açılarına dönüştür.
    Bu basit bir oran hesabıdır — gerçek kalibrasyon
    mekanik bittikten sonra yapılacak (hand-eye calibration).

    Şu an yalnızca taban (stepper) ve omuz servosu hareket eder.
    """
    # Kameranın yatay merkezi → stepper sıfır konumu
    # cx 0 ise en sol, frame_w ise en sağ
    norm_x = (cx - frame_w / 2) / (frame_w / 2)   # -1 ... +1
    norm_y = (cy - frame_h / 2) / (frame_h / 2)   # -1 ... +1 (+ = aşağı)

    # Taban adımı: ±600 step = ±~45°
    taban_step = int(norm_x * 600)

    # Omuz: merkez 90°, yukarı nesne → omuz aşağı (kol uzanır)
    omuz_aci = 90 + int(norm_y * 30)
    omuz_aci = max(30, min(150, omuz_aci))

    return taban_step, omuz_aci


def robot_hareket_et(cx, cy, frame_w, frame_h, eylem):
    """Tespit koordinatına göre kolу hareket ettir."""
    taban_step, omuz_aci = piksel_to_servo(cx, cy, frame_w, frame_h)

    print(f"[MOTOR] Taban step={taban_step:+d}  Omuz={omuz_aci}°  Eylem={eylem}")

    if arm.ser and arm.ser.is_open:
        arm.stepper_move(taban_step)
        time.sleep(0.3)
        arm.set_servo(SERVO_SHOULDER, omuz_aci)

        if eylem == "al":
            time.sleep(0.5)
            arm.set_servo(SERVO_GRIPPER, GRIPPER_CLOSE)
            print("[MOTOR] Gripper kapandı")
        elif eylem == "birak":
            time.sleep(0.5)
            arm.set_servo(SERVO_GRIPPER, GRIPPER_OPEN)
            print("[MOTOR] Gripper açıldı")
    else:
        print("[UYARI] Nucleo bağlı değil, motor komutu atlandı.")


# ============================================================
# SES TANIMA — Faster-Whisper
# ============================================================
print(f"\n[INFO] Whisper '{WHISPER_MODEL_SIZE}' yükleniyor...")
whisper = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
print("[INFO] Whisper hazır.\n")


def komutu_isle(metin):
    """Tanınan metni ayrıştır, komut_queue'ya ekle."""
    global son_komut_str
    metin = metin.lower().strip()
    son_komut_str = metin
    print(f"[SES] '{metin}'")

    # HOME
    if any(w in metin for w in ["home", "başlangıç", "baslangic",
                                  "sıfırla", "sifirla", "merkez"]):
        komut_queue.put({"eylem": "home"})
        return

    # DUR
    if any(w in metin for w in ["dur", "stop", "bekle"]):
        komut_queue.put({"eylem": "dur"})
        return

    # TUTUCU AÇ
    if any(a in metin for a in ["aç", "ac"]) and \
       any(n in metin for n in ["tutucu", "gripper", "pençe", "pence"]):
        komut_queue.put({"eylem": "gripper_ac"})
        return

    # TUTUCU KAPAT
    if any(a in metin for a in ["kapat", "sık", "sik", "tut"]) and \
       any(n in metin for n in ["tutucu", "gripper", "pençe", "pence"]):
        komut_queue.put({"eylem": "gripper_kapat"})
        return

    # Nesne bul
    bulunan_nesne = None
    for tr, en in NESNE_HARITASI.items():
        if tr in metin:
            bulunan_nesne = en
            break

    # Eylem bul
    bulunan_eylem = None
    if any(w in metin for w in EYLEMLER_AL):
        bulunan_eylem = "al"
    elif any(w in metin for w in EYLEMLER_GOSTER):
        bulunan_eylem = "goster"
    elif any(w in metin for w in EYLEMLER_BIRAK):
        bulunan_eylem = "birak"

    if bulunan_nesne and bulunan_eylem:
        print(f"[SES] Nesne='{bulunan_nesne}'  Eylem='{bulunan_eylem}'")
        komut_queue.put({"eylem": bulunan_eylem, "nesne": bulunan_nesne})
    elif bulunan_nesne:
        # Eylem belirtilmemişse varsayılan: göster
        print(f"[SES] Nesne='{bulunan_nesne}'  Eylem=varsayılan(goster)")
        komut_queue.put({"eylem": "goster", "nesne": bulunan_nesne})
    else:
        print("[SES] Tanınmayan komut.")


def ses_dinle_loop():
    """Arka planda sürekli mikrofonu dinler."""
    print("[SES] Dinleniyor... (mikrofona konuş)\n")
    while True:
        try:
            audio = sd.rec(
                int(RECORD_SECONDS * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32"
            )
            sd.wait()
            audio_np = audio.flatten()

            segments, _ = whisper.transcribe(
                audio_np,
                language=WHISPER_LANG,
                beam_size=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500}
            )

            metin = " ".join(s.text for s in segments).strip()
            if metin:
                komutu_isle(metin)

        except Exception as e:
            print(f"[SES HATA] {e}")
            time.sleep(1)


# ============================================================
# ANA DÖNGÜ
# ============================================================
def main():
    global hedef_nesne, hedef_eylem, hedef_konum

    print("=" * 60)
    print(" Robot Kol — Ses + Görüntü Kontrolü")
    print("=" * 60)
    print(f"\nESP32-CAM  : {ESP32_CAM_URL}")
    print(f"Nucleo     : {NUCLEO_PORT}")
    print(f"\nDesteklenen nesneler: {', '.join(NESNE_HARITASI.keys())}")
    print("\nKomut örnekleri:")
    print("  'şişeyi al'       → kol şişeye gider, tutar")
    print("  'topu göster'     → YOLO topu vurgular")
    print("  'home'            → başlangıç pozisyonu")
    print("  'tutucuyu aç'     → gripper açılır")
    print("\nKlavye:")
    print("  q → çıkış  |  r → hedef sıfırla  |  h → home")
    print("-" * 60)

    # Nucleo bağlantısı
    robot_baglat()

    # Ses thread'i başlat
    ses_t = threading.Thread(target=ses_dinle_loop, daemon=True)
    ses_t.start()

    # ESP32-CAM bağlan
    print(f"\n[CAM] Bağlanıyor: {ESP32_CAM_URL}")
    try:
        stream = urllib.request.urlopen(ESP32_CAM_URL, timeout=10)
        print("[CAM] Bağlandı!\n")
    except Exception as e:
        print(f"[CAM HATA] {e}")
        print("ESP32-CAM'i kontrol et ve tekrar başlat.")
        arm.disconnect()
        return

    buf          = b""
    fps_cnt      = 0
    fps_t        = time.time()
    fps_val      = 0
    son_hareket  = 0   # Son motor hareketi zamanı

    while True:
        # --- Kuyruktan komut al ---
        while not komut_queue.empty():
            komut = komut_queue.get()
            ey = komut.get("eylem")

            if ey == "home":
                hedef_nesne = None
                hedef_konum = None
                arm.home()
                print("[KOL] Home pozisyonu")

            elif ey == "dur":
                hedef_nesne = None
                hedef_konum = None
                print("[KOL] Durduruldu")

            elif ey == "gripper_ac":
                arm.set_servo(SERVO_GRIPPER, GRIPPER_OPEN)
                print("[KOL] Gripper açıldı")

            elif ey == "gripper_kapat":
                arm.set_servo(SERVO_GRIPPER, GRIPPER_CLOSE)
                print("[KOL] Gripper kapandı")

            elif ey in ("al", "goster", "birak"):
                hedef_nesne = komut.get("nesne")
                hedef_eylem = ey
                hedef_konum = None
                print(f"[AKTIF] Hedef: {hedef_nesne} / {hedef_eylem}")

        # --- Kamera karesi ---
        try:
            buf += stream.read(1024)
            a = buf.find(b'\xff\xd8')
            b = buf.find(b'\xff\xd9')

            if a != -1 and b != -1 and b > a:
                jpg = buf[a:b + 2]
                buf = buf[b + 2:]

                frame = cv2.imdecode(
                    np.frombuffer(jpg, dtype=np.uint8),
                    cv2.IMREAD_COLOR
                )
                if frame is None:
                    continue

                h, w = frame.shape[:2]
                display, detections = detect(frame)

                # --- Motor komutu (her 1.5 sn'de bir) ---
                if hedef_konum and (time.time() - son_hareket > 1.5):
                    if hedef_eylem in ("al", "birak", "goster"):
                        cx, cy = hedef_konum
                        robot_hareket_et(cx, cy, w, h, hedef_eylem)
                        son_hareket = time.time()

                # --- HUD ---
                fps_cnt += 1
                if time.time() - fps_t >= 1.0:
                    fps_val = fps_cnt
                    fps_cnt = 0
                    fps_t   = time.time()

                cv2.putText(display, f"FPS: {fps_val}",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (0, 255, 0), 2)

                hedef_str = hedef_nesne or "YOK"
                cv2.putText(display, f"Hedef: {hedef_str}",
                            (10, 60), cv2.FONT_HERSHEY_SIMPLEX,
                            0.65, (0, 255, 255), 2)

                eylem_str = hedef_eylem or "-"
                cv2.putText(display, f"Eylem: {eylem_str}",
                            (10, 90), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (255, 200, 0), 2)

                konum_str = str(hedef_konum) if hedef_konum else "-"
                cv2.putText(display, f"Konum: {konum_str}",
                            (10, 120), cv2.FONT_HERSHEY_SIMPLEX,
                            0.55, (200, 200, 200), 1)

                cv2.putText(display, f"Ses: {son_komut_str[-40:]}",
                            (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (180, 180, 255), 1)

                cv2.imshow("Robot Kol — Ses + Goruntu", display)

                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('r'):
                    hedef_nesne = None
                    hedef_konum = None
                    print("[OK] Hedef sıfırlandı")
                elif key == ord('h'):
                    arm.home()
                    print("[KOL] Home")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[DÖNGÜ HATA] {e}")
            break

    cv2.destroyAllWindows()
    arm.disconnect()
    print("\n[OK] Kapatıldı.")


if __name__ == "__main__":
    main()
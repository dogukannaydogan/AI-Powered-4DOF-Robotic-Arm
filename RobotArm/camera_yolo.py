"""
ESP32-CAM + YOLOv8 Nesne Tespiti
WiFi'dan goruntu cek, YOLO ile nesneleri tani, kutu icine al.
"""

import cv2
import numpy as np
import urllib.request
import time
from ultralytics import YOLO


# ============================================================
# AYARLAR
# ============================================================
ESP32_CAM_URL = "http://192.168.0.13/stream"

# YOLOv8 modelleri: yolov8n (en kucuk, hizli), yolov8s, yolov8m, yolov8l, yolov8x
# Baslangic icin nano (n) onerilir - CPU'da rahat calisir
MODEL_NAME = "yolov8n.pt"

# Sadece bu siniflari goster (None = tum siniflari goster)
# Tum sinif listesi: https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/datasets/coco8.yaml
# Ornek: sadece insan(0), sise(39), bardak(41), top(32), kedi(15), kopek(16)
TARGET_CLASSES = None  # None = hepsi
# TARGET_CLASSES = [0, 32, 39, 41]  # insan, top, sise, bardak

# Guven esigi (0.0 - 1.0): bu degerin altinda tespitler yok sayilir
CONFIDENCE_THRESHOLD = 0.5


# ============================================================
# YOLO MODELI YUKLEME
# ============================================================
print("[INFO] YOLO modeli yukleniyor (ilk seferde indirme yapar)...")
model = YOLO(MODEL_NAME)
print(f"[INFO] Model hazir: {MODEL_NAME}")
print(f"[INFO] Toplam sinif sayisi: {len(model.names)}")


def detect_and_draw(frame):
    """
    Goruntude nesne tespiti yap ve kutu/etiket ciz.

    Args:
        frame: BGR numpy array

    Returns:
        tuple: (display_frame, detections_list)
            detections_list = [
                {'class': 'top', 'confidence': 0.85, 'box': (x1,y1,x2,y2), 'center': (cx,cy)},
                ...
            ]
    """
    # YOLO tespiti yap
    results = model(frame, verbose=False, conf=CONFIDENCE_THRESHOLD)

    display = frame.copy()
    detections = []

    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue

        for box in boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])

            # TARGET_CLASSES filtrele
            if TARGET_CLASSES is not None and cls_id not in TARGET_CLASSES:
                continue

            class_name = model.names[cls_id]

            # Kutu koordinatlari
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2

            # Renk her sinif icin farkli
            color_seed = (cls_id * 50) % 255
            color = (int(color_seed), int(255 - color_seed), 100)

            # Kutu ciz
            cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)

            # Merkez nokta
            cv2.circle(display, (cx, cy), 5, (0, 0, 255), -1)

            # Etiket
            label = f"{class_name} {conf:.2f}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(display, (x1, y1 - label_size[1] - 10),
                          (x1 + label_size[0], y1), color, -1)
            cv2.putText(display, label, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            detections.append({
                'class': class_name,
                'confidence': conf,
                'box': (x1, y1, x2, y2),
                'center': (cx, cy)
            })

    return display, detections


def stream_with_yolo():
    """ESP32-CAM stream + YOLO tespiti."""
    print(f"\nBaglaniyor: {ESP32_CAM_URL}")
    print("Kontrol tuslari:")
    print("  q -> Cikis")
    print("  s -> Snapshot")
    print("  y -> YOLO'yu ac/kapat")

    try:
        stream = urllib.request.urlopen(ESP32_CAM_URL, timeout=10)
        print("[OK] Stream'e baglandi!\n")
    except Exception as e:
        print(f"[HATA] Baglanilamadi: {e}")
        return

    yolo_enabled = True
    bytes_buffer = b''

    fps_counter = 0
    fps_start = time.time()
    fps_display = 0

    # Son tespit edilen nesneleri konsola yazma sayaci
    print_counter = 0

    while True:
        try:
            bytes_buffer += stream.read(1024)
            a = bytes_buffer.find(b'\xff\xd8')
            b = bytes_buffer.find(b'\xff\xd9')

            if a != -1 and b != -1 and b > a:
                jpg = bytes_buffer[a:b+2]
                bytes_buffer = bytes_buffer[b+2:]

                frame = cv2.imdecode(
                    np.frombuffer(jpg, dtype=np.uint8),
                    cv2.IMREAD_COLOR
                )

                if frame is None:
                    continue

                # YOLO ile tespit
                if yolo_enabled:
                    display, detections = detect_and_draw(frame)

                    # Her 30 karede bir konsola yaz (cok hizli yazmasin)
                    print_counter += 1
                    if print_counter >= 30 and detections:
                        print(f"\n[Tespit] {len(detections)} nesne:")
                        for d in detections:
                            print(f"  -> {d['class']:15s} conf={d['confidence']:.2f}  "
                                  f"merkez=({d['center'][0]:3d},{d['center'][1]:3d})")
                        print_counter = 0
                else:
                    display = frame

                # FPS hesapla ve yaz
                fps_counter += 1
                if time.time() - fps_start >= 1.0:
                    fps_display = fps_counter
                    fps_counter = 0
                    fps_start = time.time()

                cv2.putText(display, f"FPS: {fps_display}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                yolo_status = "YOLO: AKTIF" if yolo_enabled else "YOLO: KAPALI"
                cv2.putText(display, yolo_status, (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

                cv2.imshow('ESP32-CAM + YOLO', display)

                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                if key == ord('s'):
                    filename = f"yolo_snapshot_{int(time.time())}.jpg"
                    cv2.imwrite(filename, display)
                    print(f"Snapshot: {filename}")
                if key == ord('y'):
                    yolo_enabled = not yolo_enabled
                    print(f"\nYOLO: {'AKTIF' if yolo_enabled else 'KAPALI'}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Hata: {e}")
            break

    cv2.destroyAllWindows()


if __name__ == '__main__':
    print("=" * 60)
    print(" ESP32-CAM + YOLOv8 Nesne Tespiti")
    print("=" * 60)

    print("\nIlk basta YOLO modeli inecek (yolov8n.pt, ~6 MB).")
    print("Sonraki calistirmalarda kullanilir.\n")

    stream_with_yolo()
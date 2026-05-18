"""
ESP32-CAM Stream Goruntuleyici - urllib + manuel MJPEG parser
OpenCV'nin VideoCapture'i bu ESP32-CAM ile anlasmadigi icin
manuel olarak MJPEG stream'i parse ediyoruz.
"""

import cv2
import numpy as np
import urllib.request
import time


ESP32_CAM_URL = "http://192.168.0.13/stream"


def stream_basic():
    print(f"Baglaniyor: {ESP32_CAM_URL}")
    print("Cikis icin Ctrl+C")

    try:
        stream = urllib.request.urlopen(ESP32_CAM_URL, timeout=10)
        print("[OK] Stream'e baglandi!")
    except Exception as e:
        print(f"[HATA] Baglanilamadi: {e}")
        return

    fps_counter = 0
    fps_start = time.time()
    fps_display = 0

    bytes_buffer = b''

    while True:
        try:
            bytes_buffer += stream.read(1024)

            # JPEG sinirini bul (FFD8 baslangic, FFD9 bitis)
            a = bytes_buffer.find(b'\xff\xd8')
            b = bytes_buffer.find(b'\xff\xd9')

            if a != -1 and b != -1 and b > a:
                jpg = bytes_buffer[a:b+2]
                bytes_buffer = bytes_buffer[b+2:]

                # JPEG'i decode et
                frame = cv2.imdecode(
                    np.frombuffer(jpg, dtype=np.uint8),
                    cv2.IMREAD_COLOR
                )

                if frame is None:
                    continue

                # FPS hesapla
                fps_counter += 1
                if time.time() - fps_start >= 1.0:
                    fps_display = fps_counter
                    fps_counter = 0
                    fps_start = time.time()

                # FPS yaz
                cv2.putText(frame, f"FPS: {fps_display}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                h, w = frame.shape[:2]
                cv2.putText(frame, f"{w}x{h}", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

                cv2.imshow('ESP32-CAM Stream', frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                if key == ord('s'):
                    filename = f"snapshot_{int(time.time())}.jpg"
                    cv2.imwrite(filename, frame)
                    print(f"Snapshot: {filename}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Hata: {e}")
            break

    cv2.destroyAllWindows()


def stream_with_color_detection():
    print(f"Baglaniyor: {ESP32_CAM_URL}")
    print("Kontrol tuslari:")
    print("  q -> Cikis")
    print("  s -> Snapshot")
    print("  c -> Renk tespitini ac/kapat")

    try:
        stream = urllib.request.urlopen(ESP32_CAM_URL, timeout=10)
        print("[OK] Stream'e baglandi!")
    except Exception as e:
        print(f"[HATA] Baglanilamadi: {e}")
        return

    detect_color = True
    bytes_buffer = b''

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

                display = frame.copy()

                if detect_color:
                    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                    lower_red1 = np.array([0, 120, 70])
                    upper_red1 = np.array([10, 255, 255])
                    lower_red2 = np.array([170, 120, 70])
                    upper_red2 = np.array([180, 255, 255])
                    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
                    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
                    mask = mask1 + mask2

                    kernel = np.ones((5, 5), np.uint8)
                    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
                    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

                    contours, _ = cv2.findContours(
                        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                    )

                    if contours:
                        largest = max(contours, key=cv2.contourArea)
                        if cv2.contourArea(largest) > 500:
                            (x, y), radius = cv2.minEnclosingCircle(largest)
                            center = (int(x), int(y))
                            radius = int(radius)
                            cv2.circle(display, center, radius, (0, 255, 0), 2)
                            cv2.circle(display, center, 5, (0, 0, 255), -1)
                            cv2.putText(display, f"Hedef: ({center[0]}, {center[1]})",
                                        (10, display.shape[0] - 20),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                cv2.imshow('ESP32-CAM Stream', display)

                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                if key == ord('s'):
                    filename = f"snapshot_{int(time.time())}.jpg"
                    cv2.imwrite(filename, frame)
                    print(f"Snapshot: {filename}")
                if key == ord('c'):
                    detect_color = not detect_color
                    print(f"Renk tespiti: {'AKTIF' if detect_color else 'KAPALI'}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Hata: {e}")
            break

    cv2.destroyAllWindows()


if __name__ == '__main__':
    print("=" * 50)
    print(" ESP32-CAM Stream Test (v2 - urllib)")
    print("=" * 50)
    print("\n1 - Basit stream")
    print("2 - Renk algilamali stream")
    choice = input("\nSecim (1/2): ").strip()

    if choice == '2':
        stream_with_color_detection()
    else:
        stream_basic()
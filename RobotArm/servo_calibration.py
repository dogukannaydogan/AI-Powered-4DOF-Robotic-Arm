"""
Robot Kol Servo Kalibrasyon Scripti
Mekanik bittikten sonra her servoyu tek tek test et.

Kullanim:
  python servo_calibration.py

Klavye komutlari:
  w / s  -> secili servoyu +5 / -5 derece
  a / d  -> onceki / sonraki servo sec
  h      -> secili servoyu 90 dereceye (home)
  0      -> tum servolar home
  g      -> gripper ac/kapat toggle
  q      -> cikis ve sonuclari kaydet
"""

import time
import sys
from robot_arm import RobotArm

try:
    import msvcrt  # Windows
    def getch():
        return msvcrt.getch().decode('ascii', errors='ignore')
    WINDOWS = True
except ImportError:
    import tty, termios  # Linux/Mac
    def getch():
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    WINDOWS = False


# ============================================================
# AYARLAR
# ============================================================
PORT      = "COM3"
BAUDRATE  = 115200

# Servo isim listesi (index 0-5)
SERVO_ISIMLER = [
    "0 - Taban / Turntable yardimci",
    "1 - Omuz (Shoulder)",
    "2 - Dirsek (Elbow)",
    "3 - Bilek dikey (Wrist tilt)",
    "4 - Gripper",
    "5 - Bos / Yedek",
]

# Baslangic acilar (home = 90)
servo_acilari = [90, 90, 90, 90, 90, 90]

# Guvenli sinirlar (mekanik testi sonrasi doldur)
servo_min = [0,  30,  30,  0,  40,  0]
servo_max = [180, 180, 150, 180, 140, 180]

secili_servo = 1   # Baslangicta omuz secili
adim         = 5   # Her tuslamada kac derece


# ============================================================
def ekrana_yaz():
    """Mevcut durumu temiz goster."""
    print("\033[2J\033[H", end="")   # Ekrani temizle
    print("=" * 55)
    print("  ROBOT KOL SERVO KALIBRASYON")
    print("=" * 55)
    print(f"  Adim: {adim} derece  |  w=yukari  s=asagi  a/d=servo sec")
    print(f"  h=bu servo home  |  0=tum home  |  g=gripper  |  q=cikis")
    print("-" * 55)

    for i, isim in enumerate(SERVO_ISIMLER):
        isaretci = ">>>" if i == secili_servo else "   "
        aci      = servo_acilari[i]
        bar_len  = int((aci / 180) * 30)
        bar      = "#" * bar_len + "-" * (30 - bar_len)
        print(f"  {isaretci} S{i} [{bar}] {aci:3d}°  {isim}")

    print("-" * 55)
    print(f"  Secili: {SERVO_ISIMLER[secili_servo]}")
    print(f"  Aci: {servo_acilari[secili_servo]}°  "
          f"(min={servo_min[secili_servo]}  max={servo_max[secili_servo]})")
    print("=" * 55)


def aci_gonder(arm, index, aci):
    """Servo acisini sinirlar icinde tut ve gonder."""
    aci = max(servo_min[index], min(servo_max[index], aci))
    servo_acilari[index] = aci
    resp = arm.set_servo(index, aci)
    return aci, resp


def sonuclari_kaydet():
    """Kalibrasyon sonuclarini ekrana yazdir."""
    print("\n" + "=" * 55)
    print("  KALIBRASYON SONUCLARI")
    print("  Bu degerleri main_robot.py ve kinematics.py'e kopyala:")
    print("=" * 55)
    print(f"\n  # Servo home acilar:")
    print(f"  HOME_ANGLES = {servo_acilari}")
    print(f"\n  # Servo sinirlar:")
    print(f"  SERVO_MIN = {servo_min}")
    print(f"  SERVO_MAX = {servo_max}")
    print(f"\n  # Gripper:")
    print(f"  GRIPPER_OPEN  = {servo_acilari[4]}")
    print()


# ============================================================
def main():
    global secili_servo, adim

    print(f"[INFO] Nucleo baglaniliyor: {PORT}")
    arm = RobotArm(port=PORT, baudrate=BAUDRATE)

    if not arm.connect():
        print("[HATA] Nucleo baglanamadi! COM portunu kontrol et.")
        return

    print("[OK] Baglandi. Home pozisyonu gonderiliyor...")
    arm.home()
    time.sleep(1)

    gripper_acik = True
    ekrana_yaz()

    try:
        while True:
            tus = getch().lower()

            if tus == 'q':
                break

            elif tus == 'w':
                # Servo artir
                yeni, _ = aci_gonder(arm, secili_servo,
                                      servo_acilari[secili_servo] + adim)
                ekrana_yaz()

            elif tus == 's':
                # Servo azalt
                yeni, _ = aci_gonder(arm, secili_servo,
                                      servo_acilari[secili_servo] - adim)
                ekrana_yaz()

            elif tus == 'd':
                # Sonraki servo
                secili_servo = (secili_servo + 1) % 6
                ekrana_yaz()

            elif tus == 'a':
                # Onceki servo
                secili_servo = (secili_servo - 1) % 6
                ekrana_yaz()

            elif tus == 'h':
                # Bu servoyu home
                aci_gonder(arm, secili_servo, 90)
                ekrana_yaz()

            elif tus == '0':
                # Tum servolar home
                for i in range(6):
                    servo_acilari[i] = 90
                arm.home()
                ekrana_yaz()

            elif tus == 'g':
                # Gripper toggle
                if gripper_acik:
                    aci_gonder(arm, 4, servo_min[4])   # Kapat
                    gripper_acik = False
                    print("\n  [Gripper KAPALI]")
                else:
                    aci_gonder(arm, 4, servo_max[4])   # Ac
                    gripper_acik = True
                    print("\n  [Gripper ACIK]")
                ekrana_yaz()

            elif tus == '+':
                adim = min(20, adim + 5)
                ekrana_yaz()

            elif tus == '-':
                adim = max(1, adim - 5)
                ekrana_yaz()

    except KeyboardInterrupt:
        pass

    print("\n[OK] Cikiliyor...")
    sonuclari_kaydet()
    arm.disconnect()


if __name__ == "__main__":
    main()
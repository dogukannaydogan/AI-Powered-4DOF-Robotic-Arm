"""
Klavyeden Robot Kol Kontrolu
WASD ve diger tuslarla servolari oynat.
"""

from robot_arm import RobotArm
import sys


def print_help():
    print("""
+======================================================+
|         ROBOT KOL - KLAVYE KONTROL                   |
+======================================================+

Servo 0 (taban donus servosu) :  Q / A   (+10 / -10)
Servo 1 (omuz)                 :  W / S
Servo 2 (dirsek)               :  E / D
Servo 3 (bilek dikey)          :  R / F
Servo 4 (bilek donus)          :  T / G
Servo 5 (tutucu)               :  Y / H

Step motor (taban):
   J -> 500 step sola
   L -> 500 step saga
   K -> step motoru sifirla (Zero)
   I -> mevcut pozisyonu sorgula
   X -> step motoru durdur

Hizli komutlar:
   1 -> Tum servolari home (90)
   2 -> Servo 5 (gripper) ac
   3 -> Servo 5 (gripper) kapat
   0 -> Potansiyometre oku
   p -> Ping
   ? -> Bu yardim
   q -> Cikis

NOT: Her tustan sonra Enter'a basacaksin.
+======================================================+
""")


def main():
    port = input("Nucleo COM portu (orn. COM5): ").strip()
    if not port:
        print("Port girilmedi, cikiyorum.")
        return

    arm = RobotArm(port=port)
    if not arm.connect():
        print("Baglanilamadi, cikiyorum.")
        return

    # Mevcut servo acilarini hatirla
    angles = [90, 90, 90, 90, 90, 90]

    # Servoyu home'a getir
    arm.home()
    print_help()

    while True:
        try:
            cmd = input(">>> ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break

        if not cmd:
            continue

        # Cikis
        if cmd == 'q':
            break

        # Yardim
        if cmd == '?':
            print_help()
            continue

        # Servo kontrolleri (+10 / -10 derece)
        servo_keys = {
            'q': (0, +10), 'a': (0, -10),
            'w': (1, +10), 's': (1, -10),
            'e': (2, +10), 'd': (2, -10),
            'r': (3, +10), 'f': (3, -10),
            't': (4, +10), 'g': (4, -10),
            'y': (5, +10), 'h': (5, -10),
        }

        if cmd in servo_keys:
            idx, delta = servo_keys[cmd]
            new_angle = angles[idx] + delta
            new_angle = max(0, min(180, new_angle))
            angles[idx] = new_angle
            resp = arm.set_servo(idx, new_angle)
            print(f"  Servo {idx} -> {new_angle}°  | {resp}")
            continue

        # Step motor komutlari
        if cmd == 'j':
            print(arm.stepper_move(-500))
            continue
        if cmd == 'l':
            print(arm.stepper_move(500))
            continue
        if cmd == 'k':
            print(arm.stepper_zero())
            continue
        if cmd == 'i':
            print(arm.stepper_position())
            continue
        if cmd == 'x':
            print(arm.stepper_stop())
            continue

        # Hizli komutlar
        if cmd == '1':
            angles = [90, 90, 90, 90, 90, 90]
            print(arm.home())
            continue
        if cmd == '2':
            angles[5] = 30  # gripper ac
            print(arm.set_servo(5, 30))
            continue
        if cmd == '3':
            angles[5] = 150  # gripper kapat
            print(arm.set_servo(5, 150))
            continue
        if cmd == '0':
            val = arm.read_pot()
            print(f"  Potansiyometre: {val}")
            continue
        if cmd == 'p':
            print(arm.ping())
            continue

        print(f"  Bilinmeyen komut: '{cmd}'  (yardim icin '?' yaz)")

    arm.disconnect()
    print("Gorusuruz!")


if __name__ == '__main__':
    main()
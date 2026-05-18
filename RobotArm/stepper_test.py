"""
Stepper motor test scripti
Klavye:
  a/d  -> -50 / +50 adim
  z/c  -> -10 / +10 adim
  h    -> sifira don
  0    -> mevcut pozisyonu sifirla
  q    -> cikis
"""

import time
import sys
from robot_arm import RobotArm

try:
    import msvcrt
    def getch():
        return msvcrt.getch().decode('ascii', errors='ignore')
except ImportError:
    import tty, termios
    def getch():
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


PORT = "COM3"


def main():
    print(f"[INFO] Nucleo baglaniliyor: {PORT}")
    arm = RobotArm(port=PORT)
    if not arm.connect():
        print("[HATA] Nucleo baglanamadi!")
        return

    print("[OK] Baglandi.")
    print("\n  STEPPER TEST")
    print("  a/d = -50/+50 adim")
    print("  z/c = -10/+10 adim")
    print("  h   = sifira don")
    print("  0   = mevcut pozisyonu sifirla")
    print("  p   = pot oku")
    print("  q   = cikis")

    pos = 0

    try:
        while True:
            tus = getch().lower()

            if tus == 'q':
                break
            elif tus == 'a':
                pos -= 50
                resp = arm.stepper_move(pos)
                print(f"  pos={pos:+d}  resp={resp}")
            elif tus == 'd':
                pos += 50
                resp = arm.stepper_move(pos)
                print(f"  pos={pos:+d}  resp={resp}")
            elif tus == 'z':
                pos -= 10
                resp = arm.stepper_move(pos)
                print(f"  pos={pos:+d}  resp={resp}")
            elif tus == 'c':
                pos += 10
                resp = arm.stepper_move(pos)
                print(f"  pos={pos:+d}  resp={resp}")
            elif tus == 'h':
                pos = 0
                resp = arm.stepper_move(0)
                print(f"  HOME  resp={resp}")
            elif tus == '0':
                resp = arm.stepper_zero()
                pos = 0
                print(f"  SIFIRLA  resp={resp}")
            elif tus == 'p':
                val = arm.read_pot()
                print(f"  POT = {val}")

    except KeyboardInterrupt:
        pass

    arm.disconnect()


if __name__ == "__main__":
    main()
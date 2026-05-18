"""
Yuksek Seviye Robot Kol Kontrolu
X,Y,Z koordinatlarini direkt eklem komutlarina cevirip Nucleo'ya gonderir.
"""

from robot_arm import RobotArm
from kinematics import inverse_kinematics, joints_to_servo_angles, base_angle_to_steps
import time


class RobotArmHighLevel:
    def __init__(self, port='COM3', baudrate=115200):
        """Yuksek seviye kol kontrolu baslat."""
        self.arm = RobotArm(port=port, baudrate=baudrate)
        self.connected = False
        # Son komut acilarini hatirla (sonraki IK'lar icin baslangic noktasi)
        self.last_angles = [90, 90, 90, 90, 90, 90]

    def connect(self):
        self.connected = self.arm.connect()
        if self.connected:
            self.arm.home()
            time.sleep(2)
        return self.connected

    def disconnect(self):
        if self.connected:
            self.arm.disconnect()
            self.connected = False

    def move_to(self, x, y, z, gripper_angle=None, wait=True):
        """
        Tutucu ucunu (x, y, z) koordinatina goturur.

        Args:
            x, y, z: Hedef pozisyon (mm, robot taban merkezi orijin)
            gripper_angle: Tutucu acisi (0-180), None ise degisme
            wait: Hareketin tamamlanmasini bekle

        Returns:
            bool: Hareket basarili mi
        """
        if not self.connected:
            print("[HATA] Once connect() cagir!")
            return False

        # IK coz
        ik = inverse_kinematics(x, y, z)
        if not ik['reachable']:
            print(f"[UYARI] Erisilemez nokta: ({x}, {y}, {z}) - hata: {ik['error_mm']:.1f}mm")
            return False

        # Servo acilari hesapla
        servo_angles = joints_to_servo_angles(ik)
        if gripper_angle is not None:
            servo_angles[5] = gripper_angle

        # Taban step motor komutu (eger step motor ile yonetiliyorsa)
        # Simdilik servo 0 ile yapiyoruz, kalibrasyon sonrasi step motora gecilebilir
        base_steps = base_angle_to_steps(ik['base'])

        print(f"[INFO] Hedef: ({x:+.0f}, {y:+.0f}, {z:+.0f})")
        print(f"       Eklem: {[f'{servo_angles[i]:.0f}' for i in range(6)]}")
        print(f"       Taban step: {base_steps}")

        # Servolari komutla
        resp = self.arm.set_all_servos(servo_angles)
        print(f"       Cevap: {resp}")

        # Step motor komutu
        # self.arm.stepper_move(base_steps)  # Step motor varsa

        self.last_angles = servo_angles

        if wait:
            # Yumusak hareket icin bekle
            # Su anki hizla 20ms / 10us, yani saniyede ~500us
            # En kotu durumda 2000us hareket = 4 saniye
            time.sleep(3)

        return True

    def home(self):
        """Tum eklemleri 90 derece (nominal pozisyon)."""
        if not self.connected:
            return False
        resp = self.arm.home()
        self.last_angles = [90, 90, 90, 90, 90, 90]
        time.sleep(2)
        return True

    def gripper_open(self):
        """Tutucuyu ac."""
        return self.arm.set_servo(5, 30)

    def gripper_close(self):
        """Tutucuyu kapa."""
        return self.arm.set_servo(5, 150)

    def trace_path(self, points, gripper_states=None):
        """
        Bir dizi noktayi sirayla ziyaret et.

        Args:
            points: [(x1,y1,z1), (x2,y2,z2), ...]
            gripper_states: Her nokta icin tutucu acisi listesi, opsiyonel
        """
        for i, (x, y, z) in enumerate(points):
            grip = gripper_states[i] if gripper_states else None
            print(f"\n--- Nokta {i+1}/{len(points)} ---")
            success = self.move_to(x, y, z, gripper_angle=grip)
            if not success:
                print(f"[UYARI] Nokta {i+1} atlanildi")


# ============================================================
# DEMO: Onceden tanimli hareketler
# ============================================================

def demo_pick_and_place(robot, pick_xyz, place_xyz):
    """
    Klasik pick-and-place demosu.

    Args:
        robot: RobotArmHighLevel nesnesi
        pick_xyz: Alinacak nokta (x, y, z)
        place_xyz: Birakilacak nokta (x, y, z)
    """
    print("\n" + "=" * 50)
    print(" PICK AND PLACE DEMO")
    print("=" * 50)

    # 1. Alinacak noktanin uzerine git (yukseklik+50)
    print("\n[1] Alinacak noktanin uzerine yaklasiliyor...")
    robot.move_to(pick_xyz[0], pick_xyz[1], pick_xyz[2] + 50)

    # 2. Tutucuyu ac
    print("\n[2] Tutucu aciliyor...")
    robot.gripper_open()
    time.sleep(1)

    # 3. Asagi in
    print("\n[3] Asagi iniliyor...")
    robot.move_to(*pick_xyz)

    # 4. Tutucuyu kapat
    print("\n[4] Tutucu kapaniliyor (nesne alindi)...")
    robot.gripper_close()
    time.sleep(1)

    # 5. Yukari kaldir
    print("\n[5] Yukari kaldiriliyor...")
    robot.move_to(pick_xyz[0], pick_xyz[1], pick_xyz[2] + 50)

    # 6. Birakilacak noktanin uzerine git
    print("\n[6] Birakilacak noktanin uzerine...")
    robot.move_to(place_xyz[0], place_xyz[1], place_xyz[2] + 50)

    # 7. Asagi in
    print("\n[7] Asagi iniliyor...")
    robot.move_to(*place_xyz)

    # 8. Tutucuyu ac
    print("\n[8] Tutucu aciliyor (nesne birakildi)...")
    robot.gripper_open()
    time.sleep(1)

    # 9. Yukari kaldir
    print("\n[9] Yukari kaldiriliyor...")
    robot.move_to(place_xyz[0], place_xyz[1], place_xyz[2] + 50)

    # 10. Home
    print("\n[10] Home pozisyonuna donulüyor...")
    robot.home()


# ============================================================
# ANA TEST
# ============================================================

if __name__ == '__main__':
    port = input("Nucleo COM portu (orn. COM3): ").strip()
    if not port:
        print("Port girilmedi, cikiliyor.")
        exit()

    robot = RobotArmHighLevel(port=port)

    if not robot.connect():
        print("Baglanti basarisiz!")
        exit()

    print("\n" + "=" * 50)
    print(" ROBOT KOL - YUKSEK SEVIYE TEST")
    print("=" * 50)

    try:
        # Home pozisyon
        print("\n[Home pozisyonu]")
        robot.home()
        input("Devam icin Enter...")

        # Bir noktaya git
        print("\n[Ileri uzaniyor: (200, 0, 150)]")
        robot.move_to(200, 0, 150)
        input("Devam icin Enter...")

        # Bir kare cizdir
        print("\n[Hayali bir kare ciziyor]")
        square = [
            (150,  80, 100),
            (150, -80, 100),
            (250, -80, 100),
            (250,  80, 100),
            (150,  80, 100),
        ]
        robot.trace_path(square)
        input("Devam icin Enter...")

        # Pick and place
        print("\n[Pick and place denemesi]")
        demo_pick_and_place(
            robot,
            pick_xyz=(200, 100, 80),
            place_xyz=(200, -100, 80)
        )

    except KeyboardInterrupt:
        print("\nKullanici durdu.")
    finally:
        robot.home()
        time.sleep(2)
        robot.disconnect()
        print("\nBitti.")
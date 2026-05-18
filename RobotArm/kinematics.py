"""
Robot Kol Ters Kinematik Modulu
ikpy kutuphanesi kullanarak X,Y,Z -> eklem acilari hesaplar.

Robot kol yapisi (Denavit-Hartenberg yaklasimi):
  - Base (taban):     Z ekseni donus
  - Shoulder (omuz):  Y ekseni donus
  - Elbow (dirsek):   Y ekseni donus
  - Wrist pitch:      Y ekseni donus
  - Wrist roll:       X ekseni donus
"""

import numpy as np
from ikpy.chain import Chain
from ikpy.link import OriginLink, URDFLink


# ============================================================
# ROBOT KOL FIZIKSEL PARAMETRELERI (mm cinsinden)
# Mekanik bittiginde cetvelle olcup buradan duzelt!
# ============================================================
BASE_HEIGHT      = 80.0   # Tabandan omuz eklemine
SHOULDER_TO_ELBOW = 120.0  # Ust kol uzunlugu
ELBOW_TO_WRIST   = 120.0  # Alt kol uzunlugu
WRIST_TO_TIP     = 90.0   # Tutucu ucuna kadar


def create_robot_chain():
    """
    Robot kolun kinematik zincirini olustur.
    Returns: ikpy Chain nesnesi
    """
    chain = Chain(name='robot_arm', links=[
        # Origin (sabit referans)
        OriginLink(),

        # Joint 0: Taban donusu (Z ekseni etrafinda)
        URDFLink(
            name='base',
            origin_translation=[0, 0, 0],
            origin_orientation=[0, 0, 0],
            rotation=[0, 0, 1],  # Z ekseni
            bounds=(-np.pi, np.pi)
        ),

        # Joint 1: Omuz (Y ekseni etrafinda - yukari/asagi)
        URDFLink(
            name='shoulder',
            origin_translation=[0, 0, BASE_HEIGHT],
            origin_orientation=[0, 0, 0],
            rotation=[0, 1, 0],
            bounds=(-np.pi/2, np.pi/2)  # -90 ile +90 derece
        ),

        # Joint 2: Dirsek
        URDFLink(
            name='elbow',
            origin_translation=[0, 0, SHOULDER_TO_ELBOW],
            origin_orientation=[0, 0, 0],
            rotation=[0, 1, 0],
            bounds=(-np.pi, 0)  # Sadece bukmek (negatif)
        ),

        # Joint 3: Bilek dikey (pitch)
        URDFLink(
            name='wrist_pitch',
            origin_translation=[0, 0, ELBOW_TO_WRIST],
            origin_orientation=[0, 0, 0],
            rotation=[0, 1, 0],
            bounds=(-np.pi/2, np.pi/2)
        ),

        # Joint 4: Bilek donusu (roll)
        URDFLink(
            name='wrist_roll',
            origin_translation=[0, 0, 0],
            origin_orientation=[0, 0, 0],
            rotation=[1, 0, 0],
            bounds=(-np.pi, np.pi)
        ),

        # Tutucu ucu (sabit, eklem degil)
        URDFLink(
            name='tip',
            origin_translation=[0, 0, WRIST_TO_TIP],
            origin_orientation=[0, 0, 0],
            rotation=[0, 0, 0],
            bounds=(0, 0)
        ),
    ], active_links_mask=[False, True, True, True, True, True, False])

    return chain


# Singleton zincir
_chain = create_robot_chain()


def forward_kinematics(joint_angles_rad):
    """
    Eklem acilarindan uc nokta pozisyonunu hesapla.

    Args:
        joint_angles_rad: [base, shoulder, elbow, wrist_pitch, wrist_roll]
                         (5 eklem, radyan cinsinden)

    Returns:
        (x, y, z) tuple, mm cinsinden
    """
    # ikpy 7 elemanli vektor ister (origin + 5 joint + tip)
    full_angles = [0] + list(joint_angles_rad) + [0]
    matrix = _chain.forward_kinematics(full_angles)
    pos = matrix[:3, 3]
    return tuple(pos)


def inverse_kinematics(x, y, z, initial_guess=None):
    """
    X,Y,Z hedefinden eklem acilarini hesapla.

    Args:
        x, y, z: Hedef pozisyon (mm cinsinden, robot taban merkezi orijin)
        initial_guess: Baslangic tahmini (opsiyonel, daha iyi cozum icin)

    Returns:
        dict: {
            'base': taban acisi (derece),
            'shoulder': omuz acisi (derece),
            'elbow': dirsek acisi (derece),
            'wrist_pitch': bilek dikey acisi (derece),
            'wrist_roll': bilek donus acisi (derece),
            'reachable': bool (cozum bulundu mu),
            'error_mm': hata mesafesi
        }
    """
    target = [x, y, z]

    if initial_guess is None:
        # Tum eklemler nominal pozisyon
        initial_position = [0, 0, 0, -np.pi/2, 0, 0, 0]
    else:
        initial_position = [0] + list(np.radians(initial_guess)) + [0]

    # IK cozucu
    try:
        ik_solution = _chain.inverse_kinematics(
            target,
            initial_position=initial_position
        )
    except Exception as e:
        return {
            'reachable': False,
            'error_mm': float('inf'),
            'error_msg': str(e)
        }

    # Cozumu dogrula - gercekten istenen yere gitti mi?
    actual_pos = _chain.forward_kinematics(ik_solution)[:3, 3]
    error = np.linalg.norm(np.array(target) - actual_pos)

    # ikpy degerlerini dereceye cevir
    angles_deg = np.degrees(ik_solution[1:6])  # 5 aktif eklem

    return {
        'base':        float(angles_deg[0]),
        'shoulder':    float(angles_deg[1]),
        'elbow':       float(angles_deg[2]),
        'wrist_pitch': float(angles_deg[3]),
        'wrist_roll':  float(angles_deg[4]),
        'reachable':   error < 10.0,  # 10mm hata toleransi
        'error_mm':    float(error)
    }


def joints_to_servo_angles(ik_result):
    """
    IK cozumunden Nucleo'ya gonderilecek servo acilarini hazirla.

    IK acilari -180 ile +180 derece arasi (mekanik aci).
    Servo acilari 0-180 derece (PWM acisi).
    Bu donusumu kalibre etmek lazim - simdilik basit offset.

    Args:
        ik_result: inverse_kinematics() cikti dictionary'si

    Returns:
        list: [s0, s1, s2, s3, s4, s5]
              s5 (gripper) IK'da yok, varsayilan 90.
    """
    if not ik_result['reachable']:
        return None

    # Eklem acisindan servo acisina donusum
    # Servo 0 step motorda olsa da simdilik servo gibi gosterelim
    # (Gerceginde taban step motor ile donecek)

    s0_deg = ik_result['base'] + 90        # -90..+90  ->  0..180
    s1_deg = ik_result['shoulder'] + 90    # -90..+90  ->  0..180
    s2_deg = ik_result['elbow'] + 180      # -180..0   ->  0..180
    s3_deg = ik_result['wrist_pitch'] + 90 # -90..+90  ->  0..180
    s4_deg = ik_result['wrist_roll'] + 90  # -90..+90  ->  0..180
    s5_deg = 90                            # Gripper varsayilan

    # Sinir kontrolu
    servo_angles = []
    for a in [s0_deg, s1_deg, s2_deg, s3_deg, s4_deg, s5_deg]:
        a = max(0, min(180, a))
        servo_angles.append(a)

    return servo_angles


def base_angle_to_steps(base_deg, steps_per_rev=3200, gear_ratio=1.0):
    """
    Taban donus acisini step motor adimlarina cevir.

    Args:
        base_deg: -180 ile +180 arasi taban acisi
        steps_per_rev: Tam tur icin step sayisi (1/16 microstep ile 3200)
        gear_ratio: Disli orani (varsa)

    Returns:
        int: step sayisi (yon dahil, +/-)
    """
    total_steps_per_rev = steps_per_rev * gear_ratio
    steps = int((base_deg / 360.0) * total_steps_per_rev)
    return steps


# ============================================================
# TEST FONKSIYONLARI
# ============================================================

if __name__ == '__main__':
    print("=" * 60)
    print(" ROBOT KOL TERS KINEMATIK TESTI")
    print("=" * 60)
    print(f"\nRobot kol boyutlari:")
    print(f"  Taban yuksekligi:  {BASE_HEIGHT} mm")
    print(f"  Ust kol:           {SHOULDER_TO_ELBOW} mm")
    print(f"  Alt kol:           {ELBOW_TO_WRIST} mm")
    print(f"  Bilek - uc:        {WRIST_TO_TIP} mm")
    print(f"  Maks erisim:       ~{SHOULDER_TO_ELBOW + ELBOW_TO_WRIST + WRIST_TO_TIP} mm")

    # Test pozisyonlari
    test_targets = [
        (200, 0, 150,  "Onde, orta yukseklik"),
        (150, 100, 100, "Sag onde"),
        (-150, 100, 100, "Sol onde"),
        (0, 0, 350,    "Tam yukari"),
        (250, 0, 80,   "Onde, asagi"),
        (100, 0, 200,  "Yakin one"),
        (500, 0, 100,  "Cok uzakta (erisilemez)"),
    ]

    print("\n" + "=" * 60)
    print(" Test Sonuclari")
    print("=" * 60)

    for x, y, z, desc in test_targets:
        result = inverse_kinematics(x, y, z)
        print(f"\nHedef: ({x:+4d}, {y:+4d}, {z:+4d}) mm  --  {desc}")

        if result['reachable']:
            print(f"  Cozum bulundu (hata: {result['error_mm']:.2f}mm)")
            print(f"  Eklem acilari (derece):")
            print(f"    Taban:        {result['base']:+7.2f}")
            print(f"    Omuz:         {result['shoulder']:+7.2f}")
            print(f"    Dirsek:       {result['elbow']:+7.2f}")
            print(f"    Bilek dikey:  {result['wrist_pitch']:+7.2f}")
            print(f"    Bilek donus:  {result['wrist_roll']:+7.2f}")

            servo_angles = joints_to_servo_angles(result)
            if servo_angles:
                print(f"  Servo acilari: {[f'{a:.1f}' for a in servo_angles]}")

            steps = base_angle_to_steps(result['base'])
            print(f"  Taban step:   {steps}")
        else:
            print(f"  ERISILEMEZ - hata: {result['error_mm']:.1f}mm")
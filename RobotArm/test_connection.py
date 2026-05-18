"""
Nucleo Baglanti Testi
Once bu scripti calistir, baglanti calisiyor mu gor.
"""

import serial
import serial.tools.list_ports
import time


def list_available_ports():
    """Bilgisayardaki tum seri portlari listele."""
    print("\n=== Mevcut Seri Portlar ===")
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("Hicbir seri port bulunamadi!")
        return []

    available = []
    for port in ports:
        print(f"  {port.device:12s} - {port.description}")
        available.append(port.device)
    return available


def test_nucleo(port_name, baudrate=115200):
    """Nucleo ile baglanti testi yap."""
    print(f"\n=== {port_name} portu test ediliyor ===")

    try:
        ser = serial.Serial(port_name, baudrate, timeout=2)
        time.sleep(2)  # Nucleo boot suresi
        ser.reset_input_buffer()

        # Ping gonder
        print("Ping gonderiliyor: 'P'")
        ser.write(b'P\n')

        # Cevap bekle
        response = ser.readline().decode('ascii', errors='ignore').strip()
        print(f"Cevap: '{response}'")

        if response == 'PONG':
            print("[OK] Nucleo cevap veriyor! Baglanti calisiyor.")

            # Birkac komut daha test
            print("\nHome komutu gonderiliyor: 'H'")
            ser.write(b'H\n')
            print(f"Cevap: {ser.readline().decode('ascii', errors='ignore').strip()}")

            print("\nServo 0 -> 45 derece: 'S0:45'")
            ser.write(b'S0:45\n')
            print(f"Cevap: {ser.readline().decode('ascii', errors='ignore').strip()}")

            print("\nPotansiyometre okuma: 'R'")
            ser.write(b'R\n')
            print(f"Cevap: {ser.readline().decode('ascii', errors='ignore').strip()}")

            ser.close()
            return True
        else:
            print(f"[UYARI] Beklenmedik cevap: '{response}'")
            print("       Belki yanlis port veya kod yuklenmedi?")
            ser.close()
            return False

    except serial.SerialException as e:
        print(f"[HATA] {e}")
        return False


if __name__ == '__main__':
    print("=" * 50)
    print("  Robot Kol - Nucleo Baglanti Testi")
    print("=" * 50)

    # 1. Mevcut portlari goster
    ports = list_available_ports()

    if not ports:
        print("\nNucleo USB ile bagli mi? Sonra tekrar dene.")
        exit()

    # 2. Kullanicidan port secimi
    print("\nYukaridaki portlardan Nucleo'nunki hangisi?")
    print("(STMicroelectronics yazan satira bak.)")
    port = input("Port adi (orn. COM5): ").strip()

    if not port:
        print("Port girilmedi, cikiyorum.")
        exit()

    # 3. Test et
    if test_nucleo(port):
        print("\n" + "=" * 50)
        print("  TEST BASARILI - Devam edebilirsin")
        print("=" * 50)
        print(f"\nBu portu hatirla: {port}")
        print("Diger scriptlerde de bu portu kullanacaksin.")
    else:
        print("\n" + "=" * 50)
        print("  TEST BASARISIZ")
        print("=" * 50)
        print("\nKontrol et:")
        print("  1. Nucleo USB ile bagli mi?")
        print("  2. Kod yuklendi mi? (Run As -> STM32 Application)")
        print("  3. Nucleo'ya reset attin mi? (siyah B2 butonu)")
        print("  4. Dogru COM portu secildi mi?")
"""
Mikrofon Test Scripti
3 saniye ses kaydeder ve seviyeyi gosterir.
"""

import sounddevice as sd
import numpy as np


def list_devices():
    """Mevcut ses cihazlarini listele."""
    print("\n=== Mevcut Ses Cihazlari ===")
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        # Sadece giris kapasitesi olanlari goster
        if dev['max_input_channels'] > 0:
            default_marker = " [VARSAYILAN]" if i == sd.default.device[0] else ""
            print(f"  [{i}] {dev['name']}  (kanal: {dev['max_input_channels']}){default_marker}")
    print()


def test_microphone(duration=3, sample_rate=16000):
    """Mikrofondan ses kaydet ve seviyeyi olc."""
    print(f"\n{duration} saniye ses kaydedilecek. Bir sey soyle...")
    print("3...")
    sd.sleep(1000)
    print("2...")
    sd.sleep(1000)
    print("1...")
    sd.sleep(500)
    print("KAYIT BASLADI - KONUS!")

    # Ses kaydet (mono, 16kHz)
    recording = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype='float32'
    )
    sd.wait()  # Kaydin bitmesini bekle

    print("KAYIT BITTI.\n")

    # Ses seviyesini analiz et
    audio = recording.flatten()
    max_amp = np.max(np.abs(audio))
    rms = np.sqrt(np.mean(audio**2))

    print(f"Maksimum genlik: {max_amp:.4f}")
    print(f"RMS (ortalama):  {rms:.4f}")

    # Yorumla
    if max_amp < 0.001:
        print("\n[UYARI] Hic ses algilanmadi!")
        print("  - Mikrofon mute olabilir")
        print("  - Yanlis cihaz secili olabilir")
        print("  - Mikrofon takili degil olabilir")
        return False
    elif max_amp < 0.01:
        print("\n[UYARI] Ses cok dusuk!")
        print("  - Mikrofona daha yakin konus")
        print("  - Sistem ayarlarinda mikrofon ses seviyesini artir")
        return False
    elif max_amp > 0.95:
        print("\n[UYARI] Ses doyuyor (clipping)!")
        print("  - Mikrofona daha uzak dur")
        print("  - Sistem ayarlarinda mikrofon ses seviyesini dusur")
        return True  # yine de calisir
    else:
        print("\n[OK] Mikrofon iyi calisiyor!")
        return True


if __name__ == '__main__':
    print("=" * 50)
    print(" MIKROFON TEST")
    print("=" * 50)

    list_devices()

    input("Enter'a basinca test baslayacak...")
    test_microphone(duration=3)

    print("\nTest tamamlandi.")
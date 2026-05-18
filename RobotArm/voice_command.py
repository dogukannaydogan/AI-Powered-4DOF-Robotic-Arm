"""
Sesli Komut Tanima Modulu (Whisper)
Mikrofondan ses al, metne cevir, komut yorumla.
"""

import sounddevice as sd
import numpy as np
import re
import time
from faster_whisper import WhisperModel


# ============================================================
# WHISPER MODELI - ilk calistirildiginda model iner (~250MB)
# ============================================================
print("[INFO] Whisper modeli yukleniyor (ilk seferde indirme yapar)...")
_model = WhisperModel(
    "small",          # small / base / medium / large
    device="cpu",     # GPU varsa "cuda"
    compute_type="int8"  # CPU'da en hizli
)
print("[INFO] Whisper hazir.")


# ============================================================
# KAYIT AYARLARI
# ============================================================
SAMPLE_RATE = 16000  # Whisper bunu istiyor
CHANNELS = 1


def record_audio(duration=4):
    """
    Mikrofondan belirli sure ses kaydet.

    Args:
        duration: Saniye cinsinden kayit suresi

    Returns:
        numpy array (audio data)
    """
    print(f"\n[KAYIT] {duration} saniye dinleniyor... KONUS!")
    recording = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype='float32'
    )
    sd.wait()
    print("[KAYIT] Bitti.")
    return recording.flatten()


def transcribe(audio_data, language='tr'):
    """
    Ses datasini metne cevir.

    Args:
        audio_data: numpy array
        language: 'tr' (Turkce), 'en', vb.

    Returns:
        str: Tanima sonucu metin
    """
    print("[WHISPER] Tanima yapiliyor...")
    start = time.time()

    segments, info = _model.transcribe(
        audio_data,
        language=language,
        beam_size=5,
        vad_filter=True,  # Sessiz kisimlari atla
        vad_parameters=dict(min_silence_duration_ms=500)
    )

    text = ""
    for segment in segments:
        text += segment.text

    elapsed = time.time() - start
    text = text.strip()
    print(f"[WHISPER] {elapsed:.2f}s -> '{text}'")
    return text


def listen_and_transcribe(duration=4, language='tr'):
    """Tek seferde dinle ve metne cevir."""
    audio = record_audio(duration)
    return transcribe(audio, language)


# ============================================================
# KOMUT YORUMLAMA
# ============================================================

def parse_command(text):
    """
    Metni anlamli komuta cevir.

    Ornek girisler:
        "kirmizi topu al"           -> {'action': 'pick', 'color': 'red', 'object': 'top'}
        "home pozisyonuna git"      -> {'action': 'home'}
        "tutucuyu ac"               -> {'action': 'gripper_open'}
        "tutucuyu kapat"            -> {'action': 'gripper_close'}
        "yukari git"                -> {'action': 'move', 'direction': 'up'}
        "dur"                       -> {'action': 'stop'}

    Args:
        text: Whisper'dan gelen metin

    Returns:
        dict: Komut yapisi veya None (anlasilmadiysa)
    """
    text = text.lower().strip()
    if not text:
        return None

    # Renk kelimeleri
    colors = {
        'kirmizi': 'red', 'kırmızı': 'red',
        'mavi': 'blue',
        'yesil': 'green', 'yeşil': 'green',
        'sari': 'yellow', 'sarı': 'yellow',
        'siyah': 'black',
        'beyaz': 'white'
    }

    # Nesne kelimeleri
    objects = ['top', 'küp', 'kup', 'kutu', 'şişe', 'sise', 'nesne', 'cisim']

    # ---- DURDUR KOMUTU ----
    if any(w in text for w in ['dur', 'stop', 'bekle']):
        return {'action': 'stop'}

    # ---- HOME KOMUTU ----
    if any(w in text for w in ['home', 'baslangic', 'başlangıç',
                                 'sifirla', 'sıfırla', 'merkez']):
        return {'action': 'home'}

    # ---- TUTUCU KOMUTLARI ----
    if any(w in text for w in ['ac', 'aç']) and \
       any(w in text for w in ['tutucu', 'pence', 'parmak', 'gripper']):
        return {'action': 'gripper_open'}

    if any(w in text for w in ['kapa', 'sik', 'sık', 'tut']) and \
       any(w in text for w in ['tutucu', 'pence', 'parmak', 'gripper']):
        return {'action': 'gripper_close'}

    # ---- YONLU HAREKET ----
    directions = {
        'yukari': 'up', 'yukarı': 'up',
        'asagi': 'down', 'aşağı': 'down',
        'sag': 'right', 'sağ': 'right',
        'sol': 'left',
        'ileri': 'forward',
        'geri': 'backward'
    }
    for word, direction in directions.items():
        if word in text:
            return {'action': 'move', 'direction': direction}

    # ---- AL / TUT KOMUTLARI (renk + nesne) ----
    if any(w in text for w in ['al', 'tut', 'getir', 'yakala']):
        color_detected = None
        for word, color in colors.items():
            if word in text:
                color_detected = color
                break

        object_detected = None
        for obj in objects:
            if obj in text:
                object_detected = obj
                break

        if color_detected or object_detected:
            return {
                'action': 'pick',
                'color': color_detected,
                'object': object_detected
            }

    # ---- BIRAK KOMUTU ----
    if any(w in text for w in ['birak', 'bırak', 'koy']):
        return {'action': 'place'}

    # Anlasilmadi
    return None


# ============================================================
# ANA TEST
# ============================================================

def demo():
    """Sesli komut demo - 10 komut dinle, yorumla, goster."""
    print("\n" + "=" * 50)
    print(" SESLI KOMUT DEMO")
    print("=" * 50)
    print("\nOrnek komutlar:")
    print('  "Kirmizi topu al"')
    print('  "Home pozisyonuna git"')
    print('  "Tutucuyu ac"')
    print('  "Tutucuyu kapat"')
    print('  "Sola git"')
    print('  "Dur"')
    print("\nCikis: Ctrl+C")

    try:
        while True:
            input("\nEnter'a bas, sonra konus...")
            text = listen_and_transcribe(duration=4)

            cmd = parse_command(text)
            print(f"\n  Metin:  '{text}'")
            print(f"  Komut:  {cmd}")

    except KeyboardInterrupt:
        print("\n\nCikiliyor.")


if __name__ == '__main__':
    demo()
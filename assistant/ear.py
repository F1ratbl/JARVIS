"""
🎤 JARVIS — Kulak Modülü (Dinleme + STT)
Wake word (openWakeWord) veya Push-to-Talk destekli.
Ses kaydı + Whisper ile konuşmayı metne çevirme.
"""

import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import os
import sys
from collections import deque

from assistant.config import (
    SAMPLE_RATE, RECORD_DURATION, TEMP_AUDIO_FILE,
    RECORD_DYNAMIC_ENABLED, MIN_RECORD_DURATION, MAX_RECORD_DURATION,
    SILENCE_DURATION, SILENCE_THRESHOLD, PRE_ROLL_DURATION,
    AUDIO_NORMALIZE_TARGET,
    WHISPER_LANGUAGE, WHISPER_BEAM_SIZE, WHISPER_VAD_FILTER,
    WHISPER_NO_SPEECH_THRESHOLD, WHISPER_CONDITION_ON_PREVIOUS_TEXT,
    WHISPER_INITIAL_PROMPT,
    WAKE_WORD_ENABLED, WAKE_WORD_MODEL, WAKE_WORD_THRESHOLD, WAKE_WORD_CHUNK_SIZE,
    DEBUG
)
from core.loader import global_loader

# Whisper modelini bir kere yükle (her çağrıda tekrar yükleme)
_whisper_model = None
# openWakeWord modelini bir kere yükle
_oww_model = None


def _get_whisper_model():
    """Whisper modelini lazy-load ile yükler."""
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = global_loader.get("whisper")
    return _whisper_model


def _get_oww_model():
    """openWakeWord modelini lazy-load ile yükler."""
    global _oww_model
    if _oww_model is None:
        _oww_model = global_loader.get("wake_word")
    return _oww_model


# ────────────────────────────────────────
# 🎯 WAKE WORD — Uyanma Kelimesi
# ────────────────────────────────────────

def listen_for_wake_word():
    """
    Wake word algılama.
    WAKE_WORD_ENABLED=True → openWakeWord ile 'Hey Jarvis' dinler.
    WAKE_WORD_ENABLED=False → Push-to-Talk modunda Enter tuşunu bekler.
    """
    if WAKE_WORD_ENABLED:
        return _listen_openwakeword()
    else:
        return _listen_push_to_talk()


def _listen_openwakeword():
    """openWakeWord ile wake word algılama — tamamen açık kaynak, API key gerektirmez."""
    try:
        import pyaudio

        model = _get_oww_model()
        if model is None:
            print("⚠️  openWakeWord yüklenemedi. Push-to-talk moduna geçiliyor...")
            return _listen_push_to_talk()

        # PyAudio ile mikrofon akışı
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=WAKE_WORD_CHUNK_SIZE
        )

        if DEBUG:
            print(f"👂 'Hey Jarvis' bekleniyor... (openWakeWord)")

        try:
            while True:
                # 80ms'lik ses parçası oku
                audio_data = stream.read(WAKE_WORD_CHUNK_SIZE, exception_on_overflow=False)
                audio_array = np.frombuffer(audio_data, dtype=np.int16)

                # Tahmin yap
                prediction = model.predict(audio_array)

                # hey_jarvis modeli için kontrol
                for model_name, score in prediction.items():
                    if WAKE_WORD_MODEL in model_name and score > WAKE_WORD_THRESHOLD:
                        if DEBUG:
                            print(f"🎯 Wake word algılandı! (skor: {score:.2f})")
                        # Modeli sıfırla (bir sonraki algılama için)
                        model.reset()
                        return True

        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()

    except ImportError:
        print("⚠️  openwakeword veya pyaudio yüklü değil. Push-to-talk moduna geçiliyor...")
        print("💡  Yüklemek için: pip install openwakeword pyaudio")
        return _listen_push_to_talk()
    except Exception as e:
        print(f"⚠️  openWakeWord hatası: {e}. Push-to-talk moduna geçiliyor...")
        return _listen_push_to_talk()


def _listen_push_to_talk():
    """Push-to-Talk: Enter tuşuna basarak aktifleştirme."""
    try:
        input("\n⏎  Konuşmak için ENTER'a basın...")
        return True
    except (EOFError, KeyboardInterrupt):
        return False


# ────────────────────────────────────────
# 🎤 SES KAYDI
# ────────────────────────────────────────

def _audio_rms(audio_chunk: np.ndarray) -> float:
    """Float audio chunk icin RMS seviye hesaplar."""
    if audio_chunk.size == 0:
        return 0.0
    audio = audio_chunk.astype(np.float32).reshape(-1)
    return float(np.sqrt(np.mean(np.square(audio))))


def _normalize_audio(audio_data: np.ndarray) -> np.ndarray:
    """Kaydedilen sesi int16 WAV'a guvenli sekilde normalize eder."""
    audio = audio_data.astype(np.float32).reshape(-1)
    if audio.size == 0:
        return np.array([], dtype=np.int16)

    peak = float(np.max(np.abs(audio)))
    if peak > 0:
        target = max(0.1, min(1.0, AUDIO_NORMALIZE_TARGET))
        audio = audio * min(target / peak, 12.0)

    audio = np.clip(audio, -1.0, 1.0)
    return (audio * 32767).astype(np.int16).reshape(-1, 1)


def _write_audio(filename: str, audio_data: np.ndarray) -> str:
    """Audio verisini normalize edip WAV dosyasina yazar."""
    wav.write(filename, SAMPLE_RATE, _normalize_audio(audio_data))
    return filename


def _record_fixed_duration(filename: str, duration: float) -> str | None:
    """Eski davranis: belirli sure boyunca kayit alir."""
    audio_data = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32"
    )
    sd.wait()
    return _write_audio(filename, audio_data)


def _record_until_silence(filename: str) -> str | None:
    """Konusmayi algilar, sessizlikte kaydi bitirir."""
    block_duration = 0.10
    block_size = int(SAMPLE_RATE * block_duration)
    min_blocks = max(1, int(MIN_RECORD_DURATION / block_duration))
    max_blocks = max(min_blocks, int(MAX_RECORD_DURATION / block_duration))
    fallback_blocks = max(min_blocks, int(RECORD_DURATION / block_duration))
    silence_blocks_needed = max(1, int(SILENCE_DURATION / block_duration))
    pre_roll_blocks = max(1, int(PRE_ROLL_DURATION / block_duration))

    frames = []
    pre_roll = deque(maxlen=pre_roll_blocks)
    speech_seen = False
    silence_blocks = 0
    noise_floor = SILENCE_THRESHOLD / 3.0
    active_threshold = SILENCE_THRESHOLD

    print(f"🎤 Dinleniyor (en fazla {MAX_RECORD_DURATION} saniye)...")

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=block_size
    ) as stream:
        for block_index in range(max_blocks):
            audio_chunk, overflowed = stream.read(block_size)
            chunk = np.array(audio_chunk, copy=True)
            rms = _audio_rms(chunk)

            if not speech_seen:
                noise_floor = (noise_floor * 0.90) + (min(rms, SILENCE_THRESHOLD) * 0.10)
                active_threshold = max(SILENCE_THRESHOLD, noise_floor * 3.0)

            is_voice = rms >= active_threshold

            if is_voice and not speech_seen:
                speech_seen = True
                frames.extend(pre_roll)
                if DEBUG:
                    print(f"🎙️  Konuşma algılandı (rms={rms:.4f}, eşik={active_threshold:.4f})")

            if speech_seen:
                frames.append(chunk)
                silence_blocks = 0 if is_voice else silence_blocks + 1
            else:
                pre_roll.append(chunk)

            enough_audio = len(frames) >= min_blocks
            enough_silence = silence_blocks >= silence_blocks_needed
            no_speech_timeout = not speech_seen and block_index >= fallback_blocks

            if overflowed and DEBUG:
                print("⚠️  Mikrofon buffer taşması algılandı.")

            if (speech_seen and enough_audio and enough_silence) or no_speech_timeout:
                break

    if not frames:
        frames = list(pre_roll)

    if DEBUG:
        duration = (sum(frame.shape[0] for frame in frames) / SAMPLE_RATE) if frames else 0
        print(f"✅ Kayıt tamamlandı ({duration:.1f} saniye).")

    if not frames:
        return None

    return _write_audio(filename, np.concatenate(frames, axis=0))


def record_audio(filename=None, duration=None):
    """Mikrofondan ses kaydeder ve WAV dosyasına yazar."""
    filename = filename or TEMP_AUDIO_FILE
    fixed_duration = duration is not None
    duration = duration or RECORD_DURATION
    
    if fixed_duration or not RECORD_DYNAMIC_ENABLED:
        print(f"🎤 Dinleniyor ({duration} saniye)...")
    
    try:
        if fixed_duration or not RECORD_DYNAMIC_ENABLED:
            recorded_file = _record_fixed_duration(filename, duration)
        else:
            recorded_file = _record_until_silence(filename)

        if not recorded_file:
            return None
        
        if DEBUG:
            print("✅ Kayıt tamamlandı.")
        
        return recorded_file
        
    except Exception as e:
        print(f"❌ Kayıt hatası: {e}")
        return None


# ────────────────────────────────────────
# 📝 TRANSKRİPSİYON (STT)
# ────────────────────────────────────────

def transcribe_audio(filename=None):
    """Ses dosyasını Whisper ile metne çevirir."""
    filename = filename or TEMP_AUDIO_FILE
    
    if not os.path.exists(filename):
        print("❌ Ses dosyası bulunamadı!")
        return ""
    
    model = _get_whisper_model()
    
    try:
        segments, info = model.transcribe(
            filename,
            language=WHISPER_LANGUAGE,
            beam_size=WHISPER_BEAM_SIZE,
            vad_filter=WHISPER_VAD_FILTER,
            vad_parameters={
                "min_silence_duration_ms": 500,
                "speech_pad_ms": 250,
            },
            no_speech_threshold=WHISPER_NO_SPEECH_THRESHOLD,
            condition_on_previous_text=WHISPER_CONDITION_ON_PREVIOUS_TEXT,
            initial_prompt=WHISPER_INITIAL_PROMPT,
        )
        
        if DEBUG:
            print(f"🔍 Dil olasılığı: %{info.language_probability * 100:.0f}")
        
        full_text = ""
        for segment in segments:
            full_text += segment.text + " "
        
        text = full_text.strip()
        
        if DEBUG and text:
            print(f"📝 Algılanan metin: \"{text}\"")
        
        return text
        
    except Exception as e:
        print(f"❌ Transkripsiyon hatası: {e}")
        return ""


# ────────────────────────────────────────
# 🔄 BİRLEŞİK FONKSİYON
# ────────────────────────────────────────

def record_and_transcribe(duration=None):
    """Ses kaydeder ve metne çevirir. Tek fonksiyonda tüm süreç."""
    filename = record_audio(duration=duration)
    
    if not filename:
        return ""
    
    text = transcribe_audio(filename)
    cleanup(filename)
    
    return text


def listen():
    """
    Tam dinleme süreci:
    1. Wake word bekle
    2. Komutu kaydet
    3. Metne çevir
    4. Metni döndür
    """
    if listen_for_wake_word():
        return record_and_transcribe()
    return ""


# ────────────────────────────────────────
# 🧹 TEMİZLİK
# ────────────────────────────────────────

def cleanup(filename=None):
    """Geçici ses dosyasını siler."""
    filename = filename or TEMP_AUDIO_FILE
    if os.path.exists(filename):
        os.remove(filename)


# --- TEST ---
if __name__ == "__main__":
    print("🎤 Ear modülü test ediliyor...")
    print("openWakeWord wake word testi — 'Hey Jarvis' deyin!")
    try:
        if listen_for_wake_word():
            print("✅ Wake word algılandı! Şimdi komutunuzu söyleyin...")
            text = record_and_transcribe()
            if text:
                print(f"\n✅ Sonuç: {text}")
            else:
                print("\n⚠️  Ses algılanamadı.")
        else:
            print("❌ Wake word algılanamadı.")
    except KeyboardInterrupt:
        print("\n👋 Test sonlandırıldı.")
    except Exception as e:
        print(f"❌ Hata: {e}")

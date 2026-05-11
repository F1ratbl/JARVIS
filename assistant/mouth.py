"""
🗣️ JARVIS — Ağız Modülü (Text-to-Speech)
macOS 'say' komutu (birincil) + Google TTS (yedek) desteği.
"""

import subprocess
import os
import tempfile
from assistant.config import TTS_ENGINE, TTS_VOICE, TTS_RATE, DEBUG


def speak(text: str):
    """Ana TTS fonksiyonu — config'e göre doğru motoru çağırır."""
    if not text:
        return

    if DEBUG:
        print(f"🗣️  Jarvis: {text}")

    if TTS_ENGINE == "macos_say":
        _speak_macos(text)
    elif TTS_ENGINE == "gtts":
        _speak_gtts(text)
    else:
        # Fallback olarak her zaman macOS say
        _speak_macos(text)


def _speak_macos(text: str):
    """macOS yerleşik 'say' komutu — hızlı ve çevrimdışı çalışır."""
    try:
        cmd = ["say"]
        
        # Türkçe ses varsa kullan
        if TTS_VOICE:
            cmd.extend(["-v", TTS_VOICE])
        
        # Konuşma hızı
        if TTS_RATE:
            cmd.extend(["-r", str(TTS_RATE)])
        
        cmd.append(text)
        subprocess.run(cmd, check=True, capture_output=True)
        
    except subprocess.CalledProcessError:
        # Belirtilen ses bulunamazsa varsayılan sesle dene
        if DEBUG:
            print(f"⚠️  '{TTS_VOICE}' sesi bulunamadı, varsayılan ses kullanılıyor.")
        try:
            subprocess.run(["say", "-r", str(TTS_RATE), text], check=True, capture_output=True)
        except Exception as e:
            print(f"❌ TTS Hatası: {e}")


def _speak_gtts(text: str):
    """Google TTS — daha doğal ses, internet bağlantısı gerektirir."""
    from core.loader import global_loader
    
    # LazyLoader üzerinden gtts'i yükle
    gtts_module = global_loader.get("tts")
    if gtts_module is None or gtts_module is True:  # True = macos_say fallback
        print("⚠️  gTTS yüklenemedi. macOS say'e geçiliyor...")
        _speak_macos(text)
        return

    try:
        from gtts import gTTS
        
        # Geçici dosya oluştur
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
        
        # Sesi oluştur
        tts = gTTS(text=text, lang="tr")
        tts.save(tmp_path)
        
        # macOS'ta afplay ile çal (harici bağımlılık gerektirmez)
        subprocess.run(["afplay", tmp_path], check=True)
        
        # Temizle
        os.unlink(tmp_path)
        
    except Exception as e:
        print(f"❌ gTTS Hatası: {e}")
        _speak_macos(text)


def list_available_voices():
    """macOS'ta mevcut TTS seslerini listeler."""
    result = subprocess.run(
        ["say", "-v", "?"],
        capture_output=True, text=True
    )
    voices = result.stdout.strip().split("\n")
    turkish_voices = [v for v in voices if "tr_" in v.lower() or "turk" in v.lower()]
    
    if turkish_voices:
        print("🇹🇷 Mevcut Türkçe sesler:")
        for v in turkish_voices:
            print(f"   {v}")
    else:
        print("⚠️  Türkçe ses bulunamadı. Varsayılan ses kullanılacak.")
        print("   Tüm sesler:")
        for v in voices[:10]:
            print(f"   {v}")
    
    return voices


# --- TEST ---
if __name__ == "__main__":
    print("🗣️  Mouth modülü test ediliyor...")
    list_available_voices()
    speak("Merhaba efendim, Jarvis hazır ve hizmetinizde.")

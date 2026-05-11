"""
🤖 JARVIS — Ana Orkestrasyon Döngüsü
Tüm modülleri birleştiren entry point.

Kullanım:
    python -m app.main
    
Modüller:
    - assistant/ear.py    → Dinleme (Wake Word + STT)
    - assistant/brain.py  → Düşünme (LLM + JSON)
    - assistant/hands.py  → Uygulama (macOS Otomasyon)
    - assistant/mouth.py  → Konuşma (TTS)
"""

import sys
import signal
from assistant.config import DEBUG, WAKE_WORD_ENABLED
from core.loader import global_loader
from core.metrics import LatencyTracker

# ────────────────────────────────────────
# 🎨 BANNER
# ────────────────────────────────────────

BANNER = """
╔══════════════════════════════════════════════════╗
║                                                  ║
║         ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗  ║
║         ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝  ║
║         ██║███████║██████╔╝██║   ██║██║███████╗  ║
║    ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║  ║
║    ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║  ║
║     ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝  ║
║                                                  ║
║        🤖 Yerel AI Asistan — macOS Edition       ║
║                                                  ║
╚══════════════════════════════════════════════════╝
"""


def print_status():
    """Sistem durumunu gösterir."""
    mode = "🎯 openWakeWord (Hey Jarvis)" if WAKE_WORD_ENABLED else "⏎  Push-to-Talk (Enter)"
    print(f"""
┌─────────────────────────────────────┐
│  Mod     : {mode:<25}│
│  Model   : Yerel Ollama             │
│  STT     : Whisper (faster-whisper)  │
│  TTS     : macOS say                 │
│  Çıkış   : Ctrl+C veya 'çık' deyin  │
└─────────────────────────────────────┘
""")


# ────────────────────────────────────────
# 🚀 ANA DÖNGÜ
# ────────────────────────────────────────

def main():
    """Jarvis ana çalışma döngüsü."""
    
    print(BANNER)
    
    # Durum bilgisini LazyLoader üzerinden göster
    print(global_loader.status())
    print()
    print_status()
    
    # Modülleri içe aktar (LazyLoader ile güvenli)
    from assistant import brain, ear, hands, mouth
    
    # Hoş geldin mesajı
    print("🚀 Jarvis başlatılıyor...\n")
    mouth.speak("Jarvis hazır efendim. Size nasıl yardımcı olabilirim?")
    
    # Ctrl+C ile düzgün çıkış
    def signal_handler(sig, frame):
        print("\n\n👋 Jarvis kapatılıyor...")
        mouth.speak("Hoşça kalın efendim.")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # ── ANA DÖNGÜ ──
    while True:
        try:
            # 1️⃣ Wake word veya Enter bekle
            if not ear.listen_for_wake_word():
                continue
            
            # 2️⃣ Onay sesi
            mouth.speak("Buyurun efendim.")

            tracker = LatencyTracker()
            
            # 3️⃣ Komutu dinle ve metne çevir
            command_text = ear.record_and_transcribe()
            tracker.mark("stt")
            
            if not command_text:
                mouth.speak("Sizi anlayamadım efendim, tekrar söyler misiniz?")
                continue
            
            # Çıkış komutları
            exit_commands = ["çık", "kapat", "durdur", "kapa kendini", "güle güle", "bye"]
            if any(cmd in command_text.lower() for cmd in exit_commands):
                mouth.speak("Hoşça kalın efendim. İyi günler dilerim.")
                print("👋 Jarvis kapatıldı.")
                break
            
            # 4️⃣ Beyine gönder — LLM karar versin
            command_json = brain.process_command(command_text)
            tracker.mark("llm")
            
            if not command_json:
                mouth.speak("Bu komutu işleyemedim efendim. Ollama çalıştığından emin misiniz?")
                continue
            
            # 5️⃣ Eylemi gerçekleştir
            result = hands.execute_action(command_json)
            tracker.mark("action")
            
            # 6️⃣ Sonucu söyle
            if result:
                mouth.speak(result)
            tracker.mark("tts")

            if DEBUG:
                print(f"⏱️  Latency: {tracker.summary()}")
            
            print()  # Görsel ayırıcı
            
        except KeyboardInterrupt:
            print("\n\n👋 Jarvis kapatılıyor...")
            mouth.speak("Hoşça kalın efendim.")
            break
        except Exception as e:
            if DEBUG:
                print(f"❌ Beklenmeyen hata: {e}")
                import traceback
                traceback.print_exc()
            mouth.speak("Bir hata oluştu efendim, tekrar deneyelim.")
            continue

    print("\n🤖 Jarvis oturumu sona erdi.")


# ────────────────────────────────────────
# 🏁 ENTRY POINT
# ────────────────────────────────────────

if __name__ == "__main__":
    main()

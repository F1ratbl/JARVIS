"""
🤖 JARVIS — Merkezi Yapılandırma Dosyası
Tüm modüller bu dosyadan ayarları import eder.
"""

# ────────────────────────────────────────
# 🧠 LLM (Ollama) Ayarları
# ────────────────────────────────────────
OLLAMA_MODEL = "qwen2.5:7b"  # Daha iyi Türkçe/JSON/tool takibi için yerel model; "auto" RAM'e göre seçer
OLLAMA_TEMPERATURE = 0.0   # Komut ayrıştırmada tutarlı JSON için düşük sıcaklık
OLLAMA_NUM_CTX = 2048      # Komut JSON'u için daha küçük ve hızlı bağlam penceresi
OLLAMA_KEEP_ALIVE = "30m"  # Modeli her komuttan sonra hemen boşaltma; ilk yanıt gecikmesini azaltır
WEB_SEARCH_USE_LLM_SUMMARY = False  # False: hızlı snippet cevabı, True: daha yavaş LLM özeti

# ────────────────────────────────────────
# 🎤 Ses Kayıt Ayarları
# ────────────────────────────────────────
SAMPLE_RATE = 16000          # Hz
RECORD_DURATION = 5          # saniye
TEMP_AUDIO_FILE = "temp_audio.wav"

# Dinamik kayıt: konuşma başlayınca kaydet, sessizlikte bitir.
RECORD_DYNAMIC_ENABLED = True
MIN_RECORD_DURATION = 0.8     # saniye, yanlışlıkla erken kesmeyi önler
MAX_RECORD_DURATION = 12      # saniye, uzun komutlar için üst sınır
SILENCE_DURATION = 1.0        # saniye, bu kadar sessizlikten sonra kayıt biter
SILENCE_THRESHOLD = 0.012     # RMS eşik; ortam gürültülüyse 0.018-0.025 deneyin
PRE_ROLL_DURATION = 0.3       # konuşma başındaki heceleri kaçırmamak için
AUDIO_NORMALIZE_TARGET = 0.90 # WAV yazmadan önce tepe seviyesini normalize eder

# ────────────────────────────────────────
# 🔊 Whisper STT Ayarları
# ────────────────────────────────────────
WHISPER_MODEL_SIZE = "base"  # tiny, base, small, medium, large
WHISPER_LANGUAGE = "tr"      # Türkçe
WHISPER_DEVICE = "cpu"       # cpu veya cuda
WHISPER_COMPUTE_TYPE = "int8"
WHISPER_BEAM_SIZE = 5
WHISPER_VAD_FILTER = True
WHISPER_NO_SPEECH_THRESHOLD = 0.45
WHISPER_CONDITION_ON_PREVIOUS_TEXT = False
WHISPER_INITIAL_PROMPT = (
    "Bu sesli komut Türkçe bir macOS asistanına söyleniyor. "
    "Uygulama adları, müzik, saat, alarm, takvim, not ve web arama komutları geçebilir."
)

# ────────────────────────────────────────
# 🗣️ TTS (Text-to-Speech) Ayarları
# ────────────────────────────────────────
TTS_ENGINE = "macos_say"     # "macos_say" veya "gtts"
TTS_VOICE = "Yelda"          # macOS Türkçe ses (say -v '?' ile kontrol edin)
TTS_RATE = 180               # Konuşma hızı (kelime/dakika)

# ────────────────────────────────────────
# 🎯 Wake Word Ayarları (openWakeWord)
# ────────────────────────────────────────
# openWakeWord: Açık kaynak, API key gerektirmez!
# Hazır modeller: "hey_jarvis", "alexa", "hey_mycroft" vb.
WAKE_WORD_ENABLED = True           # False yaparsanız push-to-talk kullanılır
WAKE_WORD_MODEL = "hey_jarvis"     # openWakeWord hazır model adı
WAKE_WORD_THRESHOLD = 0.5          # Algılama eşiği (0.0-1.0, düşük=hassas, yüksek=katı)
WAKE_WORD_CHUNK_SIZE = 1280        # 80ms @ 16kHz = 1280 örnek

# ────────────────────────────────────────
# 🔧 Genel Ayarlar
# ────────────────────────────────────────
DEBUG = True                 # Detaylı log çıktısı
CONVERSATION_MEMORY = 5     # Hatırlanan son mesaj sayısı

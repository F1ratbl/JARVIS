"""
🧠 JARVIS — LazyLoader (C++ Entegrasyonlu Modül Yükleyici)

Tüm AI modüllerini (Whisper, LLM, TTS, WakeWord) tembel yükleme
(lazy loading) ile yönetir. Yüklenmeden önce RAM kontrolü yapar,
yeterli bellek yoksa Türkçe uyarı verir.

C++ memory_manager modülü derlenmediyse otomatik olarak
Python fallback'e geçer — hiçbir fonksiyonellik kaybedilmez.

Kullanım:
    from core.loader import LazyLoader

    loader = LazyLoader()
    loader.load("whisper")      # RAM kontrol → yükle → cache'e kaydet
    loader.unload("whisper")    # Bellekten boşalt
    loader.status()             # Durum raporu

Mimari Kural:
    - Tüm modüller LazyLoader üzerinden yüklenir
    - C++ derlenmemişse Python fallback devreye girer
    - Her modül bağımsız test edilebilir
    - Türkçe log ve kullanıcı mesajları
"""

import sys
import os
import importlib
from typing import Optional, Callable

# ────────────────────────────────────────
# 🔌 C++ Memory Manager Entegrasyonu
# ────────────────────────────────────────

try:
    from memory_manager import MemoryManager, ModelProfiler, CacheController
    from memory_manager import __backend__ as _mm_backend
    _HAS_CPP = (_mm_backend == "cpp")
except ImportError:
    _HAS_CPP = False
    # Minimal fallback — sadece LazyLoader çalışsın
    MemoryManager = None
    ModelProfiler = None
    CacheController = None

# ────────────────────────────────────────
# 📋 Modül Kayıt Defteri
# ────────────────────────────────────────

# Her modülün: import yolu, tahmini RAM (MB), açıklaması
MODULE_REGISTRY = {
    "whisper": {
        "import_path": "faster_whisper",
        "estimated_mb": 500,      # base model
        "description": "Konuşma → Metin (STT)",
        "loader_func": "_load_whisper",
    },
    "llm": {
        "import_path": "ollama",
        "estimated_mb": 0,        # Ollama kendi belleğini/swap alanını yönettiği için loader engelini kaldırıyoruz
        "description": "Büyük Dil Modeli",
        "loader_func": "_load_llm",
    },
    "tts": {
        "import_path": None,      # macOS say — harici bağımlılık yok
        "estimated_mb": 50,
        "description": "Metin → Ses (TTS)",
        "loader_func": "_load_tts",
    },
    "wake_word": {
        "import_path": "openwakeword",
        "estimated_mb": 100,
        "description": "Uyanma Kelimesi Algılama",
        "loader_func": "_load_wake_word",
    },
    "recorder": {
        "import_path": "sounddevice",
        "estimated_mb": 20,
        "description": "Mikrofon Ses Kaydı",
        "loader_func": "_load_recorder",
    },
    "web_search": {
        "import_path": "ddgs",
        "estimated_mb": 30,
        "description": "Web Arama (DuckDuckGo)",
        "loader_func": "_load_web_search",
    },
}


# ════════════════════════════════════════
# 🚀 LazyLoader — Ana Sınıf
# ════════════════════════════════════════

class LazyLoader:
    """
    C++ entegrasyonlu tembel modül yükleyici.

    - Yüklemeden önce RAM kontrolü yapar (can_load)
    - Yetersiz RAM'de Türkçe uyarı verir
    - LRU mantığıyla modül takibi yapar (CacheController)
    - C++ yoksa pure Python fallback çalışır
    """

    def __init__(self, debug: bool = True):
        self._debug = debug
        self._loaded_modules: dict[str, object] = {}
        self._last_errors: dict[str, str] = {}

        # C++ bileşenlerini başlat
        self._profiler: Optional[ModelProfiler] = None
        self._cache: Optional[CacheController] = None

        if ModelProfiler is not None:
            self._profiler = ModelProfiler()
            # Modül kayıt defterindeki modelleri profiler'a kaydet
            for name, info in MODULE_REGISTRY.items():
                self._profiler.register_model(name, info["estimated_mb"])

        if CacheController is not None:
            self._cache = CacheController()

        if self._debug:
            backend = "C++" if _HAS_CPP else "Python fallback"
            self._log(f"LazyLoader başlatıldı (backend: {backend})")
            if MemoryManager is not None:
                self._log(MemoryManager.summary())

    # ────────────────────────────────────
    # 📋 Modül Yükleme / Boşaltma
    # ────────────────────────────────────

    def load(self, module_name: str) -> Optional[object]:
        """
        Modülü yükler. Yüklemeden önce RAM kontrolü yapar.

        Args:
            module_name: Modül adı (ör: "whisper", "llm", "tts")

        Returns:
            Yüklenen modül objesi veya None (hata/yetersiz RAM)
        """
        # Zaten yüklüyse tekrar yükleme
        if module_name in self._loaded_modules:
            self._log(f"'{module_name}' zaten yüklü, önbellekten döndürülüyor.")
            if self._cache:
                self._cache.touch(module_name)
            return self._loaded_modules[module_name]

        # Kayıt defterinde var mı?
        if module_name not in MODULE_REGISTRY:
            self._last_errors[module_name] = f"'{module_name}' kayıt defterinde bulunamadı."
            self._warn(f"'{module_name}' kayıt defterinde bulunamadı.")
            return None

        info = MODULE_REGISTRY[module_name]

        # ── RAM Kontrolü ──
        if not self._check_ram(module_name, info["estimated_mb"]):
            return None

        # ── Modülü Yükle ──
        self._log(f"'{module_name}' yükleniyor... ({info['description']})")

        try:
            loader_name = info.get("loader_func")
            if loader_name and hasattr(self, loader_name):
                module_obj = getattr(self, loader_name)()
            else:
                module_obj = self._generic_load(info["import_path"])

            if module_obj is not None:
                self._last_errors.pop(module_name, None)
                self._loaded_modules[module_name] = module_obj

                # Cache'e kaydet
                if self._cache:
                    self._cache.mark_loaded(module_name, info["estimated_mb"])

                self._log(f"✅ '{module_name}' başarıyla yüklendi.")
                return module_obj
            else:
                self._last_errors.setdefault(module_name, f"'{module_name}' yüklenemedi.")
                self._warn(f"'{module_name}' yüklenemedi.")
                return None

        except Exception as e:
            self._last_errors[module_name] = f"'{module_name}' yüklenirken hata: {e}"
            self._warn(f"'{module_name}' yüklenirken hata: {e}")
            return None

    def unload(self, module_name: str) -> bool:
        """
        Modülü bellekten boşaltır.

        Args:
            module_name: Boşaltılacak modül adı

        Returns:
            True: başarıyla boşaltıldı, False: zaten yüklü değildi
        """
        if module_name not in self._loaded_modules:
            self._log(f"'{module_name}' zaten yüklü değil.")
            return False

        del self._loaded_modules[module_name]

        freed_mb = 0
        if self._cache:
            freed_mb = self._cache.mark_unloaded(module_name)

        self._log(f"🗑️  '{module_name}' boşaltıldı (~{freed_mb} MB serbest).")
        return True

    def get(self, module_name: str) -> Optional[object]:
        """Yüklü modülü döndürür, yüklü değilse otomatik yükler."""
        if module_name in self._loaded_modules:
            if self._cache:
                self._cache.touch(module_name)
            return self._loaded_modules[module_name]
        return self.load(module_name)

    def is_loaded(self, module_name: str) -> bool:
        """Modülün yüklü olup olmadığını döndürür."""
        return module_name in self._loaded_modules

    def get_last_error(self, module_name: str) -> str:
        """Son yükleme hatasını kullanıcıya gösterilebilir biçimde döndürür."""
        return self._last_errors.get(module_name, "")

    # ────────────────────────────────────
    # 🧠 RAM Kontrolü
    # ────────────────────────────────────

    def _check_ram(self, module_name: str, estimated_mb: int) -> bool:
        """
        Modül yüklemeden önce RAM kontrolü yapar.
        Yetersizse Türkçe uyarı verir.

        Returns:
            True: yeterli RAM var, False: yetersiz
        """
        # Profiler varsa (C++ veya fallback), can_load kontrol et
        if self._profiler:
            try:
                if not self._profiler.can_load(module_name):
                    avail = MemoryManager.get_available_ram() if MemoryManager else "?"
                    self._last_errors[module_name] = (
                        f"Yetersiz bellek: gerekli ~{estimated_mb} MB, mevcut {avail} MB."
                    )
                    self._warn(
                        f"⚠️  YETERSIZ BELLEK — '{module_name}' yüklenemiyor!\n"
                        f"   Gerekli : ~{estimated_mb} MB\n"
                        f"   Mevcut  : {avail} MB\n"
                        f"   Öneri   : Başka bir modülü boşaltın veya "
                        f"daha küçük model seçin."
                    )

                    # Boşaltma önerisi
                    if self._cache:
                        candidates = self._cache.get_unload_candidates()
                        if candidates:
                            self._warn(
                                f"   💡 Boşaltılabilecek modüller: "
                                f"{', '.join(candidates)}"
                            )
                    return False
            except RuntimeError:
                # Model kayıtlı değilse, basit kontrol yap
                pass

        # Profiler yoksa veya model kayıtlı değilse, basit kontrol
        if MemoryManager is not None:
            avail = MemoryManager.get_available_ram()
            safe_required = int(estimated_mb * 1.20)
            if avail < safe_required:
                self._last_errors[module_name] = (
                    f"Yetersiz bellek: gerekli ~{estimated_mb} MB, mevcut {avail} MB."
                )
                self._warn(
                    f"⚠️  YETERSIZ BELLEK — '{module_name}' yüklenemiyor!\n"
                    f"   Gerekli : ~{estimated_mb} MB (+%20 güvenlik)\n"
                    f"   Mevcut  : {avail} MB"
                )
                return False

        return True

    # ────────────────────────────────────
    # 🔧 Modül Yükleyiciler
    # ────────────────────────────────────

    def _generic_load(self, import_path: str) -> Optional[object]:
        """Genel amaçlı import fonksiyonu."""
        if not import_path:
            return True  # Import gerekmiyorsa (ör: macOS say)
        try:
            return importlib.import_module(import_path)
        except ImportError as e:
            self._warn(f"'{import_path}' import edilemedi: {e}")
            self._warn(f"💡  pip install {import_path.replace('_', '-')}")
            return None

    def _load_whisper(self) -> Optional[object]:
        """Whisper STT modelini yükler."""
        try:
            from faster_whisper import WhisperModel
            # Config'den model boyutunu al
            try:
                from assistant.config import (
                    WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE
                )
            except ImportError:
                WHISPER_MODEL_SIZE = "base"
                WHISPER_DEVICE = "cpu"
                WHISPER_COMPUTE_TYPE = "int8"

            # RAM'e göre model önerisi
            if self._profiler:
                recommended = self._profiler.recommend_whisper_model()
                if recommended != WHISPER_MODEL_SIZE:
                    self._log(
                        f"💡 RAM'e göre önerilen Whisper modeli: '{recommended}' "
                        f"(config'te: '{WHISPER_MODEL_SIZE}')"
                    )

            model = WhisperModel(
                WHISPER_MODEL_SIZE,
                device=WHISPER_DEVICE,
                compute_type=WHISPER_COMPUTE_TYPE
            )
            return model
        except Exception as e:
            self._warn(f"Whisper yüklenemedi: {e}")
            return None

    def _load_llm(self) -> Optional[object]:
        """Ollama LLM bağlantısını kontrol eder."""
        try:
            import ollama
            # Bağlantı testi
            try:
                ollama.list()
            except Exception:
                # Kapalıysa otomatik başlat
                import subprocess
                import time
                self._log("Ollama kapalı, arka planda otomatik başlatılıyor...")
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                time.sleep(3)
                ollama.list()

            # RAM'e göre model önerisi
            if self._profiler:
                recommended = self._profiler.recommend_llm_model()
                self._log(f"💡 RAM'e göre önerilen LLM modeli: '{recommended}'")

            self._last_errors.pop("llm", None)
            return ollama
        except Exception as e:
            self._last_errors["llm"] = f"Ollama bağlantısı kurulamadı: {e}"
            self._warn(f"Ollama otomatik başlatılamadı veya bağlanılamadı: {e}")
            return None

    def _load_tts(self) -> Optional[object]:
        """TTS motorunu yükler (macOS say veya gTTS)."""
        try:
            from assistant.config import TTS_ENGINE
        except ImportError:
            TTS_ENGINE = "macos_say"

        if TTS_ENGINE == "macos_say":
            import subprocess
            result = subprocess.run(
                ["which", "say"], capture_output=True, text=True
            )
            if result.returncode == 0:
                return True  # macOS say mevcut
            self._warn("macOS 'say' komutu bulunamadı.")
            return None
        else:
            return self._generic_load("gtts")

    def _load_wake_word(self) -> Optional[object]:
        """openWakeWord modelini yükler."""
        try:
            import openwakeword
            from openwakeword.model import Model
            openwakeword.utils.download_models()
            model = Model(inference_framework="onnx")
            return model
        except Exception as e:
            self._warn(f"openWakeWord yüklenemedi: {e}")
            return None

    def _load_recorder(self) -> Optional[object]:
        """sounddevice ses kaydediciyi yükler."""
        return self._generic_load("sounddevice")

    def _load_web_search(self) -> Optional[object]:
        """DuckDuckGo arama modülünü yükler."""
        return self._generic_load("ddgs")

    # ────────────────────────────────────
    # 📊 Durum & Bilgi
    # ────────────────────────────────────

    def status(self) -> str:
        """Detaylı durum raporu döndürür."""
        lines = []
        lines.append("╔══════════════════════════════════════╗")
        lines.append("║   🧠 LazyLoader Durum Raporu         ║")
        lines.append("╚══════════════════════════════════════╝")

        # Backend
        backend = "C++" if _HAS_CPP else "Python fallback"
        lines.append(f"  Backend: {backend}")

        # RAM durumu
        if MemoryManager is not None:
            lines.append(f"  {MemoryManager.summary()}")
            lines.append(f"  Process RAM: {MemoryManager.get_process_usage()} MB")

        # Model önerileri
        if self._profiler:
            lines.append(
                f"  Önerilen Whisper: {self._profiler.recommend_whisper_model()}"
            )
            lines.append(
                f"  Önerilen LLM: {self._profiler.recommend_llm_model()}"
            )

        # Yüklü modüller
        lines.append(f"\n  Yüklü modüller ({len(self._loaded_modules)}):")
        if self._loaded_modules:
            for name in self._loaded_modules:
                mb = MODULE_REGISTRY.get(name, {}).get("estimated_mb", "?")
                desc = MODULE_REGISTRY.get(name, {}).get("description", "")
                lines.append(f"    ✅ {name} — ~{mb} MB ({desc})")
        else:
            lines.append("    (hiçbir modül yüklü değil)")

        # Yüklenmemiş modüller
        unloaded = [n for n in MODULE_REGISTRY if n not in self._loaded_modules]
        if unloaded:
            lines.append(f"\n  Yüklenmemiş modüller ({len(unloaded)}):")
            for name in unloaded:
                mb = MODULE_REGISTRY[name]["estimated_mb"]
                desc = MODULE_REGISTRY[name]["description"]
                lines.append(f"    ⬚ {name} — ~{mb} MB ({desc})")

        # Cache durumu
        if self._cache:
            lines.append(f"\n  {self._cache.status()}")

        return "\n".join(lines)

    def get_recommendations(self) -> dict:
        """RAM'e göre model önerilerini döndürür."""
        
        # Default fallbacks
        total = 8192
        avail = 4096
        whisper_model = "base"
        llm_model = "mistral:7b-q4"
        pressure = "unknown"
        
        try:
            if MemoryManager is not None:
                total = MemoryManager.get_total_ram()
                avail = MemoryManager.get_available_ram()
                pressure = MemoryManager.get_ram_pressure()
                
            if self._profiler:
                whisper_model = self._profiler.recommend_whisper_model()
                llm_model = self._profiler.recommend_llm_model()
        except Exception:
            pass
            
        # --- FIX OLLAMA MODELS (C++ BACKEND OVERRIDE) ---
        if llm_model == "mistral:7b-q2":
            llm_model = "llama3.2" # Daha uyumlu ve verimli 3B model
        elif llm_model == "mistral:7b-q4":
            llm_model = "qwen2.5:7b" # 8 GB RAM'de Türkçe komut/JSON/tool takibi için daha dengeli model
            
        return {
            "total_ram_mb": total,
            "available_ram_mb": avail,
            "pressure": pressure,
            "whisper_model": whisper_model,
            "llm_model": llm_model
        }

    def get_llm_model(self) -> str:
        """Return configured LLM model, or the RAM-based recommendation."""
        try:
            from assistant.config import OLLAMA_MODEL
        except ImportError:
            OLLAMA_MODEL = "auto"

        if OLLAMA_MODEL and str(OLLAMA_MODEL).lower() != "auto":
            return str(OLLAMA_MODEL)
        return self.get_recommendations()["llm_model"]

    # ────────────────────────────────────
    # 🛠️ Yardımcılar
    # ────────────────────────────────────

    def _log(self, msg: str):
        """Debug log mesajı yazdırır."""
        if self._debug:
            print(f"  [LazyLoader] {msg}")

    def _warn(self, msg: str):
        """Uyarı mesajı yazdırır (her zaman)."""
        print(f"  [LazyLoader] ⚠️  {msg}")


# ────────────────────────────────────────
# 🧪 TEST & GLOBAL INSTANCE
# ────────────────────────────────────────

# Proje genelinde kullanılacak tek (singleton) yükleyici
global_loader = LazyLoader(debug=True)

if __name__ == "__main__":
    print("🧠 LazyLoader test ediliyor...\n")

    loader = LazyLoader(debug=True)
    print()

    # Durum raporu
    print(loader.status())
    print()

    # Öneriler
    recs = loader.get_recommendations()
    print(f"Model önerileri: {recs}")

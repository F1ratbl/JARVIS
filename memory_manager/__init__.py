"""
🧠 JARVIS — Bellek Yönetim Modülü (Python Arayüzü)

C++ ile yazılmış memory_manager modülünün Python'dan import edilmesini sağlar.
C++ derlenmediyse, saf Python fallback devreye girer.

Kullanım:
    from memory_manager import MemoryManager, ModelProfiler, CacheController

Sınıflar:
    MemoryManager    → Toplam / kullanılabilir RAM ölçümü
    ModelProfiler    → Modelin RAM'e sığıp sığmadığını kontrol
    CacheController  → LRU mantığıyla düşük öncelikli modülü boşalt
"""

try:
    # C++ derlenmiş modülü yükle
    from ._memory_manager import (
        MemoryManager,
        ModelProfiler,
        CacheController,
        get_total_memory_mb,
        get_available_memory_mb,
    )
    _BACKEND = "cpp"

except ImportError:
    # ── Python Fallback ──
    # C++ modülü derlenmemişse saf Python implementasyonu kullan.
    import warnings
    warnings.warn(
        "⚠️  C++ memory_manager derlenemedi, Python fallback kullanılıyor. "
        "Performans için: cd memory_manager && ./build.sh",
        RuntimeWarning,
        stacklevel=2,
    )

    import platform
    import subprocess
    import os
    import resource
    from collections import OrderedDict

    _BACKEND = "python"

    class MemoryManager:
        """Sistem RAM bilgilerini ölçen sınıf (Python fallback)."""

        @staticmethod
        def get_total_memory() -> int:
            """Toplam fiziksel RAM miktarını byte cinsinden döndürür."""
            system = platform.system()
            if system == "Darwin":
                result = subprocess.run(
                    ["sysctl", "-n", "hw.memsize"],
                    capture_output=True, text=True
                )
                return int(result.stdout.strip())
            elif system == "Linux":
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            kb = int(line.split()[1])
                            return kb * 1024
            raise RuntimeError("Desteklenmeyen platform")

        @staticmethod
        def get_available_memory() -> int:
            """Kullanılabilir RAM miktarını byte cinsinden döndürür."""
            system = platform.system()
            if system == "Darwin":
                result = subprocess.run(
                    ["vm_stat"], capture_output=True, text=True
                )
                lines = result.stdout.split("\n")
                page_size = 16384  # Apple Silicon varsayılan
                # İlk satırdan page size'ı bulmaya çalış
                for line in lines:
                    if "page size of" in line:
                        parts = line.split()
                        for p in parts:
                            if p.isdigit():
                                page_size = int(p)
                                break
                        break

                free_pages = 0
                inactive_pages = 0
                for line in lines:
                    if "Pages free:" in line:
                        free_pages = int(line.split(":")[1].strip().rstrip("."))
                    elif "Pages inactive:" in line:
                        inactive_pages = int(line.split(":")[1].strip().rstrip("."))

                return (free_pages + inactive_pages) * page_size
            elif system == "Linux":
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemAvailable:"):
                            kb = int(line.split()[1])
                            return kb * 1024
            raise RuntimeError("Desteklenmeyen platform")

        @staticmethod
        def get_usage_ratio() -> float:
            """RAM kullanım yüzdesini döndürür (0.0 – 1.0)."""
            total = MemoryManager.get_total_memory()
            avail = MemoryManager.get_available_memory()
            if total == 0:
                return 0.0
            return 1.0 - (avail / total)

        @staticmethod
        def get_total_ram() -> int:
            """Toplam RAM'i MB cinsinden döndürür."""
            return MemoryManager.get_total_memory() // (1024 * 1024)

        @staticmethod
        def get_available_ram() -> int:
            """Kullanılabilir RAM'i MB cinsinden döndürür."""
            return MemoryManager.get_available_memory() // (1024 * 1024)

        @staticmethod
        def get_process_usage() -> int:
            """Bu process'in kullandığı RAM'i MB cinsinden döndürür."""
            system = platform.system()
            if system == "Darwin":
                # macOS: resource modülü byte döndürür
                usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                return usage // (1024 * 1024)
            elif system == "Linux":
                # Linux: resource modülü KB döndürür
                usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                return usage // 1024
            raise RuntimeError("Desteklenmeyen platform")

        @staticmethod
        def get_ram_pressure() -> str:
            """RAM baskı seviyesini döndürür: low / medium / high."""
            ratio = MemoryManager.get_usage_ratio()
            if ratio < 0.60:
                return "low"
            if ratio < 0.85:
                return "medium"
            return "high"

        @staticmethod
        def summary() -> str:
            """RAM durumunun okunabilir özetini döndürür."""
            total = MemoryManager.get_total_memory()
            avail = MemoryManager.get_available_memory()
            used = total - avail
            ratio = MemoryManager.get_usage_ratio()
            return (
                f"RAM Durumu: {used // (1024*1024)} MB kullanılıyor / "
                f"{total // (1024*1024)} MB toplam  "
                f"({int(ratio * 100)}% dolu)  —  "
                f"{avail // (1024*1024)} MB kullanılabilir"
                f"  —  Baskı: {MemoryManager.get_ram_pressure()}"
            )

    class ModelProfiler:
        """AI modellerinin RAM profilini yöneten sınıf (Python fallback)."""

        _DEFAULT_MODELS = {
            "whisper-tiny": 390,
            "whisper-base": 500,
            "whisper-small": 970,
            "whisper-medium": 2950,
            "whisper-large": 6170,
            "mistral:7b-q4": 4500,
            "mistral:7b-q2": 2800,
            "mistral-7b": 5500,
            "llama3-8b": 6500,
            "llama3-3b": 2800,
            "coqui-tts": 1200,
            "openwakeword": 100,
        }

        def __init__(self):
            self._models = dict(self._DEFAULT_MODELS)

        def register_model(self, name: str, estimated_mb: int):
            self._models[name] = estimated_mb

        def can_load(self, model_name: str) -> bool:
            if model_name not in self._models:
                raise RuntimeError(
                    f"Model kayıtlı değil: '{model_name}'. "
                    "Önce register_model() ile kaydedin."
                )
            required_bytes = self._models[model_name] * 1024 * 1024
            available = MemoryManager.get_available_memory()
            safe_required = int(required_bytes * 1.20)
            return available >= safe_required

        @staticmethod
        def recommend_whisper_model() -> str:
            total_mb = MemoryManager.get_total_ram()
            if total_mb <= 8192:
                return "tiny"
            if total_mb <= 16384:
                return "base"
            return "small"

        @staticmethod
        def recommend_llm_model() -> str:
            total_mb = MemoryManager.get_total_ram()
            if total_mb <= 8192:
                return "llama3.2" # 3B model (low RAM)
            return "llama3" # 8B model (high RAM)

        def get_model_mb(self, model_name: str) -> int:
            return self._models.get(model_name, 0)

        def list_models(self) -> list:
            return list(self._models.keys())

        def profile_report(self, model_name: str) -> str:
            mb = self._models.get(model_name, 0)
            avail_mb = MemoryManager.get_available_ram()
            fits = False
            if mb > 0:
                fits = avail_mb >= int(mb * 1.20)

            lines = [f"Model Profili: {model_name}"]
            if mb > 0:
                lines.append(f"  Gerekli RAM : {mb} MB")
            else:
                lines.append("  Gerekli RAM : Bilinmiyor")
            lines.append(f"  Mevcut RAM  : {avail_mb} MB")
            status = "✅ Yüklenebilir" if fits else "❌ Yetersiz bellek" if mb > 0 else "⚠️ Kayıtlı değil"
            lines.append(f"  Durum       : {status}")
            return "\n".join(lines)

    class CacheController:
        """LRU mantığıyla modülleri yöneten önbellek denetleyicisi (Python fallback)."""

        def __init__(self):
            self._cache: OrderedDict[str, int] = OrderedDict()
            self._unload_count = 0
            self._watching = False
            self._watch_thread = None

        def mark_loaded(self, module_name: str, size_mb: int):
            if module_name in self._cache:
                self._cache.move_to_end(module_name, last=False)
                self._cache[module_name] = size_mb
            else:
                self._cache[module_name] = size_mb
                self._cache.move_to_end(module_name, last=False)

        def mark_unloaded(self, module_name: str) -> int:
            if module_name not in self._cache:
                return 0
            freed = self._cache.pop(module_name)
            self._unload_count += 1
            return freed

        def touch(self, module_name: str):
            if module_name in self._cache:
                self._cache.move_to_end(module_name, last=False)

        def get_unload_candidates(self) -> list:
            pressure = MemoryManager.get_ram_pressure()
            if pressure != "high":
                return []
            return list(reversed(self._cache.keys()))

        def watch(self, interval_seconds: int, callback):
            import threading
            self.stop_watch()
            self._watching = True

            def _loop():
                import time
                while self._watching:
                    candidates = self.get_unload_candidates()
                    if candidates and callback:
                        try:
                            callback(candidates)
                        except Exception as e:
                            print(f"[CacheController] ⚠️  Callback hatası: {e}")
                    time.sleep(interval_seconds)

            self._watch_thread = threading.Thread(target=_loop, daemon=True)
            self._watch_thread.start()

        def stop_watch(self):
            self._watching = False
            if self._watch_thread and self._watch_thread.is_alive():
                self._watch_thread.join(timeout=2)
            self._watch_thread = None

        def is_watching(self) -> bool:
            return self._watching

        def size(self) -> int:
            return len(self._cache)

        def get_unload_count(self) -> int:
            return self._unload_count

        def get_loaded_modules(self) -> list:
            return list(self._cache.keys())

        def get_module_size(self, module_name: str) -> int:
            return self._cache.get(module_name, 0)

        def status(self) -> str:
            pressure = MemoryManager.get_ram_pressure()
            lines = [f"Önbellek Durumu ({len(self._cache)} modül yüklü, baskı: {pressure}):"]
            total_mb = 0
            for name, mb in self._cache.items():
                lines.append(f"  • {name} — ~{mb} MB")
                total_mb += mb
            lines.append(f"  Toplam tahmini kullanım: ~{total_mb} MB")
            lines.append(f"  Toplam boşaltma sayısı: {self._unload_count}")
            lines.append(f"  İzleme aktif: {'evet' if self._watching else 'hayır'}")
            return "\n".join(lines)

    def get_total_memory_mb() -> int:
        return MemoryManager.get_total_memory() // (1024 * 1024)

    def get_available_memory_mb() -> int:
        return MemoryManager.get_available_memory() // (1024 * 1024)


# ── Modül bilgisi ──
__version__ = "0.1.0"
__backend__ = _BACKEND

__all__ = [
    "MemoryManager",
    "ModelProfiler",
    "CacheController",
    "get_total_memory_mb",
    "get_available_memory_mb",
]

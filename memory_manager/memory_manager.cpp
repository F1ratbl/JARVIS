/**
 * 🧠 JARVIS — C++ Bellek Yönetim Modülü
 *
 * Görevler:
 *   - MemoryManager   : Toplam / kullanılabilir RAM ölçümü
 *   - ModelProfiler   : Modelin RAM'e sığıp sığmadığını kontrol
 *   - CacheController : LRU mantığıyla düşük öncelikli modülü boşalt
 *
 * Platform desteği:
 *   - Linux  → /proc/meminfo
 *   - macOS  → sysctl (Apple Silicon dahil)
 *
 * Thread-safe: mutex + arka plan izleme thread'i
 * Köprü: pybind11 ile Python'a açılır
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <fstream>
#include <functional>
#include <iostream>
#include <list>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

// ── Platform-spesifik başlıklar ──
#ifdef __APPLE__
#include <mach/mach.h>
#include <mach/mach_host.h>
#include <mach/task.h>
#include <mach/task_info.h>
#include <sys/sysctl.h>
#elif __linux__
#include <fstream>
#include <unistd.h>
#else
#error "Desteklenmeyen platform. Sadece Linux ve macOS desteklenir."
#endif

namespace py = pybind11;

// ════════════════════════════════════════
// 📊 MemoryManager — RAM Ölçümü
// ════════════════════════════════════════

class MemoryManager {
public:
  /**
   * Toplam fiziksel RAM miktarını byte cinsinden döndürür.
   */
  static size_t get_total_memory() {
#ifdef __APPLE__
    int mib[2] = {CTL_HW, HW_MEMSIZE};
    int64_t mem = 0;
    size_t len = sizeof(mem);
    if (sysctl(mib, 2, &mem, &len, nullptr, 0) != 0) {
      throw std::runtime_error("sysctl ile toplam bellek okunamadı");
    }
    return static_cast<size_t>(mem);
#elif __linux__
    std::ifstream meminfo("/proc/meminfo");
    if (!meminfo.is_open()) {
      throw std::runtime_error("/proc/meminfo açılamadı");
    }
    std::string line;
    while (std::getline(meminfo, line)) {
      if (line.find("MemTotal:") == 0) {
        size_t kb = 0;
        std::sscanf(line.c_str(), "MemTotal: %zu kB", &kb);
        return kb * 1024;
      }
    }
    throw std::runtime_error("MemTotal /proc/meminfo içinde bulunamadı");
#endif
  }

  /**
   * Kullanılabilir (serbest) RAM miktarını byte cinsinden döndürür.
   */
  static size_t get_available_memory() {
#ifdef __APPLE__
    mach_port_t host = mach_host_self();
    vm_statistics64_data_t vm_stat;
    mach_msg_type_number_t count = HOST_VM_INFO64_COUNT;
    kern_return_t kr =
        host_statistics64(host, HOST_VM_INFO64,
                          reinterpret_cast<host_info64_t>(&vm_stat), &count);
    if (kr != KERN_SUCCESS) {
      throw std::runtime_error("mach host_statistics64 başarısız");
    }
    // Kullanılabilir = free + inactive (macOS raporlaması)
    size_t page_size = vm_kernel_page_size;
    size_t available =
        (vm_stat.free_count + vm_stat.inactive_count) * page_size;
    return available;
#elif __linux__
    std::ifstream meminfo("/proc/meminfo");
    if (!meminfo.is_open()) {
      throw std::runtime_error("/proc/meminfo açılamadı");
    }
    std::string line;
    while (std::getline(meminfo, line)) {
      if (line.find("MemAvailable:") == 0) {
        size_t kb = 0;
        std::sscanf(line.c_str(), "MemAvailable: %zu kB", &kb);
        return kb * 1024;
      }
    }
    throw std::runtime_error("MemAvailable /proc/meminfo içinde bulunamadı");
#endif
  }

  /**
   * RAM kullanım yüzdesini döndürür (0.0 – 1.0).
   */
  static double get_usage_ratio() {
    size_t total = get_total_memory();
    size_t available = get_available_memory();
    if (total == 0)
      return 0.0;
    return 1.0 - (static_cast<double>(available) / static_cast<double>(total));
  }

  // ── AŞAMA 1 API ──

  /**
   * Toplam fiziksel RAM miktarını MB cinsinden döndürür.
   */
  static size_t get_total_ram() { return get_total_memory() / (1024 * 1024); }

  /**
   * Kullanılabilir RAM miktarını MB cinsinden döndürür.
   */
  static size_t get_available_ram() {
    return get_available_memory() / (1024 * 1024);
  }

  /**
   * Bu process'in kullandığı RAM'i MB cinsinden döndürür (RSS).
   */
  static size_t get_process_usage() {
#ifdef __APPLE__
    mach_task_basic_info_data_t info;
    mach_msg_type_number_t count = MACH_TASK_BASIC_INFO_COUNT;
    kern_return_t kr = task_info(mach_task_self(), MACH_TASK_BASIC_INFO,
                                 reinterpret_cast<task_info_t>(&info), &count);
    if (kr != KERN_SUCCESS) {
      throw std::runtime_error("task_info ile process belleği okunamadı");
    }
    return info.resident_size / (1024 * 1024);
#elif __linux__
    std::ifstream status("/proc/self/status");
    if (!status.is_open()) {
      throw std::runtime_error("/proc/self/status açılamadı");
    }
    std::string line;
    while (std::getline(status, line)) {
      if (line.find("VmRSS:") == 0) {
        size_t kb = 0;
        std::sscanf(line.c_str(), "VmRSS: %zu kB", &kb);
        return kb / 1024;
      }
    }
    throw std::runtime_error("VmRSS /proc/self/status içinde bulunamadı");
#endif
  }

  /**
   * RAM baskı seviyesini döndürür: "low", "medium" veya "high".
   *   low    → kullanım < %60
   *   medium → kullanım %60-%85
   *   high   → kullanım > %85
   */
  static std::string get_ram_pressure() {
    double ratio = get_usage_ratio();
    if (ratio < 0.60)
      return "low";
    if (ratio < 0.85)
      return "medium";
    return "high";
  }

  /**
   * MB cinsinden toplam / kullanılabilir / kullanılan bilgisini döndürür.
   */
  static std::string summary() {
    size_t total = get_total_memory();
    size_t avail = get_available_memory();
    size_t used = total - avail;
    double ratio = get_usage_ratio();

    std::ostringstream oss;
    oss << "RAM Durumu: " << (used / (1024 * 1024)) << " MB kullanılıyor / "
        << (total / (1024 * 1024)) << " MB toplam  ("
        << static_cast<int>(ratio * 100) << "% dolu)  —  "
        << (avail / (1024 * 1024)) << " MB kullanılabilir"
        << "  —  Baskı: " << get_ram_pressure();
    return oss.str();
  }
};

// ════════════════════════════════════════
// 🔍 ModelProfiler — Model RAM Profili
// ════════════════════════════════════════

class ModelProfiler {
private:
  // Kayıtlı modeller: ad → tahmini MB
  std::unordered_map<std::string, size_t> registered_models_;
  mutable std::mutex mtx_;

  // Varsayılan bilinen modeller (hazır tablo)
  static const std::unordered_map<std::string, size_t> &default_models() {
    static const std::unordered_map<std::string, size_t> defaults = {
        {"whisper-tiny", 390},   {"whisper-base", 500},
        {"whisper-small", 970},  {"whisper-medium", 2950},
        {"whisper-large", 6170}, {"mistral:7b-q4", 4500},
        {"mistral:7b-q2", 2800}, {"mistral-7b", 5500},
        {"llama3-8b", 6500},     {"llama3-3b", 2800},
        {"coqui-tts", 1200},     {"openwakeword", 100},
    };
    return defaults;
  }

public:
  ModelProfiler() {
    // Varsayılan modelleri kayıt defterine kopyala
    registered_models_ = default_models();
  }

  /**
   * Modeli kaydet veya mevcut kaydı güncelle.
   *
   * @param name          Model adı (örn: "whisper-base")
   * @param estimated_mb  Tahmini RAM ihtiyacı (MB)
   */
  void register_model(const std::string &name, size_t estimated_mb) {
    std::lock_guard<std::mutex> lock(mtx_);
    registered_models_[name] = estimated_mb;
  }

  /**
   * Kayıtlı modelin RAM'e sığıp sığmadığını kontrol eder.
   * Model kayıtlı değilse std::runtime_error fırlatır.
   *
   * @param model_name  Kayıtlı model adı
   * @return true = sığar, false = sığmaz
   */
  bool can_load(const std::string &model_name) const {
    std::lock_guard<std::mutex> lock(mtx_);

    auto it = registered_models_.find(model_name);
    if (it == registered_models_.end()) {
      throw std::runtime_error("Model kayıtlı değil: '" + model_name +
                               "'. "
                               "Önce register_model() ile kaydedin.");
    }

    size_t required_bytes = it->second * 1024ULL * 1024ULL;
    size_t available = MemoryManager::get_available_memory();
    // %20 güvenlik marjı
    size_t safe_required = static_cast<size_t>(required_bytes * 1.20);
    return available >= safe_required;
  }

  /**
   * Toplam RAM kapasitesine göre en uygun Whisper modelini önerir.
   *
   * Eşikler (toplam RAM):
   *   ≤ 8 GB  →  "tiny"
   *   8-16 GB →  "base"
   *   > 16 GB →  "small"
   */
  static std::string recommend_whisper_model() {
    size_t total_mb = MemoryManager::get_total_ram();
    if (total_mb <= 8192)
      return "tiny";
    if (total_mb <= 16384)
      return "base";
    return "small";
  }

  /**
   * Toplam RAM kapasitesine göre en uygun LLM modelini önerir.
   *
   * Eşikler (toplam RAM):
   *   ≤ 8 GB  →  "mistral:7b-q2"  (hafif, az RAM)
   *   > 8 GB  →  "mistral:7b-q4"  (dengeli)
   */
  static std::string recommend_llm_model() {
    size_t total_mb = MemoryManager::get_total_ram();
    if (total_mb <= 8192)
      return "mistral:7b-q2";
    return "mistral:7b-q4";
  }

  /**
   * Kayıtlı modelin tahmini MB değerini döndürür.
   * Kayıtlı değilse 0 döner.
   */
  size_t get_model_mb(const std::string &model_name) const {
    std::lock_guard<std::mutex> lock(mtx_);
    auto it = registered_models_.find(model_name);
    return (it != registered_models_.end()) ? it->second : 0;
  }

  /**
   * Kayıtlı tüm model adlarını döndürür.
   */
  std::vector<std::string> list_models() const {
    std::lock_guard<std::mutex> lock(mtx_);
    std::vector<std::string> names;
    names.reserve(registered_models_.size());
    for (const auto &pair : registered_models_) {
      names.push_back(pair.first);
    }
    return names;
  }

  /**
   * Model profil raporu.
   */
  std::string profile_report(const std::string &model_name) const {
    std::lock_guard<std::mutex> lock(mtx_);

    auto it = registered_models_.find(model_name);
    size_t required_mb = (it != registered_models_.end()) ? it->second : 0;
    size_t avail_mb = MemoryManager::get_available_ram();
    bool fits = false;
    if (required_mb > 0) {
      size_t safe = static_cast<size_t>(required_mb * 1.20);
      fits = avail_mb >= safe;
    }

    std::ostringstream oss;
    oss << "Model Profili: " << model_name << "\n";
    if (required_mb > 0) {
      oss << "  Gerekli RAM : " << required_mb << " MB\n";
    } else {
      oss << "  Gerekli RAM : Bilinmiyor\n";
    }
    oss << "  Mevcut RAM  : " << avail_mb << " MB\n";
    oss << "  Durum       : "
        << (required_mb > 0 ? (fits ? "✅ Yüklenebilir" : "❌ Yetersiz bellek")
                            : "⚠️ Kayıtlı değil");
    return oss.str();
  }
};

// ════════════════════════════════════════
// 🗑️ CacheController — LRU Önbellek Yönetimi
// ════════════════════════════════════════

class CacheController {
private:
    // LRU sırası: en son kullanılan başta (front), en az kullanılan sonda (back)
    std::list<std::string> lru_order_;
    // Modül adı → (tahmini MB, listedeki iterator)
    std::unordered_map<std::string,
        std::pair<size_t, std::list<std::string>::iterator>> cache_;
    mutable std::mutex mtx_;

    // Arka plan izleme
    std::thread watch_thread_;
    std::atomic<bool> watching_{false};
    size_t unload_count_ = 0;

    // Python callback (boşaltma önerisi geldiğinde çağrılır)
    py::object py_callback_;
    bool has_callback_ = false;

public:
    CacheController() = default;
    ~CacheController() { stop_watch(); }

    // Kopyalama engelle (thread güvenliği)
    CacheController(const CacheController&) = delete;
    CacheController& operator=(const CacheController&) = delete;

    // ── AŞAMA 3 API ──

    /**
     * Modül yüklendiğinde çağır — LRU listesine ekler.
     *
     * @param module_name  Modül adı (örn: "whisper", "llm")
     * @param size_mb      Modülün tahmini RAM kullanımı (MB)
     */
    void mark_loaded(const std::string& module_name, size_t size_mb) {
        std::lock_guard<std::mutex> lock(mtx_);

        // Zaten varsa LRU sırasını güncelle
        auto it = cache_.find(module_name);
        if (it != cache_.end()) {
            lru_order_.erase(it->second.second);
        }

        lru_order_.push_front(module_name);
        cache_[module_name] = {size_mb, lru_order_.begin()};
    }

    /**
     * Modül boşaltılınca çağır — LRU listesinden siler.
     *
     * @param module_name  Boşaltılan modül adı
     * @return Boşaltılan modülün MB'ı, bulunamazsa 0
     */
    size_t mark_unloaded(const std::string& module_name) {
        std::lock_guard<std::mutex> lock(mtx_);

        auto it = cache_.find(module_name);
        if (it == cache_.end()) return 0;

        size_t freed_mb = it->second.first;
        lru_order_.erase(it->second.second);
        cache_.erase(it);
        unload_count_++;
        return freed_mb;
    }

    /**
     * Modüle erişildiğini bildir → LRU sırasında öne taşı.
     */
    void touch(const std::string& module_name) {
        std::lock_guard<std::mutex> lock(mtx_);

        auto it = cache_.find(module_name);
        if (it == cache_.end()) return;

        lru_order_.erase(it->second.second);
        lru_order_.push_front(module_name);
        it->second.second = lru_order_.begin();
    }

    /**
     * RAM baskısı "high" olunca boşaltılması önerilen modülleri döndürür.
     * LRU mantığı: en az kullanılan modüller listenin başında.
     * Baskı "high" değilse boş liste döner.
     *
     * @return Boşaltma adayı modül adları (LRU sırasıyla, en az kullanılan önce)
     */
    std::vector<std::string> get_unload_candidates() const {
        std::vector<std::string> candidates;

        std::string pressure = MemoryManager::get_ram_pressure();
        if (pressure != "high") return candidates;

        std::lock_guard<std::mutex> lock(mtx_);
        // Sondan (LRU) başa doğru — en az kullanılan önce
        for (auto rit = lru_order_.rbegin(); rit != lru_order_.rend(); ++rit) {
            candidates.push_back(*rit);
        }
        return candidates;
    }

    /**
     * Arka plan thread'inde RAM'i izler.
     * Baskı "high" olunca callback tetiklenir.
     *
     * @param interval_seconds  Kontrol aralığı (saniye)
     * @param callback          Python callback fonksiyonu:
     *                          callback(candidates: list[str])
     */
    void watch(int interval_seconds, py::object callback) {
        // Önce eski izlemeyi durdur
        stop_watch();

        {
            std::lock_guard<std::mutex> lock(mtx_);
            py_callback_ = callback;
            has_callback_ = !callback.is_none();
        }

        watching_.store(true);
        watch_thread_ = std::thread([this, interval_seconds]() {
            while (watching_.load()) {
                auto candidates = get_unload_candidates();

                if (!candidates.empty() && has_callback_) {
                    // Python callback çağırmak için GIL'i al
                    py::gil_scoped_acquire acquire;
                    try {
                        py_callback_(candidates);
                    } catch (const py::error_already_set& e) {
                        std::cerr << "[CacheController] ⚠️  Callback hatası: "
                                  << e.what() << "\n";
                    }
                }

                std::this_thread::sleep_for(
                    std::chrono::seconds(interval_seconds)
                );
            }
        });
    }

    /**
     * watch() ile başlatılan arka plan izlemesini durdurur.
     */
    void stop_watch() {
        watching_.store(false);
        if (watch_thread_.joinable()) {
            watch_thread_.join();
        }
    }

    /**
     * İzleme thread'inin çalışıp çalışmadığını döndürür.
     */
    bool is_watching() const {
        return watching_.load();
    }

    // ── Bilgi metodları ──

    /**
     * Yüklü modül sayısını döndürür.
     */
    size_t size() const {
        std::lock_guard<std::mutex> lock(mtx_);
        return cache_.size();
    }

    /**
     * Toplam boşaltma sayısını döndürür.
     */
    size_t get_unload_count() const { return unload_count_; }

    /**
     * Yüklü modül adlarını LRU sırasıyla döndürür.
     * (En son kullanılan ilk sırada)
     */
    std::vector<std::string> get_loaded_modules() const {
        std::lock_guard<std::mutex> lock(mtx_);
        return std::vector<std::string>(lru_order_.begin(), lru_order_.end());
    }

    /**
     * Belirli bir modülün tahmini MB'ını döndürür. Bulunamazsa 0.
     */
    size_t get_module_size(const std::string& module_name) const {
        std::lock_guard<std::mutex> lock(mtx_);
        auto it = cache_.find(module_name);
        return (it != cache_.end()) ? it->second.first : 0;
    }

    /**
     * Önbellek durum raporu.
     */
    std::string status() const {
        std::lock_guard<std::mutex> lock(mtx_);

        size_t total_mb = 0;
        std::ostringstream oss;
        oss << "Önbellek Durumu (" << cache_.size() << " modül yüklü, "
            << "baskı: " << MemoryManager::get_ram_pressure() << "):\n";

        for (const auto& name : lru_order_) {
            auto it = cache_.find(name);
            if (it != cache_.end()) {
                oss << "  • " << name << " — ~" << it->second.first << " MB\n";
                total_mb += it->second.first;
            }
        }

        oss << "  Toplam tahmini kullanım: ~" << total_mb << " MB\n";
        oss << "  Toplam boşaltma sayısı: " << unload_count_ << "\n";
        oss << "  İzleme aktif: " << (watching_.load() ? "evet" : "hayır");
        return oss.str();
    }
};

// ════════════════════════════════════════
// 🐍 PYBIND11 BAĞLAMALARI
// ════════════════════════════════════════

PYBIND11_MODULE(_memory_manager, m) {
  m.doc() = "JARVIS C++ Bellek Yönetim Modülü — RAM ölçümü, model profilleme "
            "ve LRU önbellek";

  // ── MemoryManager ──
  py::class_<MemoryManager>(m, "MemoryManager",
                            "Sistem RAM bilgilerini ölçen sınıf (Linux: "
                            "/proc/meminfo, macOS: sysctl)")
      .def_static("get_total_memory", &MemoryManager::get_total_memory,
                  "Toplam fiziksel RAM miktarını byte cinsinden döndürür")
      .def_static("get_available_memory", &MemoryManager::get_available_memory,
                  "Kullanılabilir RAM miktarını byte cinsinden döndürür")
      .def_static("get_usage_ratio", &MemoryManager::get_usage_ratio,
                  "RAM kullanım oranını döndürür (0.0 – 1.0)")
      .def_static("get_total_ram", &MemoryManager::get_total_ram,
                  "Toplam RAM'i MB cinsinden döndürür")
      .def_static("get_available_ram", &MemoryManager::get_available_ram,
                  "Kullanılabilir RAM'i MB cinsinden döndürür")
      .def_static("get_process_usage", &MemoryManager::get_process_usage,
                  "Bu process'in kullandığı RAM'i MB cinsinden döndürür")
      .def_static("get_ram_pressure", &MemoryManager::get_ram_pressure,
                  "RAM baskı seviyesini döndürür: low / medium / high")
      .def_static("summary", &MemoryManager::summary,
                  "RAM durumunun okunabilir özetini döndürür");

  // ── ModelProfiler ──
  py::class_<ModelProfiler>(m, "ModelProfiler",
                            "AI modellerinin RAM profilini yöneten sınıf")
      .def(py::init<>(), "Varsayılan model tablosuyla ModelProfiler oluşturur")
      .def("register_model", &ModelProfiler::register_model, py::arg("name"),
           py::arg("estimated_mb"),
           "Modeli kaydet veya güncelle (ad + tahmini MB)")
      .def("can_load", &ModelProfiler::can_load, py::arg("model_name"),
           "Kayıtlı modelin mevcut RAM'e sığıp sığmadığını kontrol eder")
      .def_static(
          "recommend_whisper_model", &ModelProfiler::recommend_whisper_model,
          "RAM'e göre en uygun Whisper modelini önerir (tiny/base/small)")
      .def_static("recommend_llm_model", &ModelProfiler::recommend_llm_model,
                  "RAM'e göre en uygun LLM modelini önerir (mistral:7b-q2/q4)")
      .def("get_model_mb", &ModelProfiler::get_model_mb, py::arg("model_name"),
           "Kayıtlı modelin tahmini MB değerini döndürür")
      .def("list_models", &ModelProfiler::list_models,
           "Kayıtlı tüm model adlarını döndürür")
      .def("profile_report", &ModelProfiler::profile_report,
           py::arg("model_name"), "Model profil raporunu döndürür");

  // ── CacheController ──
  py::class_<CacheController>(
      m, "CacheController",
      "LRU mantığıyla modülleri yöneten önbellek denetleyicisi. "
      "RAM baskısı yükselince otomatik boşaltma önerisi yapar.")
      .def(py::init<>(), "CacheController oluşturur")
      .def("mark_loaded", &CacheController::mark_loaded,
           py::arg("module_name"), py::arg("size_mb"),
           "Modül yüklendiğinde kaydet (ad + tahmini MB)")
      .def("mark_unloaded", &CacheController::mark_unloaded,
           py::arg("module_name"),
           "Modül boşaltılınca sil, boşaltılan MB'ı döndürür")
      .def("touch", &CacheController::touch,
           py::arg("module_name"),
           "Modüle erişildiğini bildirir (LRU sırasını günceller)")
      .def("get_unload_candidates", &CacheController::get_unload_candidates,
           "RAM baskısı 'high' ise boşaltma adaylarını LRU sırasıyla döndürür")
      .def("watch", &CacheController::watch,
           py::arg("interval_seconds"), py::arg("callback"),
           "Arka plan thread'inde RAM izleme başlatır. "
           "Baskı 'high' olunca callback(candidates) çağrılır")
      .def("stop_watch", &CacheController::stop_watch,
           "Arka plan izlemesini durdurur")
      .def("is_watching", &CacheController::is_watching,
           "İzleme thread'inin çalışıp çalışmadığını döndürür")
      .def("size", &CacheController::size, "Yüklü modül sayısını döndürür")
      .def("get_unload_count", &CacheController::get_unload_count,
           "Toplam boşaltma sayısını döndürür")
      .def("get_loaded_modules", &CacheController::get_loaded_modules,
           "Yüklü modülleri LRU sırasıyla döndürür")
      .def("get_module_size", &CacheController::get_module_size,
           py::arg("module_name"),
           "Modülün tahmini MB'ını döndürür")
      .def("status", &CacheController::status,
           "Önbellek durum raporunu döndürür");

  // ── Modül seviyesi yardımcı fonksiyonlar ──
  m.def(
      "get_total_memory_mb", []() { return MemoryManager::get_total_ram(); },
      "Toplam RAM'i MB cinsinden döndürür (kısa yol)");

  m.def(
      "get_available_memory_mb",
      []() { return MemoryManager::get_available_ram(); },
      "Kullanılabilir RAM'i MB cinsinden döndürür (kısa yol)");
}

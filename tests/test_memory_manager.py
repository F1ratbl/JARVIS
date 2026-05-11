import time
import unittest
import sys
import os

# Proje kök dizinini PYTHONPATH'e ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from memory_manager import MemoryManager, ModelProfiler, CacheController
from memory_manager import __backend__ as mm_backend

class TestMemoryManager(unittest.TestCase):
    """JARVIS Memory Manager Stres ve İşlevsellik Testleri"""

    @classmethod
    def setUpClass(cls):
        print("\n" + "="*50)
        print(f"🧠 Bellek Yöneticisi Testleri Başlıyor")
        print(f"⚙️  Kullanılan Backend: {mm_backend.upper()}")
        print("="*50)

    def test_01_ram_values_sanity(self):
        """RAM değerlerinin mantıklı bir aralıkta olduğunu doğrula"""
        total = MemoryManager.get_total_ram()
        available = MemoryManager.get_available_ram()
        process = MemoryManager.get_process_usage()
        
        self.assertGreater(total, 0, "Toplam RAM 0'dan büyük olmalı")
        self.assertGreater(available, 0, "Kullanılabilir RAM 0'dan büyük olmalı")
        self.assertGreaterEqual(total, available, "Toplam RAM, kullanılabilir RAM'den büyük veya eşit olmalı")
        self.assertGreater(process, 0, "Process bellek kullanımı 0'dan büyük olmalı")
        
        # Oran testi
        ratio = MemoryManager.get_usage_ratio()
        self.assertTrue(0.0 <= ratio <= 1.0, f"RAM kullanım oranı (ratio) {ratio} [0.0, 1.0] aralığında olmalı")

        # Baskı testi
        pressure = MemoryManager.get_ram_pressure()
        self.assertIn(pressure, ["low", "medium", "high"], f"Geçersiz RAM baskı seviyesi: {pressure}")

    def test_02_model_profiler_recommendations(self):
        """recommend_whisper_model() ve recommend_llm_model() çıktısını test et"""
        mp = ModelProfiler()
        
        whisper_rec = mp.recommend_whisper_model()
        self.assertIn(whisper_rec, ["tiny", "base", "small"], f"Geçersiz Whisper model önerisi: {whisper_rec}")

        llm_rec = mp.recommend_llm_model()
        self.assertIn(llm_rec, ["mistral:7b-q2", "mistral:7b-q4"], f"Geçersiz LLM model önerisi: {llm_rec}")

    def test_03_cache_controller_flow(self):
        """mark_loaded -> get_unload_candidates LRU akışını test et"""
        cc = CacheController()
        
        # 1. Modülleri yükle (sıra: mod1, mod2, mod3)
        cc.mark_loaded("mod1", 100)
        cc.mark_loaded("mod2", 200)
        cc.mark_loaded("mod3", 300)
        
        # En son eklenen mod3 olduğu için LRU sırası: ['mod3', 'mod2', 'mod1']
        loaded = cc.get_loaded_modules()
        self.assertEqual(loaded, ["mod3", "mod2", "mod1"], "LRU ekleme sırası hatalı")
        
        # 2. Touch işlemi (mod2'yi öne taşı)
        cc.touch("mod2")
        loaded_after_touch = cc.get_loaded_modules()
        self.assertEqual(loaded_after_touch, ["mod2", "mod3", "mod1"], "touch() sonrası LRU sırası hatalı")
        
        # 3. get_unload_candidates() Testi
        # RAM baskısı "high" ise adaylar döner, aksi halde boş döner
        candidates = cc.get_unload_candidates()
        pressure = MemoryManager.get_ram_pressure()
        
        if pressure == "high":
            # Beklenen aday sırası, en az kullanılan en başta olmalı: ['mod1', 'mod3', 'mod2']
            self.assertEqual(candidates, ["mod1", "mod3", "mod2"], "Boşaltma adayları sırası hatalı (LRU'dan en eskiye)")
        else:
            self.assertEqual(candidates, [], "Baskı high değilken aday dönmemeli")
            
        # 4. Boşaltma işlemi
        freed = cc.mark_unloaded("mod1")
        self.assertEqual(freed, 100, "mark_unloaded yanlış serbest bırakılan MB döndürdü")
        self.assertEqual(cc.size(), 2, "Modül boşaltıldıktan sonra cache boyutu hatalı")

    def test_04_stress_test_memory_leak(self):
        """50 iterasyonlu döngüde get_available_ram çağır, bellek sızıntısı olmadığını kontrol et"""
        ITERATIONS = 50
        
        # Başlangıç process belleği
        start_memory = MemoryManager.get_process_usage()
        
        for i in range(ITERATIONS):
            # API çağrıları
            avail = MemoryManager.get_available_ram()
            ratio = MemoryManager.get_usage_ratio()
            pressure = MemoryManager.get_ram_pressure()
            summary = MemoryManager.summary()
            
            # Aşırı hızlı çalışıp sistemi yanıltmaması için çok kısa bekleme
            time.sleep(0.01)

        # Bitiş process belleği
        end_memory = MemoryManager.get_process_usage()
        
        # Sızıntı toleransı (C++ - Python entegrasyonu, gc falan sebebiyle 5 MB tolerans verelim)
        diff = end_memory - start_memory
        self.assertLess(diff, 5, f"Olası bellek sızıntısı: İşlem sırasında bellek {diff} MB arttı (Max tolerans 5 MB)")

if __name__ == "__main__":
    unittest.main(verbosity=2)

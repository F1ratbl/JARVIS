# JARVIS

JARVIS, macOS uzerinde calisan, veri mahremiyetini merkeze alan yerel bir sesli yapay zeka asistanidir. Sistem; wake-word algilama, yerel STT, yerel LLM cikarimi, macOS otomasyonu, metin-ses donusumu ve gerektiginde DuckDuckGo uzerinden hafif web baglami toplama katmanlarini tek bir moduler mimaride birlestirir.

## Problem

Alexa, Siri ve Google Assistant gibi yaygin sesli asistanlar, kullanici sesini ve ortamdan uretilen metin verisini genellikle bulut servislerinde isler. Bu mimari; konusma kaliplari, aliskanliklar ve kisisel bilgiler gibi hassas verilerin ucuncu taraf altyapilara tasinmasina neden olur. Bu durum GDPR ve KVKK acisindan veri minimizasyonu, acik riza, saklama suresi ve veri egemenligi riskleri dogurur.

JARVIS bu problemi, temel yapay zeka islemlerini yerel donanimda calistirarak azaltmayi hedefler.

## Amac

Projenin amaci; kullanici verisini mumkun oldugunca cihazda tutan, sesle kontrol edilebilen ve macOS ile entegre calisan bir kisisel asistan gelistirmektir.

Temel hedefler:

- Wake-word ile yalnizca cagrildiginda aktiflesme
- Whisper tabanli yerel konusma tanima
- Ollama uzerinden yerel LLM cikarimi
- macOS AppleScript/subprocess otomasyonu
- Yerel TTS icin macOS `say`
- Web gerektiren sorularda bulut LLM API'si kullanmadan DuckDuckGo snippet'leriyle hizli cevap verme; istenirse yerel LLM ozetleme moduna gecebilme
- Dusuk RAM kullanimina uygun lazy loading ve model onerisi

## Kapsam

Mevcut kapsam:

- `assistant/ear.py`: wake-word/push-to-talk, dinamik ses kaydi, ses normalizasyonu, Whisper STT
- `assistant/brain.py`: Turkce dogal dili JSON aksiyona ceviren Ollama tabanli LLM katmani
- `assistant/hands.py`: macOS otomasyonu, fuzzy app matching, action plugin dispatcher
- `assistant/mouth.py`: macOS `say` ve opsiyonel gTTS TTS katmani
- `assistant/config.py`: model, STT, TTS ve gizlilik ayarlari
- `app/api.py`: FastAPI + WebSocket dashboard
- `app/desktop.py`: yerel dashboard'u native masaustu penceresinde acan launcher
- `app/main.py`: terminal modu giris noktasi
- `core/loader.py`: RAM kontrollu lazy loader ve model onerisi
- `core/first_run.py`: first-run ortam kontrolu
- `core/metrics.py`: STT, LLM, action ve TTS latency olcumu
- `plugins/base.py`: Strategy kalibina uygun action plugin arayuzu
- `memory_manager/`: C++/Python fallback bellek yoneticisi

## Mimari

```text
Wake Word / Push-to-Talk
        |
        v
assistant/ear.py  -> Dinamik kayit -> Whisper STT
        |
        v
assistant/brain.py -> Ollama LLM -> JSON action
        |
        v
assistant/hands.py -> Plugin Registry / Strategy -> macOS action
        |
        v
assistant/mouth.py -> TTS
```

Web paneli ayni cekirdek akisla calisir:

```text
frontend/index.html + app.js
        |
        v
app/api.py /ws
        |
        v
assistant/brain.py + assistant/hands.py + assistant/mouth.py
```

## Veri Akisi ve Gizlilik

Varsayilan yerel akis:

1. Wake-word sesi cihazda islenir.
2. Komut sesi gecici WAV dosyasina yazilir.
3. WAV dosyasi yerel Whisper modeliyle metne cevrilir.
4. Gecici ses dosyasi silinir.
5. Metin yerel Ollama modeline gonderilir.
6. Uretilen JSON action yerel macOS otomasyonuna uygulanir.
7. Sonuc macOS `say` ile seslendirilir.

Disariya cikabilecek veriler:

- `web_search` aksiyonunda arama sorgusu DuckDuckGo tarafina gider.
- `TTS_ENGINE = "gtts"` secilirse metin Google TTS servisine gider.
- Ilk model kurulumunda Ollama modeli internetten indirilir.
- `DEBUG=True` iken transkript ve model ciktisi terminal loglarinda gorunebilir.

Mahremiyet icin onerilen ayarlar:

- `assistant/config.py` icinde `TTS_ENGINE = "macos_say"` kullanin.
- Hassas kullanimda `DEBUG = False` yapin.
- Web arama aksiyonunu yalnizca guncel bilgi gerektiginde kullanin.

## DuckDuckGo, SearXNG ve Tor Karsilastirmasi

| Secenek | Ek surec | Yaklasik RAM etkisi | Gecikme | Gizlilik | Tercih nedeni |
| --- | --- | ---: | --- | --- | --- |
| `ddgs` / DuckDuckGo | Yok | Cok dusuk | Dusuk | Sorgu DuckDuckGo'ya gider | Dusuk RAM, kolay kurulum, snippet tabanli hafif RAG |
| SearXNG | Var | 150-300 MB | Orta | Instance'a bagli | Ayri servis ve RAM maliyeti nedeniyle bu prototipte secilmedi |
| Tor yonlendirme | Var | 50 MB+ | Yuksek | Ag anonimligi daha guclu | Gecikme ve daemon maliyeti nedeniyle varsayilan degil |

Bu projede `ddgs` secilmistir. Web sonuclari yalnizca kisa metin snippet'leri olarak tutulur. Varsayilan modda hizli snippet cevabi uretilir; daha akici ama daha yavas cevap gerektiginde `WEB_SEARCH_USE_LLM_SUMMARY = True` ile sonuclar yerel LLM'e baglam olarak verilebilir.

## Fuzzy App Matching

Uygulama yonetiminde sesli komut hatalarini azaltmak icin fuzzy matching vardir.

Ornekler:

- "krom ac" -> `Google Chrome`
- "vs code ac" -> `Visual Studio Code`
- "notlar ac" -> `Notes`
- "hesap makinesi ac" -> `Calculator`

Bu katman once bilinen alias listesini dener, sonra `/Applications`, `/System/Applications`, `/System/Applications/Utilities` ve kullanici `Applications` klasorlerinde `.app` arar.

## Plugin / Strategy Mimarisi

Action calistirma katmani artik tek bir `action_map` sozlugune bagli degildir. `plugins/base.py` icinde:

- `ActionPlugin`
- `FunctionActionPlugin`
- `ActionRegistry`
- `CommandValidationError`

yapilari bulunur. `hands.execute_action()` gelen JSON komutu registry uzerinden ilgili Strategy plugin'ine yonlendirir.

Yeni bir action eklemek icin:

1. `assistant/hands.py` icinde action fonksiyonunu yazin veya ayri modulden import edin.
2. `_build_action_registry()` icinde `FunctionActionPlugin(...)` olarak kaydedin.
3. `assistant/brain.py` system prompt'una action formatini ekleyin.

## Guvenlik

Action dispatcher yalnizca registry'de tanimli action'lari calistirir. Eksik parametreler yakalanir ve kullaniciya hata mesaji dondurulur.

Onay gerektiren aksiyonlar desteklenir. Ornegin `empty_trash`, dogrudan calismak yerine once onay ister. Kullanici "onayliyorum" derse `confirm_action`, "iptal et" derse `cancel_action` uretilir.

## First-Run Kontrolu

Ortam kontrolu icin:

```bash
./venv/bin/python -m core.first_run
```

Kontrol edilen basliklar:

- macOS platformu
- `say`, `osascript`, `ollama` komutlari
- `faster_whisper`, `sounddevice`, `numpy`, `scipy`, `ddgs`, `openwakeword`, `pyaudio` Python paketleri

Web dashboard `system_info` mesajlarina bu kontrol sonuclarini da ekler.

## Calistirma

Terminal modu:

```bash
./venv/bin/python -m app.main
```

Web dashboard:

```bash
./venv/bin/python -m app.api
```

Ardindan:

```text
http://localhost:8000
```

Masaustu uygulamasi (gelistirme modu):

```bash
./venv/bin/python -m app.desktop
```

Bu komut FastAPI sunucusunu sadece `127.0.0.1` uzerinde arka planda baslatir ve dashboard'u native bir pencere icinde acar. `pywebview` kurulu degilse ayni yerel adres varsayilan tarayicida acilir.

macOS `.app` paketi uretmek:

```bash
./venv/bin/python -m pip install -r requirements.txt
./scripts/build_macos_app.sh
open dist/JARVIS.app
```

Paketlenmis uygulama yine yerel Ollama, macOS `say`, mikrofon ve AppleScript izinlerine ihtiyac duyar. Ilk calistirmada macOS mikrofon/otomasyon izni sorabilir.

## 6. Performans Testleri ve Optimizasyon

`core/metrics.py`, her komut icin asama surelerini olcer:

- `stt`
- `llm`
- `action`
- `tts`
- `total`

`DEBUG=True` iken terminalde `Latency: stt=... | llm=... | action=... | tts=...` ciktisi gorulur. WebSocket tarafinda `latency` eventi yayinlanir.

Hedef: STT + LLM + action + TTS toplam dongusunu mumkun oldugunca 3 saniye altinda tutmak.

Model secimi `assistant/config.py` icindeki `OLLAMA_MODEL` ile yapilir. Varsayilan model `qwen2.5:7b` olarak ayarlidir; Turkce komutlari, JSON aksiyon ciktilarini ve arac kullanimini `llama3.2` gibi kucuk modellere gore daha tutarli takip eder. RAM'e gore otomatik secim isterseniz degeri `"auto"` yapabilirsiniz.

8 GB RAM'li sistemlerde onerilen pratik secim `qwen2.5:7b`, daha hizli ama daha zayif alternatif `llama3.2`, daha genis bellekli sistemlerde denenebilecek alternatifler ise `qwen3:8b`, `llama3.1:8b` veya `gemma3:12b` modelleridir.

### 6.1. Gecikme (Latency) Testleri

Olcumler 11 Mayis 2026 tarihinde, 8 GB RAM'li macOS ortaminda yapilmistir. Testlerde varsayilan model once `qwen3:8b`, optimizasyonlardan sonra `qwen2.5:7b` olarak kullanilmistir.

Ilk testlerde asil gecikmenin STT, TTS veya DuckDuckGo aramasindan degil; yerel LLM'in ilk calismasindan ve `assistant/brain.py` icindeki uzun sistem prompt'unun her istekte islenmesinden kaynaklandigi gorulmustur.

| Asama / Senaryo | Optimizasyon oncesi | Optimizasyon sonrasi | Not |
| --- | ---: | ---: | --- |
| `merhaba` ilk LLM cevabi, uzun prompt | 27.358 sn | - | `qwen2.5:7b`, preload yok |
| `merhaba` mevcut preload ile, uzun prompt | 25.281 sn | - | Sadece kisa LLM warmup yeterli olmadi |
| `merhaba` kompakt prompt ile, preload yok | - | 14.921 sn | Sistem prompt'u 6611 karakterden 1683 karaktere indirildi |
| `merhaba` kompakt prompt + brain preload | - | 2.666 sn | Preload dogrudan `brain.process_command()` yolunu isitir |
| Kural tabanli komut anlama | 0.000-0.003 sn | 0.000-0.003 sn | `takvimi ac`, takvim etkinligi, hava durumu niyeti |
| Hava durumu API aksiyonu | 0.665-1.037 sn | 0.665-1.037 sn | `wttr.in` tabanli deterministik cevap |
| DuckDuckGo sadece arama | 1.927 sn | 1.927 sn | Arama katmani ana darboğaz degil |
| DuckDuckGo hizli snippet cevabi | 42-58 sn LLM ozetleme | 1-2 sn | Varsayilan mod LLM ozetlemeyi beklemez |
| DuckDuckGo + LLM ozetleme | 42-58 sn | Opsiyonel / kapali | Daha akici ozet uretir ancak 8 GB RAM'de agir kalir |
| STT model yukleme | 14.328 sn | Preload ile acilisa tasindi | Ilk sesli kullanimda hissedilen gecikme azalir |
| STT kisa ses transkripsiyonu | 0.858 sn | 0.858 sn | Whisper model yuklendikten sonraki sure |
| TTS kisa cevap | 1.848 sn | 1.848 sn | `macOS say`, sesli okuma suresi dahil |
| TTS orta cevap | 6.596 sn | 6.596 sn | Cevap uzadikca dogrudan artar |

Pratik UI deneyiminde cevap balonu artik TTS'in bitmesini beklemeden gosterilir. Bu nedenle kullanicinin ekranda gordugu sure, sesli okumanin tamamlanma suresinden ayrilmistir. Son deneyimlerde gozlenen yaklasik sureler:

| Komut | UI'da gorunen fark | Hedefe gore durum |
| --- | ---: | --- |
| `telegrami ac` | Anlik | Hedefin icinde |
| `nvidia nedir` | ~2 sn | Hedefin icinde |
| `merhaba` | ~5 sn | Hedefin uzerinde |

Bu ayrim onemlidir: uygulama acma gibi deterministik komutlar LLM'e gitmeden calistigi icin anliktir. Serbest sohbet ise hala yerel LLM cikarimina baglidir; bu nedenle `merhaba` gibi basit gorunen ifadeler bile model tarafinda 5 saniye civarina cikabilir.

Yapilan gecikme optimizasyonlari:

- Model `qwen3:8b` yerine 8 GB RAM icin daha dengeli `qwen2.5:7b` olarak ayarlandi.
- `OLLAMA_KEEP_ALIVE = "30m"` eklendi; model her komuttan sonra hemen bellekten dusmesin.
- `OLLAMA_NUM_CTX` 4096'dan 2048'e indirildi; komut JSON'u icin yeterli ama daha hizli baglam penceresi kullanildi.
- Runtime sistem prompt'u 6611 karakterden 1683 karaktere indirildi.
- Preload sadece `global_loader.get("llm")` yapmak yerine dogrudan `brain.process_command("Hazir misin?")` cagirarak tam brain yolunu isitir hale getirildi.
- Web aramada varsayilan olarak hizli snippet cevabi donuldu; LLM ozetleme opsiyonel hale getirildi.
- TTS, UI cevabini bloklamayacak sekilde arka plana alindi.
- Uygulama acma komutlarinda cevap balonu once gosterilip asil macOS aksiyonu arka planda calistirildi.

### 6.2. Kaynak Tuketimi (RAM & CPU/GPU)

Test sirasinda C++ destekli `memory_manager` uzerinden raporlanan bellek durumu genel olarak su aralikta olculmustur:

| Durum | RAM kullanimi | Kullanilabilir RAM | Bellek baskisi |
| --- | ---: | ---: | --- |
| Normal test araligi | %63-%74 | 2.1-3.0 GB | medium |
| Daha bos durumda web/LLM ayrimi | %49 civari | 4.1 GB | low |
| `qwen3:8b` denemeleri | %77-%83 | 1.3-1.8 GB | medium/high siniri |

`qwen3:8b` modeli 8 GB RAM'de teorik olarak calissa da pratikte model runner'in durmasina ve 40-50 saniyeyi asan cevap surelerine yol acmistir. Bu nedenle varsayilan model `qwen2.5:7b` olarak dusurulmustur. Bu tercih, kalite ile bellek kararliligi arasinda daha dengeli sonuc vermektedir.

Kaynak kullanimini azaltmak icin uygulanan kararlar:

- LLM modeli RAM'e gore secilebilir hale getirildi.
- Ayarlar paneline model secimi eklendi.
- 8 GB RAM icin model onerisi artik `qwen3:8b` yerine `qwen2.5:7b` verir.
- Whisper, web arama modulu ve LLM arka planda preload edilir.
- Gereksiz buyuk sistem prompt'u kisaltilarak token isleme maliyeti azaltildi.

### 6.3. Donanim Avantajlari

Hedef platform Apple Silicon macOS olarak secildigi icin sistem, birlesik bellek (Unified Memory) mimarisinden faydalanir. CPU, GPU ve Neural Engine ayni fiziksel bellek havuzunu paylastigi icin veri kopyalama maliyeti klasik ayrik bellek mimarilerine gore daha dusuktur. Bu, yerel model cikariminda ve ses isleme akisinda avantaj saglar.

Buna ragmen 8 GB RAM sinifi, 7B-8B arasi modeller icin sinirli bir alandir. Bu projede yapilan testler, 8 GB cihazlarda model seciminin yanit suresini dogrudan belirledigini gostermistir:

- `qwen3:8b`: Daha zeki ancak 8 GB RAM'de gecikme ve runner kararliligi riski yuksek.
- `qwen2.5:7b`: Turkce komut ve JSON uretimi icin daha dengeli varsayilan.
- `llama3.2:latest`: Daha hizli alternatif; ancak Turkce/anlama kalitesi daha zayif olabilir.

Bu nedenle sistem ilk kurulumda RAM'i analiz eder, model secimi icin oneride bulunur ve nihai karari kullaniciya birakir.

## Test

Mevcut testleri calistirma:

```bash
./venv/bin/python tests/test_memory_manager.py
./venv/bin/python tests/test_action_plugins.py
```

Sözdizimi kontrolu:

```bash
./venv/bin/python -m py_compile assistant/ear.py assistant/brain.py assistant/hands.py assistant/mouth.py assistant/config.py app/main.py app/api.py core/loader.py core/first_run.py core/metrics.py plugins/base.py
```

## Kisitlar

- Platform: AppleScript nedeniyle macOS hedeflenir.
- Donanim: 7B-8B sinifi yerel modeller icin minimum 8 GB RAM, daha kararlı deneyim icin 16 GB RAM tavsiye edilir.
- Web arama: Bulut LLM/STT API kullanmaz, ancak DuckDuckGo'ya sorgu gonderir.
- Wake-word: Ses buluta gitmez; fakat mikrofon stream'i yerel olarak surekli dinlenir.
- TTS: Varsayilan `macos_say` yerlidir; `gtts` secilirse bulut servisi kullanilir.

## Yol Haritasi

- Dashboard'da first-run check listesini gorsel hale getirme
- Daha kapsamli unit testler
- Plugin'leri ayri dosyalara bolme
- Tehlikeli action'lar icin daha gelismis onay akisi
- Whisper `small` model secenegi icin otomatik kalite/latency karsilastirmasi

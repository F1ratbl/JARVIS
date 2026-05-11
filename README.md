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
- Web gerektiren sorularda bulut LLM API'si kullanmadan DuckDuckGo snippet'lerini yerel modele baglam olarak verme
- Dusuk RAM kullanimina uygun lazy loading ve model onerisi

## Kapsam

Mevcut kapsam:

- `assistant/ear.py`: wake-word/push-to-talk, dinamik ses kaydi, ses normalizasyonu, Whisper STT
- `assistant/brain.py`: Turkce dogal dili JSON aksiyona ceviren Ollama tabanli LLM katmani
- `assistant/hands.py`: macOS otomasyonu, fuzzy app matching, action plugin dispatcher
- `assistant/mouth.py`: macOS `say` ve opsiyonel gTTS TTS katmani
- `assistant/config.py`: model, STT, TTS ve gizlilik ayarlari
- `app/api.py`: FastAPI + WebSocket dashboard
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

Bu projede `ddgs` secilmistir. Web sonuclari yalnizca kisa metin snippet'leri olarak tutulur ve yerel LLM'e baglam olarak verilir.

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

## Performans Olcumu

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
- Donanim: Llama 3 icin minimum 8 GB RAM, tavsiye edilen 16 GB RAM.
- Web arama: Bulut LLM/STT API kullanmaz, ancak DuckDuckGo'ya sorgu gonderir.
- Wake-word: Ses buluta gitmez; fakat mikrofon stream'i yerel olarak surekli dinlenir.
- TTS: Varsayilan `macos_say` yerlidir; `gtts` secilirse bulut servisi kullanilir.

## Yol Haritasi

- Dashboard'da first-run check listesini gorsel hale getirme
- Daha kapsamli unit testler
- Plugin'leri ayri dosyalara bolme
- Tehlikeli action'lar icin daha gelismis onay akisi
- Whisper `small` model secenegi icin otomatik kalite/latency karsilastirmasi

# JARVIS Teknik Dokumantasyon

Bu dokuman, JARVIS projesinin kurulumu, dosya yapisi, temel calisma akisi ve gelistirme noktalarini aciklar.

## 1. Proje Ozeti

JARVIS, macOS uzerinde calisan yerel bir yapay zeka asistanidir. Kullanici komutlarini sesli veya yazili olarak alir, yerel model yardimiyla ya da kural tabanli cozumle JSON aksiyonlara donusturur ve macOS uzerinde gerekli islemleri calistirir.

Temel hedefler:

- Kullanici verisini mumkun oldugunca cihazda tutmak
- Bulut LLM/STT API kullanmadan calismak
- Sesli ve yazili komutlari desteklemek
- macOS uygulamalarini yonetmek
- Web arama gerektiren sorularda hizli cevap uretmek
- Dusuk RAM sinifinda calisabilecek model secimi sunmak

## 2. Klasor Yapisi

```text
app/
  api.py          Web dashboard, FastAPI ve WebSocket giris noktasi
  main.py         Terminal modu giris noktasi

assistant/
  brain.py        Komut anlama ve JSON aksiyon uretimi
  config.py       Model, STT, TTS ve genel ayarlar
  ear.py          Wake-word, mikrofon kaydi ve STT
  hands.py        macOS aksiyonlari ve plugin dispatcher
  mouth.py        TTS / sesli cevap

core/
  first_run.py    Ortam kontrolu
  loader.py       Lazy loading, RAM kontrolu, model onerisi
  metrics.py      Latency olcumleri

frontend/
  index.html      Web arayuzu
  app.js          WebSocket, sohbet gecmisi, ayarlar mantigi
  style.css       Arayuz stilleri ve animasyonlar

plugins/
  base.py         Strategy kalibi icin action plugin altyapisi

tests/
  test_brain_rules.py
  test_action_plugins.py
  test_memory_manager.py
```

## 3. Kurulum

Python sanal ortamini aktif ettikten sonra bagimliliklar yuklenir:

```bash
python3 -m venv venv
./venv/bin/python -m pip install -r requirements.txt
```

Ollama kurulu olmalidir. Kullanilan varsayilan model:

```text
qwen2.5:7b
```

Model yuklu degilse arayuzdeki model secim ekranindan indirilebilir.

## 4. Calistirma

Web dashboard:

```bash
./venv/bin/python -m app.api
```

Tarayici:

```text
http://localhost:8000
```

Terminal modu:

```bash
./venv/bin/python -m app.main
```

## 5. Temel Calisma Akisi

### 5.1. Yazili Komut Akisi

```text
frontend/app.js
    -> WebSocket /ws
    -> app/api.py process_text_command()
    -> assistant/brain.py process_command()
    -> assistant/hands.py execute_action()
    -> assistant/mouth.py speak()
```

Yazili komutlarda kullanici mesaji WebSocket ile sunucuya gider. Sunucu komutu `brain.py` ile yorumlar, `hands.py` ile uygular ve cevabi UI'a gonderir. TTS artik arka planda calistigi icin UI cevabi sesin bitmesini beklemez.

### 5.2. Sesli Komut Akisi

```text
assistant/ear.py
    -> wake-word / push-to-talk
    -> audio record
    -> Whisper STT
    -> brain.py
    -> hands.py
    -> mouth.py
```

Sesli kullanimda mikrofon kaydi gecici WAV dosyasina yazilir, Whisper ile metne cevrilir ve islem sonunda dosya silinir.

## 6. Moduller

### 6.1. `assistant/brain.py`

Sistemin karar verme katmanidir. Gelen metni JSON aksiyona cevirir.

Ornek:

```json
{"action": "open_app", "target": "Telegram"}
```

Once kural tabanli komutlar denenir. Cozulemeyen durumlarda Ollama uzerinden yerel LLM kullanilir.

Onemli ozellikler:

- Kompakt system prompt
- JSON formatinda cikti zorlama
- Conversation history
- Hava durumu takip sorulari icin son sehir bilgisini hatirlama
- Web sorularini `web_search` aksiyonuna yonlendirme

### 6.2. `assistant/hands.py`

JSON aksiyonlari gercek islemlere cevirir.

Desteklenen bazi aksiyonlar:

- `open_app`
- `close_app`
- `create_event`
- `create_note`
- `get_weather`
- `web_search`
- `set_volume`
- `general_response`

Web aramada varsayilan mod hizli snippet cevabidir. LLM ozetleme icin:

```python
WEB_SEARCH_USE_LLM_SUMMARY = True
```

### 6.3. `assistant/ear.py`

Mikrofon kaydi, wake-word ve Whisper STT islemlerini yurutur.

Onemli ayarlar:

```python
WHISPER_MODEL_SIZE = "base"
RECORD_DYNAMIC_ENABLED = True
SILENCE_DURATION = 1.0
```

### 6.4. `assistant/mouth.py`

TTS katmanidir. Varsayilan motor macOS `say` komutudur:

```python
TTS_ENGINE = "macos_say"
TTS_VOICE = "Yelda"
TTS_RATE = 180
```

## 7. Yapilandirma

Ana ayar dosyasi:

```text
assistant/config.py
```

Onemli LLM ayarlari:

```python
OLLAMA_MODEL = "qwen2.5:7b"
OLLAMA_NUM_CTX = 2048
OLLAMA_KEEP_ALIVE = "30m"
WEB_SEARCH_USE_LLM_SUMMARY = False
```

8 GB RAM icin `qwen2.5:7b` varsayilan olarak secilmistir. Daha hizli ama daha zayif alternatif olarak `llama3.2:latest` denenebilir.

## 8. Arayuz Ozellikleri

Web arayuzunde:

- Sohbet gecmisi
- Yeni sohbet
- Tek sohbet silme
- Tum sohbetleri silme
- Ayarlar paneli
- Model secimi
- Model indirme
- RAM bilgisi
- Mikrofon dinleme animasyonu

bulunur.

## 9. Performans Notlari

Son olcumlere gore:

| Senaryo | Sure |
| --- | ---: |
| `telegrami ac` | Anlik |
| `nvidia nedir` | Yaklasik 2 sn |
| `merhaba` | Yaklasik 5 sn |
| `nasilsin` | 8-10 sn |

Deterministik komutlarda hedeflenen 3 saniye tutturulmustur. Serbest sohbet cevaplari yerel LLM'in cevap uretme suresine baglidir.

Yapilan optimizasyonlar:

- `qwen3:8b` yerine `qwen2.5:7b`
- Preload
- `keep_alive`
- Kompakt prompt
- Kucuk context penceresi
- UI cevabini TTS'ten once gonderme
- Web aramada hizli snippet modu

## 10. Testler

Sözdizimi kontrolu:

```bash
./venv/bin/python -m py_compile app/api.py assistant/brain.py assistant/hands.py assistant/ear.py assistant/mouth.py
```

Birim testleri:

```bash
./venv/bin/python tests/test_brain_rules.py
./venv/bin/python tests/test_action_plugins.py
```

## 11. Yeni Aksiyon Ekleme

1. `assistant/hands.py` icine aksiyon fonksiyonu yazilir.
2. `_build_action_registry()` icinde `FunctionActionPlugin` olarak kaydedilir.
3. `assistant/brain.py` system prompt'una aksiyon formati eklenir.
4. Gerekirse test dosyalarina yeni test eklenir.

## 12. Bilinen Sinirlar

- macOS disinda tam destek yoktur.
- 8 GB RAM'de buyuk modeller yavas veya kararsiz calisabilir.
- Serbest sohbet yanitlari 3 saniye hedefinin uzerine cikabilir.
- Web aramada hizli snippet modu daha hizlidir, ancak LLM ozet modu kadar akici ozet uretmez.
- Wake-word surekli yerel mikrofon akisi gerektirir.

## 13. Gelecek Gelistirmeler

- Streaming LLM cevabi
- Daha hizli sohbet modeli modu
- Ekran okuma ve goruntu isleme
- Kalici yerel hafiza
- Daha gelismis takvim/hatirlatici yonetimi
- Performans grafiklerinin arayuzde gosterilmesi

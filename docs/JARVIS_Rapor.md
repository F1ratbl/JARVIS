# JARVIS

## Yerel, Gizlilik Odakli, Sesli Kontrol Edilen Yapay Zeka Asistani

**Grup Adi:** Bir Kutu Hurda  
**Grup Uyeleri:** Firat Bali, Merve Barisik, Hamza Cakmakci, Omer Erdem  
**Universite:** Bitlis Eren Universitesi  
**Bolum:** Yazilim Muhendisligi  
**Danisman:** Ozlem Seker  
**Tarih:** 12/05/2026

## Ozet

JARVIS, macOS uzerinde calisan, kullanici verisini mumkun oldugunca yerel donanimda isleyen, sesli ve yazili komutlarla kontrol edilebilen bir kisisel yapay zeka asistani olarak gelistirilmistir. Projenin cikis noktasi, Alexa, Siri ve Google Assistant gibi bulut tabanli asistanlarin kullanici sesi, komut gecmisi ve davranis verilerini ucuncu taraf altyapilarda islemesi nedeniyle ortaya cikan gizlilik ve veri egemenligi riskleridir. Baslangictaki Bir Kutu Hurda ara raporunda hedeflenen; wake-word, yerel STT, yerel LLM, TTS, macOS otomasyonu, DuckDuckGo tabanli hafif web arama ve dusuk RAM tuketimli mimari hedefleri bu uygulamada somut bir prototipe donusturulmustur. Gelistirme surecinde yalnizca hedeflenen ozellikler uygulanmamis, ek olarak model secim arayuzu, sohbet gecmisi, preload mekanizmasi, prompt optimizasyonu, hizli web cevabi, ayarlar paneli ve performans olcumleri de sisteme eklenmistir.

**Anahtar kelimeler:** Yerel yapay zeka, sesli asistan, macOS otomasyonu, veri gizliligi, Ollama, Whisper, DuckDuckGo, KVKK, GDPR

## 1. Giris

### 1.1. Problem Tanimi

Yapay zeka destekli sesli asistan teknolojileri son yillarda hizli bir gelisim gostermis; Amazon Alexa, Google Assistant ve Apple Siri gibi sistemler gunluk hayatin bir parcasi haline gelmistir. Ancak bu sistemlerin onemli bir bolumu, kullanicidan alinan ses ve komut verilerini bulut sunucularinda islemektedir. Bu mimari, kullanicinin konusma kaliplarinin, aliskanliklarinin, kisisel tercihlerinin ve mahrem bilgilerinin ucuncu taraf altyapilara tasinmasina neden olabilir.

Bu durum, Avrupa Birligi Genel Veri Koruma Yonetmeligi (GDPR) ve Turkiye'deki Kisisel Verilerin Korunmasi Kanunu (KVKK) acisindan veri minimizasyonu, acik riza, saklama suresi ve veri egemenligi riskleri dogurur. Bir Kutu Hurda ara raporunda bu temel problem "bulut tabanli asistanlarin mimari ve gizlilik kirilganligi" olarak tanimlanmisti. Gelistirilen JARVIS prototipi bu probleme yerel calisan, kullanici verisini cihazdan cikarmamayi hedefleyen bir alternatif sunmaktadir.

### 1.2. Projenin Amaci

Projenin temel amaci; veri mahremiyetini merkeze alan, sesli komutlarla kontrol edilebilen, macOS isletim sistemiyle entegre calisan ve temel yapay zeka islemlerini yerel donanim uzerinde yuruten bir kisisel asistan gelistirmektir. Sistem; konusma tanima, dogal dil anlama, yerel LLM cikarimi, web arama ile baglam toplama, metinden sese donusum ve macOS otomasyonunu tek bir moduler mimaride birlestirmektedir.

Baslangicta yalnizca temel sesli komut ve yerel model calistirma hedeflenirken, uygulama surecinde su noktalarda proje daha ileri tasinmistir:

- Ilk kurulum ekranina RAM'e gore model onerisi eklendi.
- Ayarlar panelinden model secimi ve model indirme akisi eklendi.
- Sohbet gecmisi, yeni sohbet olusturma ve sohbet silme ozellikleri eklendi.
- Uzun sistem prompt'u kisaltilarak LLM yanit gecikmesi azaltildi.
- `qwen3:8b` modelinin 8 GB RAM icin agir kaldigi gorulerek varsayilan model `qwen2.5:7b` yapildi.
- `keep_alive` ve preload ile modelin tekrar tekrar soguk baslamasi engellendi.
- Web aramalarinda once hizli snippet cevabi donulerek 40-58 saniyelik gecikme 1-2 saniye bandina indirildi.

### 1.3. Kapsam ve Sinirlar

Proje kapsaminda asagidaki bilesenler gerceklestirilmistir:

- Wake-word veya push-to-talk ile komut baslatma
- Whisper tabanli yerel STT
- Ollama uzerinden yerel LLM cikarimi
- Turkce dogal dil komutlarini JSON aksiyonlara ceviren `brain.py`
- macOS AppleScript/subprocess otomasyon katmani
- Fuzzy matching destekli uygulama yonetimi
- DuckDuckGo tabanli web arama
- macOS `say` ile yerel TTS
- Strategy kalibina dayali plugin mimarisi
- FastAPI + WebSocket tabanli web arayuzu
- Sohbet gecmisi ve model ayarlari arayuzu
- Performans olcumleri ve gecikme optimizasyonlari

Kapsam disinda kalan veya gelecek calismalara birakilan konular; ekran okuma, goruntu isleme, gelismis ajan planlama, uzun sureli kalici hafiza ve cok adimli gorev yurutme olarak belirlenmistir.

### 1.4. Varsayimlar ve Kisitlar

Sistem macOS hedeflenerek gelistirilmistir. AppleScript ve macOS `say` bagimliligi nedeniyle tam islevsellik macOS disinda garanti edilmez. Gelistirme ortaminda 8 GB RAM sinifi dikkate alinmis, bu nedenle buyuk yerel modellerde RAM baskisi onemli bir kisit olarak ortaya cikmistir. Yerel LLM cikarimi icin Ollama kullanilmaktadir. Web arama gerektiren durumlarda bulut LLM API'leri kullanilmamakta, DuckDuckGo uzerinden alinan kisa metin sonuclari yerel isleme katmanina sunulmaktadir.

## 2. Ilgili Calismalar

### 2.1. Bulut Tabanli Asistanlar

Alexa, Siri ve Google Assistant gibi sistemler yuksek dogruluk ve genis servis entegrasyonu sunsa da, kullanici verisinin onemli bir kismini bulut altyapisinda isler. Bu yaklasim guclu hesaplama imkani saglar; ancak veri gizliligi, hizmete bagimlilik, internet kesintilerinde calisamama ve ucuncu taraf veri isleme risklerini beraberinde getirir.

JARVIS bu yaklasima alternatif olarak cihaz ici isleme prensibini temel alir. Ses tanima, LLM cikarimi ve TTS gibi temel bilesenler yerel calisir. Yalnizca guncel bilgi gerektiren web arama sorgulari disariya cikar.

### 2.2. Yerel LLM Araclari

Ollama gibi araclar yerel LLM calistirmayi kolaylastirir; ancak tek basina bir kisisel asistan degildir. Standart bir Ollama kurulumu, kullanici komutlarini isletim sistemi aksiyonlarina donusturmez, macOS uygulamalarini yonetmez ve sesli giris/cikis akisini sunmaz. JARVIS bu boslugu; STT, LLM, aksiyon dispatcher, TTS ve web arayuzunu bir araya getirerek doldurur.

### 2.3. Baslangic Planindan Ayrisan Gelismeler

Bir Kutu Hurda ara raporunda hedeflenen mimari; wake-word, Whisper, Ollama/Llama 3, DuckDuckGo Search, AppleScript otomasyonu ve plugin mimarisi uzerine kuruluydu. Proje ilerledikce bu hedefler korunmus, ancak pratik deneyimlerden dogan ek iyilestirmeler yapilmistir. Ozellikle Llama 3 yerine Turkce komut/JSON dengesi daha iyi olan Qwen modelleri denenmis; `qwen3:8b` kalite acisindan guclu olsa da 8 GB RAM'de yavas ve kararsiz kaldigi icin `qwen2.5:7b` varsayilan yapilmistir.

## 3. Gereksinim Analizi

### 3.1. Fonksiyonel Gereksinimler

| ID | Gereksinim | Durum |
| --- | --- | --- |
| FR-01 | Kullanici sesli komut verebilmelidir. | Gerceklestirildi |
| FR-02 | Sistem wake-word veya push-to-talk ile aktiflesmelidir. | Gerceklestirildi |
| FR-03 | Konusma yerel STT modeliyle metne cevrilmelidir. | Gerceklestirildi |
| FR-04 | Turkce komutlar JSON aksiyonlara donusturulmelidir. | Gerceklestirildi |
| FR-05 | macOS uygulamalari acilip kapatilabilmelidir. | Gerceklestirildi |
| FR-06 | Takvime etkinlik eklenebilmelidir. | Gerceklestirildi |
| FR-07 | Hava durumu ve guncel bilgi sorgulari desteklenmelidir. | Gerceklestirildi |
| FR-08 | Web arama gerektiren sorularda DuckDuckGo kullanilmalidir. | Gerceklestirildi |
| FR-09 | Sistem cevaplari sesli okuyabilmelidir. | Gerceklestirildi |
| FR-10 | Kullanici model secimi yapabilmelidir. | Plan disi ek iyilestirme olarak gerceklestirildi |
| FR-11 | Sohbet gecmisi yonetilebilmelidir. | Plan disi ek iyilestirme olarak gerceklestirildi |

### 3.2. Fonksiyonel Olmayan Gereksinimler

| ID | Kategori | Gereksinim | Hedef / Sonuc |
| --- | --- | --- | --- |
| NFR-01 | Gecikme | Kural tabanli komutlarda hizli yanit | Anlik / milisaniye seviyesi |
| NFR-02 | Gecikme | Web bilgi sorgularinda 3 sn hedefi | Son testlerde yaklasik 2 sn |
| NFR-03 | Gecikme | Serbest LLM sohbetinde 3 sn hedefi | Yaklasik 5 sn; hedefin uzerinde |
| NFR-04 | Bellek | 8 GB RAM sinifinda calisabilme | `qwen2.5:7b` ile daha dengeli |
| NFR-05 | Gizlilik | Bulut LLM/STT API kullanmama | Saglandi |
| NFR-06 | Genisletilebilirlik | Plugin mimarisi | Strategy kalibi ile saglandi |
| NFR-07 | Platform | macOS entegrasyonu | AppleScript/subprocess ile saglandi |

## 4. Sistem Mimarisi ve Tasarim

### 4.1. Genel Mimari

Sistemin temel veri akisi asagidaki gibidir:

```text
Kullanici sesi / yazisi
        |
        v
assistant/ear.py veya frontend
        |
        v
assistant/brain.py
        |
        v
assistant/hands.py
        |
        v
assistant/mouth.py
        |
        v
Kullaniciya metin/ses cevabi
```

Sesli kullanimda `ear.py` mikrofon verisini alir, Whisper ile metne cevirir ve `brain.py` katmanina gonderir. Yazili kullanimda frontend WebSocket uzerinden metni dogrudan `app/api.py` katmanina iletir. `brain.py` gelen metni once kural tabanli olarak cozmeye calisir; cozemiyorsa yerel LLM'e basvurur. Uretilen JSON aksiyon `hands.py` tarafindan calistirilir. Sonuc kullaniciya web arayuzunde gosterilir ve `mouth.py` ile seslendirilir.

### 4.2. Dogal Dil Isleme ve LLM Katmani

`assistant/brain.py` sistemin karar verme katmanidir. Kullanici metnini standart JSON komut formatina donusturur. Ornegin:

```json
{"action": "open_app", "target": "Telegram"}
```

Kritik komutlarda LLM hatalarini azaltmak icin kural tabanli on isleme kullanilir. Uygulama acma, hava durumu, takvim etkinligi ve web arama gibi sik kullanilan komutlar LLM'e gitmeden cozulur. Daha belirsiz sohbet veya yorumlama gerektiren durumlarda Ollama uzerinden yerel LLM kullanilir.

Baslangicta sistem prompt'u daha uzun ve ornek agirlikliydi. Performans testlerinde bunun ilk cevap gecikmesini artirdigi goruldu. Bu nedenle runtime prompt'u 6611 karakterden 1683 karaktere indirildi. Bu degisiklik, cevap suresinde belirgin iyilesme sagladi.

### 4.3. Hafif RAG ve Web Arama

Ara raporda planlanan DuckDuckGo tabanli hafif RAG katmani uygulanmistir. Ancak testlerde DuckDuckGo sonucunu LLM ile ozetlemenin 40-58 saniyeye kadar gecikmeye yol actigi gorulmustur. Bu nedenle varsayilan davranis hizli snippet cevabi olacak sekilde guncellenmistir. LLM ozetleme ihtiyac halinde `WEB_SEARCH_USE_LLM_SUMMARY = True` ile tekrar acilabilir.

Bu tasarim baslangic planindan daha kullanici odakli bir noktaya tasinmistir: teorik olarak daha guzel ozet uretmek yerine, pratikte 3 saniye hedefini yakalayacak hizli cevap onceliklendirilmisir.

### 4.4. macOS Entegrasyonu

`assistant/hands.py`, macOS uygulamalarini acma/kapatma, takvim etkinligi ekleme, sistem aksiyonlari ve web arama gibi islemleri yurutur. Uygulama adlarinda ses tanima hatalarini azaltmak icin fuzzy matching desteklenir. Ornegin "krom", "chrome" ve "google chrome" gibi farkli soylemler ayni uygulamaya yonlendirilebilir.

## 5. Uygulama ve Gelistirme Sureci

### 5.1. Ortam Kurulumu

Proje Python tabanli olarak gelistirilmistir. Web arayuzu FastAPI ve WebSocket ile calisir. STT icin `faster-whisper`, LLM cikarimi icin Ollama, TTS icin macOS `say`, web arama icin `ddgs` kullanilmistir.

### 5.2. Model Secimi ve Optimizasyon

Baslangic planinda Llama 3 tabanli yerel LLM dusunulmustur. Gelistirme surecinde Qwen modellerinin Turkce komut anlama ve JSON uretme konusunda daha dengeli sonuc verdigi gorulmustur. `qwen3:8b` modeli kalite acisindan iyi olsa da 8 GB RAM'de gecikme ve kararlilik sorunlari yasatmistir. Bu nedenle varsayilan model `qwen2.5:7b` olarak belirlenmistir.

Ek olarak:

- Model ayarlari arayuze tasindi.
- RAM'e gore model onerisi eklendi.
- Preload ile STT, web arama ve LLM onceden hazirlanir hale getirildi.
- `OLLAMA_KEEP_ALIVE = "30m"` ile modelin hemen bellekten dusmesi engellendi.
- `OLLAMA_NUM_CTX` 4096'dan 2048'e indirildi.

### 5.3. Plugin Mimarisi

Action calistirma katmani Strategy kalibina uygun hale getirilmistir. Yeni bir aksiyon eklemek icin ilgili fonksiyon `hands.py` icinde yazilip registry'ye eklenebilir. Bu tasarim, projenin ileride genisletilmesini kolaylastirmaktadir.

### 5.4. Arayuz Gelistirmeleri

Baslangic planinda yalnizca asistan motoru hedeflenirken, gelistirme surecinde kullanici deneyimini artiran web arayuzu olusturulmustur. Arayuzde:

- Sohbet gecmisi
- Yeni sohbet olusturma
- Sohbet silme
- Ayarlar paneli
- Model secimi
- Mikrofon animasyonu
- Preload/model durum bilgilendirmesi

ozellikleri bulunur.

## 6. Performans Testleri ve Optimizasyon

### 6.1. Gecikme Testleri

Son kullanici deneyimine gore olculen sureler asagidaki gibidir:

| Senaryo | Olculen Sure | Hedefe Gore Durum |
| --- | ---: | --- |
| `telegrami ac` | Anlik | Hedefin icinde |
| `nvidia nedir` | Yaklasik 2 sn | Hedefin icinde |
| `merhaba` | Yaklasik 5 sn | Hedefin uzerinde |
| `nasilsin` | Yaklasik 8-10 sn | Hedefin uzerinde |

Bu sonuclar, sistemin deterministik komutlarda ve hizli web bilgi sorgularinda 3 saniyelik hedefi karsiladigini; serbest sohbet cevaplarinda ise yerel LLM cikarimi nedeniyle hedefin uzerinde kaldigini gostermektedir.

Yapilan optimizasyonlar sonucunda daha once 27.358 saniye olan ilk LLM cevabi, kompakt prompt ve brain preload ile 2.666 saniyeye kadar dusurulmustur. Ancak serbest sohbetlerde modelin urettigi cevap uzunluguna bagli olarak 5-10 saniyelik sureler gorulebilmektedir.

### 6.2. Kaynak Tuketimi

Testler sirasinda 8 GB RAM sinifinda `qwen3:8b` modelinin sistemi zorladigi gorulmustur. RAM baskisi arttiginda model runner durabilmekte veya cevap sureleri belirgin bicimde yukselmektedir. `qwen2.5:7b` modeli daha dengeli calismistir. Web arama tarafinda DuckDuckGo sorgusu tek basina yaklasik 2 saniye civarinda tamamlanmistir; asil gecikme, web sonuclarinin LLM ile ozetlenmesi sirasinda ortaya cikmistir.

### 6.3. Donanim Avantajlari

Apple Silicon mimarisindeki birlesik bellek yapisi, CPU/GPU arasinda veri kopyalama maliyetini azaltarak yerel model cikarimi icin avantaj saglar. Ancak 8 GB bellek sinifi, 7B-8B arasi modeller icin hala sinirli bir calisma alanidir. Bu nedenle proje, model secimini kullaniciya birakir ve RAM durumuna gore oneride bulunur.

## 7. Guvenlik ve Gizlilik Analizi

### 7.1. Cihaz Ici Veri Isleme

JARVIS'in temel gizlilik yaklasimi, ses tanima ve LLM cikarimi gibi islemleri yerel cihazda yapmaktir. Varsayilan STT ve TTS akisinda bulut API kullanilmaz. Web arama gerektiren durumlarda yalnizca arama sorgusu DuckDuckGo tarafina gider. Model cevaplari OpenAI, Gemini veya benzeri bulut LLM servislerine gonderilmez.

### 7.2. Otomasyon Izinleri

macOS otomasyon islemleri AppleScript ve subprocess tabanli olarak calisir. Tehlikeli sayilabilecek aksiyonlar icin onay akisi desteklenmistir. Ornegin cop kutusunu bosaltma gibi islemler dogrudan calismak yerine kullanicidan onay bekler.

### 7.3. KVKK/GDPR Acisindan Degerlendirme

Sistem, veri minimizasyonu ilkesine uygun olarak kullanici verisini gereksiz yere dis servislere gondermez. Ses dosyalari gecici olarak olusturulur ve islem sonrasinda silinir. Bu tasarim, kullanicinin veri egemenligini artirmayi hedefler.

## 8. Sonuc ve Gelecek Calismalar

JARVIS projesi, baslangictaki Bir Kutu Hurda ara raporunda tanimlanan yerel, gizlilik odakli, sesli kontrol edilen yapay zeka asistani hedefini buyuk olcude gerceklestirmistir. Baslangicta planlanan wake-word, Whisper STT, Ollama LLM, DuckDuckGo web arama, macOS otomasyonu ve plugin mimarisi uygulanmis; bunlara ek olarak model secim arayuzu, sohbet gecmisi, performans optimizasyonlari ve preload mekanizmasi gelistirilmistir.

Proje, kural tabanli komutlarda ve hizli web bilgi sorgularinda hedeflenen 3 saniyelik yanit dongusunu yakalamaktadir. Serbest sohbet cevaplarinda ise yerel LLM cikarim maliyeti nedeniyle hedefin uzerinde kalinmaktadir. Gelecek calismalarda streaming cevap, daha hafif sohbet modeli, ekran okuma, yerel goruntu isleme, kalici hafiza ve daha gelismis ajan planlama ozellikleri eklenebilir.

## Kaynakca

- Apple. (2026). AppleScript Language Guide. Apple Developer Documentation.
- Ollama. (2026). Ollama local model runtime documentation.
- OpenAI. (2023). Whisper: Robust Speech Recognition via Large-Scale Weak Supervision.
- DuckDuckGo. (2026). DuckDuckGo Search.
- European Union. (2016). General Data Protection Regulation (GDPR).
- Kisisel Verileri Koruma Kurumu. (2016). Kisisel Verilerin Korunmasi Kanunu.

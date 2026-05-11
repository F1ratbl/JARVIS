"""
🧠 JARVIS — Beyin Modülü (LLM Komut İşleme)
Ollama + Llama3 ile doğal dili JSON komutlarına çevirir.
Conversation memory ve genişletilmiş aksiyon desteği.
"""

import json
import re
import unicodedata
from datetime import datetime, timedelta
from assistant.config import CONVERSATION_MEMORY, DEBUG
from core.loader import global_loader

# ────────────────────────────────────────
# 📝 SİSTEM TALİMATI
# ────────────────────────────────────────

SYSTEM_PROMPT = """
Sen Jarvis adında, macOS üzerinde çalışan bir yapay zeka asistanısın.
Görevin: Kullanıcının Türkçe söylediği doğal dildeki istekleri, bilgisayarın anlayacağı JSON formatına çevirmek.

KRİTİK KURALLAR:
- Asla sohbet etme, açıklama yapma. SADECE JSON çıktısı ver.
- Yanıtın TAMAMI sadece tek bir JSON objesi olmalı, başka hiçbir şey olmamalı.
- JSON objesi mutlaka "action" anahtarı içermelidir.
- Kesinlikle TÜRKÇE yanıt ver.

KULLANILACAK AKSİYONLAR:

1. "open_app" — Uygulama açmak
   Format: {"action": "open_app", "target": "UygulamaAdı"}
   Örnekler: Safari, Spotify, Chrome, Calculator, Terminal, Notes, Finder, VS Code

2. "close_app" — Uygulama kapatmak
   Format: {"action": "close_app", "target": "UygulamaAdı"}

3. "play_music" — Müzik çalmak
   Format: {"action": "play_music", "target": "şarkı/sanatçı adı"}

4. "pause_music" — Müziği durdurmak/devam ettirmek
   Format: {"action": "pause_music"}

5. "next_track" — Sonraki şarkı
   Format: {"action": "next_track"}

6. "previous_track" — Önceki şarkı
   Format: {"action": "previous_track"}

7. "set_volume" — Ses seviyesini ayarlamak (0-100)
   Format: {"action": "set_volume", "value": 50}

8. "set_brightness" — Parlaklığı ayarlamak (0.0-1.0)
   Format: {"action": "set_brightness", "value": 0.7}

9. "get_time" — Saat/tarih sormak
   Format: {"action": "get_time"}

10. "web_search" — İnternette bilgi aramak ve canlı web verisi çekmek
    Format: {"action": "web_search", "target": "arama sorgusu"}
    Not: Bu aksiyon internetten güncel bilgileri, haberleri, fiyatları, tanımları ve araştırma sorularını çeker ve sana okur.
    Kullanıcı bir bilgi sorusu soruyorsa ve bu soru bilgisayar kontrolü değilse web_search kullan.

11. "lock_screen" — Ekranı kilitlemek
    Format: {"action": "lock_screen"}

12. "dark_mode" — Karanlık modu açıp kapatmak
    Format: {"action": "dark_mode"}

13. "screenshot" — Ekran görüntüsü almak
    Format: {"action": "screenshot"}

14. "empty_trash" — Çöp kutusunu boşaltmak
    Format: {"action": "empty_trash"}

15. "create_event" — Takvime etkinlik eklemek
    Format: {"action": "create_event", "target": "etkinlik başlığı", "date": "YYYY-MM-DD", "time": "saat", "duration": süre_dakika, "all_day": true/false}
    date için: "bugün", "yarın", veya "2026-04-15" formatı. Belirtilmezse bugün.
    time için: "14:00" gibi saat formatı. Belirtilmezse şu andan 1 saat sonra.
    duration: dakika cinsinden süre, varsayılan 60.
    Kullanıcı sadece gün söylüyorsa veya "tatil", "bayram", "doğum günü" gibi tüm gün süren bir şey söylüyorsa all_day true yap.

16. "create_note" — Not almak (Apple Notes)
    Format: {"action": "create_note", "target": "not başlığı", "content": "not içeriği"}
    Eğer content belirtilmezse, target'ın kendisi not içeriği olur.

17. "set_timer" — Zamanlayıcı/geri sayım kurmak
    Format: {"action": "set_timer", "value": süre_sayısı, "unit": "birim", "label": "etiket"}
    unit: "saniye", "dakika" veya "saat". Varsayılan "dakika".
    label: opsiyonel açıklama.

18. "set_alarm" — Belirli bir saat için alarm kurmak
    Format: {"action": "set_alarm", "time": "saat:dakika", "label": "etiket"}
    Örnek: {"action": "set_alarm", "time": "07:30", "label": "sabah alarmı"}

19. "general_response" — Teknik olmayan sohbet yanıtları
    Format: {"action": "general_response", "response": "Yanıt metni"}
    Yanıtta Jarvis gibi kibarlık ve saygı kullan. "Efendim" diye hitap et.

20. "confirm_action" — Bekleyen güvenlik onayını kabul etmek
    Format: {"action": "confirm_action"}
    Kullanıcı "onaylıyorum", "evet yap", "tamam devam et" derse bunu kullan.

21. "cancel_action" — Bekleyen güvenlik onayını iptal etmek
    Format: {"action": "cancel_action"}
    Kullanıcı "iptal et", "vazgeç", "hayır" derse bunu kullan.

22. "get_weather" — Hava durumu, yağış, sıcaklık, rüzgar veya nem bilgisi
    Format: {"action": "get_weather", "target": "şehir adı", "detail": "summary"}
    detail: "summary", "precipitation", "temperature", "wind", "humidity"
    Kullanıcı "yağış oranı kaç" gibi takip sorusu sorarsa son hava durumu şehrini kullan.

ÖRNEKLER:

Kullanıcı: "Spotify aç"
{"action": "open_app", "target": "Spotify"}

Kullanıcı: "Metallica çal"
{"action": "play_music", "target": "Metallica"}

Kullanıcı: "Sesi kıs"
{"action": "set_volume", "value": 30}

Kullanıcı: "Saat kaç?"
{"action": "get_time"}

Kullanıcı: "Python öğrenmek istiyorum"
{"action": "web_search", "target": "Python programlama öğrenme"}

Kullanıcı: "OpenAI nedir?"
{"action": "web_search", "target": "OpenAI nedir"}

Kullanıcı: "Bitcoin kaç dolar?"
{"action": "web_search", "target": "Bitcoin kaç dolar güncel"}

Kullanıcı: "Bugünkü teknoloji haberleri neler?"
{"action": "web_search", "target": "bugünkü teknoloji haberleri"}

Kullanıcı: "Nasılsın?"
{"action": "general_response", "response": "İyiyim efendim, size nasıl yardımcı olabilirim?"}

Kullanıcı: "Müziği durdur"
{"action": "pause_music"}

Kullanıcı: "Ekranı kilitle"
{"action": "lock_screen"}

Kullanıcı: "Yarın saat 14'te toplantı var"
{"action": "create_event", "target": "Toplantı", "date": "yarın", "time": "14:00", "duration": 60}

Kullanıcı: "Bugün saat 3'te diş hekimi randevusu ekle"
{"action": "create_event", "target": "Diş Hekimi Randevusu", "date": "bugün", "time": "15:00", "duration": 30}

Kullanıcı: "23 mayısa kurban bayramı tatili yaz"
{"action": "create_event", "target": "Kurban Bayramı Tatili", "date": "2026-05-23", "time": "", "duration": 1440, "all_day": true}

Kullanıcı: "Market listesi: süt, ekmek, yumurta"
{"action": "create_note", "target": "Market Listesi", "content": "Süt, Ekmek, Yumurta"}

Kullanıcı: "Bunu not al: yarın raporu teslim et"
{"action": "create_note", "target": "Hatırlatma", "content": "Yarın raporu teslim et"}

Kullanıcı: "5 dakika zamanlayıcı kur"
{"action": "set_timer", "value": 5, "unit": "dakika", "label": "5 dakika zamanlayıcı"}

Kullanıcı: "30 dakika sonra hatırlat"
{"action": "set_timer", "value": 30, "unit": "dakika", "label": "hatırlatma"}

Kullanıcı: "2 saat sonra alarm kur"
{"action": "set_timer", "value": 2, "unit": "saat", "label": "2 saat alarm"}

Kullanıcı: "Sabah 7'ye alarm kur"
{"action": "set_alarm", "time": "07:00", "label": "Sabah alarmı"}

Kullanıcı: "14:30'a alarm ayarla"
{"action": "set_alarm", "time": "14:30", "label": "Öğleden sonra alarmı"}

Kullanıcı: "Onaylıyorum"
{"action": "confirm_action"}

Kullanıcı: "İptal et"
{"action": "cancel_action"}

Kullanıcı: "Bugün Bitlis'te hava nasıl?"
{"action": "get_weather", "target": "Bitlis", "detail": "summary"}

Kullanıcı: "Yağış oranı kaç?"
{"action": "get_weather", "target": "Bitlis", "detail": "precipitation"}
"""

# ────────────────────────────────────────
# 💾 CONVERSATION MEMORY
# ────────────────────────────────────────

_conversation_history = []
_last_weather_location = ""
_last_web_query = ""

MONTH_NAMES = [
    "ocak", "şubat", "mart", "nisan", "mayıs", "haziran",
    "temmuz", "ağustos", "eylül", "ekim", "kasım", "aralık",
]

TURKISH_PROVINCES = [
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Amasya", "Ankara",
    "Antalya", "Artvin", "Aydın", "Balıkesir", "Bilecik", "Bingöl",
    "Bitlis", "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum",
    "Denizli", "Diyarbakır", "Edirne", "Elazığ", "Erzincan", "Erzurum",
    "Eskişehir", "Gaziantep", "Giresun", "Gümüşhane", "Hakkari", "Hatay",
    "Isparta", "Mersin", "İstanbul", "İzmir", "Kars", "Kastamonu",
    "Kayseri", "Kırklareli", "Kırşehir", "Kocaeli", "Konya", "Kütahya",
    "Malatya", "Manisa", "Kahramanmaraş", "Mardin", "Muğla", "Muş",
    "Nevşehir", "Niğde", "Ordu", "Rize", "Sakarya", "Samsun", "Siirt",
    "Sinop", "Sivas", "Tekirdağ", "Tokat", "Trabzon", "Tunceli",
    "Şanlıurfa", "Uşak", "Van", "Yozgat", "Zonguldak", "Aksaray",
    "Bayburt", "Karaman", "Kırıkkale", "Batman", "Şırnak", "Bartın",
    "Ardahan", "Iğdır", "Yalova", "Karabük", "Kilis", "Osmaniye", "Düzce",
]

_PROVINCE_LOOKUP = {}

KNOWN_APP_TARGETS = {
    "app store", "ayarlar", "calendar", "calculator", "chrome", "discord",
    "excel", "facetime", "finder", "fotograflar", "google chrome", "hesap makinesi",
    "krom", "mail", "mesajlar", "music", "notlar", "notes", "photos", "posta",
    "powerpoint", "safari", "slack", "spotify", "system settings", "takvim",
    "telegram", "terminal", "visual studio code", "vs code", "vscode", "whatsapp",
    "word", "zoom",
}


def _normalize_text(text: str) -> str:
    text = text.lower().replace("ı", "i")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text


MONTHS = {_normalize_text(name): index for index, name in enumerate(MONTH_NAMES, start=1)}


for _province in TURKISH_PROVINCES:
    _PROVINCE_LOOKUP[_normalize_text(_province)] = _province


def _extract_weather_location(text: str) -> str:
    normalized = _normalize_text(text)
    for key, province in _PROVINCE_LOOKUP.items():
        if re.search(rf"\b{re.escape(key)}(?:'?(?:te|ta|de|da|e|a|in|un|nin|nın|nun|nün))?\b", normalized):
            return province
    return ""


def _weather_detail(text: str) -> str:
    normalized = _normalize_text(text)
    if any(word in normalized for word in ["yagis", "yagmur", "kar", "oran"]):
        return "precipitation"
    if any(word in normalized for word in ["sicaklik", "kac derece", "derece"]):
        return "temperature"
    if "ruzgar" in normalized:
        return "wind"
    if "nem" in normalized:
        return "humidity"
    return "summary"


def _extract_time(text: str) -> tuple[str, tuple[int, int] | None]:
    """Extract Turkish time expressions and return cleaned text + HH:MM."""
    patterns = [
        r"\bsaat\s+(\d{1,2})(?:[:.](\d{2}))?\b",
        r"\b(\d{1,2})[:.](\d{2})\b",
        r"\b(\d{1,2})(?:'?(?:te|ta|de|da))\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        hour = int(match.group(1))
        minute = int(match.group(2) or 0) if len(match.groups()) > 1 else 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            cleaned = (text[:match.start()] + " " + text[match.end():]).strip()
            return cleaned, (hour, minute)
    return text, None


def _format_date(year: int, month: int, day: int) -> str:
    return f"{year:04d}-{month:02d}-{day:02d}"


def _extract_calendar_date(text: str) -> tuple[str, str | None]:
    """Extract common Turkish calendar dates and return cleaned text + YYYY-MM-DD."""
    now = datetime.now()
    normalized = _normalize_text(text)

    relative_patterns = [
        (r"\bbugun\b", now),
        (r"\byarin\b", now + timedelta(days=1)),
        (r"\bobur gun\b|\böbur gün\b|\bsonraki gun\b", now + timedelta(days=2)),
    ]
    for pattern, date_value in relative_patterns:
        match = re.search(pattern, normalized)
        if match:
            cleaned = (text[:match.start()] + " " + text[match.end():]).strip()
            return cleaned, date_value.strftime("%Y-%m-%d")

    numeric = re.search(r"\b(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?\b", text)
    if numeric:
        day = int(numeric.group(1))
        month = int(numeric.group(2))
        year = int(numeric.group(3)) if numeric.group(3) else now.year
        if year < 100:
            year += 2000
        try:
            candidate = datetime(year, month, day)
            if not numeric.group(3) and candidate.date() < now.date():
                candidate = candidate.replace(year=year + 1)
            cleaned = (text[:numeric.start()] + " " + text[numeric.end():]).strip()
            return cleaned, candidate.strftime("%Y-%m-%d")
        except ValueError:
            return text, None

    month_names = "|".join(sorted(MONTHS, key=len, reverse=True))
    named = re.search(
        rf"\b(\d{{1,2}})\s*({month_names})(?:'?(?:a|e|ta|te|da|de|nda|nde|ina|ine))?(?:\s+(\d{{4}}))?\b",
        normalized,
        flags=re.IGNORECASE,
    )
    if named:
        day = int(named.group(1))
        month = MONTHS[named.group(2)]
        year = int(named.group(3)) if named.group(3) else now.year
        try:
            candidate = datetime(year, month, day)
            if not named.group(3) and candidate.date() < now.date():
                candidate = candidate.replace(year=year + 1)
            cleaned = (text[:named.start()] + " " + text[named.end():]).strip()
            return cleaned, candidate.strftime("%Y-%m-%d")
        except ValueError:
            return text, None

    return text, None


def _title_case_tr(text: str) -> str:
    words = [word for word in re.split(r"\s+", text.strip()) if word]
    return " ".join(word[:1].upper() + word[1:] for word in words)


def _clean_app_target(target: str) -> str:
    target = _normalize_text(target)
    target = re.sub(r"\b(jarvis|lutfen|uygulamasini|uygulamasini|uygulamayi|uygulama|programi|program)\b", " ", target)
    target = re.sub(r"\s+", " ", target).strip(" ,.-'")
    if target in KNOWN_APP_TARGETS:
        return target

    suffixes = ["'yi", "'yi", "'yı", "'yu", "'yü", "'i", "'ı", "'u", "'ü", "yi", "yı", "yu", "yü", "ni", "nı", "nu", "nü", "i", "ı", "u", "ü"]
    for suffix in suffixes:
        if target.endswith(suffix):
            candidate = target[: -len(suffix)].strip(" ,.-'")
            if candidate in KNOWN_APP_TARGETS:
                return candidate

    return target


def _app_command(user_input: str) -> dict | None:
    """Route simple app open/close commands without waiting for the LLM."""
    normalized = _normalize_text(user_input).strip()
    if re.search(r"\b(ses|sesi|volume|parlaklik|isik|ışık)\b", normalized):
        return None

    patterns = [
        (r"^(?P<target>.+?)\s+(?:ac|aç|baslat|başlat)$", "open_app"),
        (r"^(?:ac|aç|baslat|başlat)\s+(?P<target>.+)$", "open_app"),
        (r"^(?P<target>.+?)\s+(?:kapat|cik|çık|sonlandir|sonlandır)$", "close_app"),
        (r"^(?:kapat|cik|çık|sonlandir|sonlandır)\s+(?P<target>.+)$", "close_app"),
    ]
    for pattern, action in patterns:
        match = re.search(pattern, normalized)
        if not match:
            continue
        target = _clean_app_target(match.group("target"))
        if target:
            return {"action": action, "target": target}
    return None


def _calendar_command(user_input: str) -> dict | None:
    normalized = _normalize_text(user_input)
    calendar_verbs = [
        "takvime", "takvimime", "ajandaya", "yaz", "ekle", "isaretle",
        "işaretle", "not dus", "not düş", "kaydet"
    ]
    if not any(verb in normalized for verb in calendar_verbs):
        return None

    text_without_time, parsed_time = _extract_time(user_input)
    text_without_date, parsed_date = _extract_calendar_date(text_without_time)
    if not parsed_date:
        return None

    title = text_without_date
    filler_patterns = [
        r"\btakvime\b", r"\btakvimime\b", r"\bajandaya\b",
        r"\byaz\b", r"\bekle\b", r"\bişaretle\b", r"\bisaretle\b",
        r"\bnot\s+düş\b", r"\bnot\s+dus\b", r"\bkaydet\b",
    ]
    for pattern in filler_patterns:
        title = re.sub(pattern, " ", title, flags=re.IGNORECASE)
    title = title.strip(" ,.-")
    title = re.sub(r"\s+", " ", title).strip(" ,.-")
    if not title:
        title = "Etkinlik"

    all_day = parsed_time is None or any(
        token in normalized for token in ["tatil", "bayram", "dogum gunu", "doğum günü"]
    )
    return {
        "action": "create_event",
        "target": _title_case_tr(title),
        "date": parsed_date,
        "time": f"{parsed_time[0]:02d}:{parsed_time[1]:02d}" if parsed_time else "",
        "duration": 1440 if all_day else 60,
        "all_day": all_day,
    }


def _is_local_command(normalized: str) -> bool:
    """Avoid routing device-control commands to web search."""
    local_patterns = [
        r"\b(ac|aç|kapat|cal|çal|duraklat|durdur|kilitle)\b",
        r"\bspotify|telegram|chrome|krom|safari|terminal|finder|notlar|takvim\b",
        r"\balarm\b|\bzamanlayici\b|\bzamanlayıcı\b|\bhatirlat\b|\bhatırlat\b",
        r"\bsaat kac\b|\bsaat kaç\b|\btarih\b",
        r"\bsesi\b|\bses seviyesi\b|\bparlaklik\b|\bparlaklık\b",
        r"\bekran goruntusu\b|\bekran görüntüsü\b|\bcop kutusu\b|\bçöp kutusu\b",
        r"\bnasilsin\b|\bnasılsın\b|\bmerhaba\b|\bselam\b",
    ]
    return any(re.search(pattern, normalized) for pattern in local_patterns)


def _looks_like_web_question(normalized: str) -> bool:
    """Detect questions that need external/general information."""
    if _is_local_command(normalized):
        return False

    explicit_web = [
        "internette", "internet", "webde", "web'de", "ara", "arat",
        "arastir", "araştir", "araştır", "google", "haber", "guncel", "güncel",
        "fiyat", "dolar", "euro", "borsa", "kripto", "bitcoin",
    ]
    if any(token in normalized for token in explicit_web):
        return True

    question_patterns = [
        r"\b(nedir|ne demek|kimdir|nerede|ne zaman|neden|nasil|nasıl)\b",
        r"\b(kac|kaç) (tl|lira|dolar|euro|para|yasinda|yaşında|metre|km|gb|mb)\b",
        r"\b(en iyi|karsilastir|karşılaştır|oner|öner)\b",
    ]
    return any(re.search(pattern, normalized) for pattern in question_patterns)


def _clean_web_query(user_input: str) -> str:
    """Remove command filler while keeping the user's actual information need."""
    query = user_input.strip()
    replacements = [
        r"\binternette\b", r"\bwebde\b", r"\bweb'de\b", r"\bgoogle'?da\b",
        r"\bara\b", r"\barat\b", r"\baraştır\b", r"\barastir\b",
        r"\bbana\b", r"\bsöyle\b", r"\bsoyle\b", r"\blütfen\b", r"\blutfen\b",
    ]
    for pattern in replacements:
        query = re.sub(pattern, " ", query, flags=re.IGNORECASE)
    query = " ".join(query.split())
    return query or user_input.strip()


def _rule_based_command(user_input: str) -> dict | None:
    """Fast deterministic routing for common commands where LLM mistakes are costly."""
    global _last_weather_location, _last_web_query

    normalized = _normalize_text(user_input)

    calendar_command = _calendar_command(user_input)
    if calendar_command:
        return calendar_command

    app_command = _app_command(user_input)
    if app_command:
        return app_command

    weather_keywords = [
        "hava", "sicaklik", "derece", "yagis", "yagmur", "kar", "ruzgar", "nem"
    ]
    if any(keyword in normalized for keyword in weather_keywords):
        location = _extract_weather_location(user_input) or _last_weather_location
        if location:
            _last_weather_location = location
            return {
                "action": "get_weather",
                "target": location,
                "detail": _weather_detail(user_input),
            }

    if _looks_like_web_question(normalized):
        query = _clean_web_query(user_input)
        _last_web_query = query
        return {
            "action": "web_search",
            "target": query,
        }

    return None


def _add_to_history(role: str, content: str):
    """Konuşma geçmişine mesaj ekler."""
    _conversation_history.append({"role": role, "content": content})
    # Bellek sınırını aşarsa eski mesajları sil
    while len(_conversation_history) > CONVERSATION_MEMORY * 2:
        _conversation_history.pop(0)


def clear_history():
    """Konuşma geçmişini temizler."""
    global _last_weather_location, _last_web_query
    _conversation_history.clear()
    _last_weather_location = ""
    _last_web_query = ""


# ────────────────────────────────────────
# 🔍 JSON ÇIKARMA (Robust)
# ────────────────────────────────────────

def _extract_json(text: str) -> dict | None:
    """
    Model çıktısından JSON objesini çıkarır.
    Model bazen JSON'dan önce/sonra text ekleyebilir, 
    bu fonksiyon bunu tolere eder.
    """
    # 1. Direkt parse dene
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    
    # 2. Code block içinden çıkar (```json ... ```)
    code_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1))
        except json.JSONDecodeError:
            pass
    
    # 3. İlk { ile son } arasını bul
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    
    return None


# ────────────────────────────────────────
# 🧠 ANA İŞLEM FONKSİYONU
# ────────────────────────────────────────

def process_command(user_input: str) -> dict | None:
    """
    Kullanıcı metnini LLM'e gönderir, JSON komut döndürür.
    
    Args:
        user_input: Kullanıcının söylediği metin
        
    Returns:
        JSON dict (aksiyon bilgisi) veya None (hata durumunda)
    """
    if not user_input or not user_input.strip():
        return None
    
    if DEBUG:
        print(f"\n🧠 Beyin işliyor: \"{user_input}\"")

    quick_command = _rule_based_command(user_input)
    if quick_command:
        if DEBUG:
            print(f"⚡ Kural tabanlı komut: {json.dumps(quick_command, ensure_ascii=False)}")
        _add_to_history("user", user_input)
        _add_to_history("assistant", json.dumps(quick_command, ensure_ascii=False))
        return quick_command
    
    # Mesaj listesini oluştur
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Conversation history ekle
    messages.extend(_conversation_history)
    
    # Yeni kullanıcı mesajını ekle
    messages.append({"role": "user", "content": user_input})
    
    try:
        # LazyLoader üzerinden ollama'yı yükle
        ollama = global_loader.get("llm")
        if not ollama:
            error_detail = global_loader.get_last_error("llm") or "Ollama servisi başlatılamadı."
            if DEBUG:
                print(f"⚠️  LLM (Ollama) yüklenemedi: {error_detail}")
            return {
                "action": "general_response",
                "response": f"Yerel zeka modeli şu anda hazır değil efendim. {error_detail}"
            }

        try:
            from assistant.config import OLLAMA_NUM_CTX, OLLAMA_TEMPERATURE
        except ImportError:
            OLLAMA_NUM_CTX = 4096
            OLLAMA_TEMPERATURE = 0.0

        chat_kwargs = {
            "model": global_loader.get_llm_model(),
            "messages": messages,
            "format": "json",
            "options": {
                "temperature": OLLAMA_TEMPERATURE,
                "num_ctx": OLLAMA_NUM_CTX,
            },
        }

        # Qwen3 gibi reasoning destekli modellerde komut JSON'u için hızlı/temiz mod.
        if str(global_loader.get_llm_model()).startswith("qwen3"):
            chat_kwargs["think"] = False

        # Ollama'ya gönder
        try:
            response = ollama.chat(**chat_kwargs)
        except TypeError:
            chat_kwargs.pop("think", None)
            response = ollama.chat(**chat_kwargs)
        model_output = response["message"]["content"]
        
        if DEBUG:
            print(f"📤 Model çıktısı: {model_output}")
        
        # JSON çıkar
        command = _extract_json(model_output)
        
        if command and "action" in command:
            # Başarılı — geçmişe ekle
            _add_to_history("user", user_input)
            _add_to_history("assistant", model_output)
            
            if DEBUG:
                print(f"✅ Komut: {json.dumps(command, ensure_ascii=False)}")
            
            return command
        else:
            if DEBUG:
                print("⚠️  Model geçerli bir JSON komutu üretmedi. Ham metni kullanıyoruz.")
            
            # Son çare: general_response olarak dön (Modelin ham metnini kurtar)
            clean_output = model_output.strip()
            # Bazen başında/sonunda gereksiz markdown kalabiliyor
            clean_output = re.sub(r'^```json\s*|```\s*$', '', clean_output).strip()
            
            _add_to_history("user", user_input)
            _add_to_history("assistant", clean_output)
            
            return {
                "action": "general_response",
                "response": clean_output if clean_output else "Anlayamadım efendim, tekrar söyleyebilir misiniz?"
            }
            
    except Exception as e:
        print(f"❌ LLM Hatası: {e}")
        if "connection" in str(e).lower() or "refused" in str(e).lower():
            print("💡 Ollama çalışıyor mu? Kontrol edin: ollama serve")
        return None


# --- TEST ---
if __name__ == "__main__":
    print("🧠 Brain modülü test ediliyor...")
    
    test_commands = [
        "Spotify aç",
        "Metallica çal",
        "Saat kaç?",
        "Nasılsın?",
        "Sesi %30'a ayarla",
        "Ekranı kilitle",
    ]
    
    for cmd in test_commands:
        result = process_command(cmd)
        print(f"  Girdi: {cmd}")
        print(f"  Çıktı: {result}")
        print()

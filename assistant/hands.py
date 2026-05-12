"""
🖐️ JARVIS — Eller Modülü (macOS Sistem Otomasyonu)
AppleScript ve subprocess ile macOS kontrolü.
"""

import subprocess
import webbrowser
import urllib.parse
import threading
import time
import os
import difflib
import json
import re
import unicodedata
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from assistant.config import DEBUG
from plugins.base import (
    ActionContext,
    ActionRegistry,
    CommandValidationError,
    FunctionActionPlugin,
)


# ────────────────────────────────────────
# 🔧 AppleScript Yardımcı Fonksiyon
# ────────────────────────────────────────

def run_applescript(script: str) -> str:
    """AppleScript komutunu çalıştırır ve sonucu döndürür."""
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            error = result.stderr.strip() or "AppleScript komutu başarısız oldu."
            if DEBUG:
                print(f"⚠️  AppleScript hata: {error}")
            return f"Hata: {error}"
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "Komut zaman aşımına uğradı."
    except Exception as e:
        return f"Hata: {e}"


def applescript_quote(value: object) -> str:
    """Return a safely quoted AppleScript string literal."""
    text = str(value)
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


APPLE_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def applescript_date_var(var_name: str, value: datetime) -> str:
    """Build an AppleScript date object without locale-dependent date strings."""
    month_name = APPLE_MONTHS[value.month - 1]
    return f'''
    set {var_name} to current date
    set year of {var_name} to {value.year}
    set month of {var_name} to {month_name}
    set day of {var_name} to {value.day}
    set time of {var_name} to {(value.hour * 3600) + (value.minute * 60) + value.second}
    '''


# ────────────────────────────────────────
# 📱 Uygulama Kontrolü
# ────────────────────────────────────────

APP_ALIASES = {
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "krom": "Google Chrome",
    "safari": "Safari",
    "spotify": "Spotify",
    "terminal": "Terminal",
    "terminale": "Terminal",
    "finder": "Finder",
    "bulucu": "Finder",
    "notes": "Notes",
    "notlar": "Notes",
    "note": "Notes",
    "calendar": "Calendar",
    "takvim": "Calendar",
    "calculator": "Calculator",
    "hesap makinesi": "Calculator",
    "settings": "System Settings",
    "ayarlar": "System Settings",
    "sistem ayarlari": "System Settings",
    "sistem ayarları": "System Settings",
    "mail": "Mail",
    "posta": "Mail",
    "visual studio code": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "code": "Visual Studio Code",
}

APP_DISPLAY_NAMES = {
    "Calendar": "Takvim",
    "Notes": "Notlar",
    "Calculator": "Hesap Makinesi",
    "System Settings": "Sistem Ayarları",
    "Finder": "Finder",
    "Google Chrome": "Google Chrome",
    "Visual Studio Code": "Visual Studio Code",
    "Telegram": "Telegram",
    "Spotify": "Spotify",
    "Safari": "Safari",
    "Terminal": "Terminal",
}


def _normalize_app_name(name: str) -> str:
    """Normalize app names for fuzzy matching."""
    normalized = unicodedata.normalize("NFKD", name.strip().lower())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(normalized.replace("-", " ").replace("_", " ").split())


@lru_cache(maxsize=1)
def _installed_apps() -> dict[str, str]:
    """Return normalized app name -> display app name for common macOS app paths."""
    app_dirs = [
        Path("/Applications"),
        Path("/System/Applications"),
        Path("/System/Applications/Utilities"),
        Path.home() / "Applications",
    ]
    apps: dict[str, str] = {}

    for app_dir in app_dirs:
        if not app_dir.exists():
            continue
        for app_path in app_dir.rglob("*.app"):
            display_name = app_path.stem
            apps.setdefault(_normalize_app_name(display_name), display_name)

    for alias, canonical in APP_ALIASES.items():
        apps.setdefault(_normalize_app_name(alias), canonical)
        apps.setdefault(_normalize_app_name(canonical), canonical)

    return apps


def resolve_app_name(app_name: str, min_score: float = 0.70) -> tuple[str, float]:
    """
    Resolve a spoken app name to a macOS app name.

    Returns (resolved_name, score). If no confident match exists, the original
    name is returned with score 0.0 so macOS can still try to open it.
    """
    if not app_name:
        return app_name, 0.0

    normalized = _normalize_app_name(app_name)
    alias = APP_ALIASES.get(normalized)
    if alias:
        return alias, 1.0

    apps = _installed_apps()
    if normalized in apps:
        return apps[normalized], 1.0

    candidates = difflib.get_close_matches(normalized, apps.keys(), n=1, cutoff=min_score)
    if not candidates:
        return app_name, 0.0

    match = candidates[0]
    score = difflib.SequenceMatcher(None, normalized, match).ratio()
    return apps[match], score


def display_app_name(app_name: str) -> str:
    """User-facing app name."""
    return APP_DISPLAY_NAMES.get(app_name, app_name)


def open_app(app_name: str) -> str:
    """Uygulamayı açar."""
    resolved_name, score = resolve_app_name(app_name)
    display_name = display_app_name(resolved_name)
    try:
        subprocess.run(["open", "-a", resolved_name], check=True, capture_output=True)
        if DEBUG:
            print(f"✅ {resolved_name} açıldı. (eşleşme: {score:.2f})")
        return f"{display_name} açıldı efendim."
    except subprocess.CalledProcessError:
        # Tam adla bulunamazsa AppleScript dene
        result = run_applescript(f"tell application {applescript_quote(resolved_name)} to activate")
        if "error" in result.lower():
            return f"{app_name} uygulamasını bulamadım efendim."
        return f"{display_name} açıldı efendim."


def close_app(app_name: str) -> str:
    """Uygulamayı kapatır."""
    resolved_name, score = resolve_app_name(app_name)
    display_name = display_app_name(resolved_name)
    script = f"tell application {applescript_quote(resolved_name)} to quit"
    run_applescript(script)
    if DEBUG:
        print(f"✅ {resolved_name} kapatıldı. (eşleşme: {score:.2f})")
    return f"{display_name} kapatıldı efendim."


# ────────────────────────────────────────
# 🎵 Müzik Kontrolü (Spotify + Apple Music)
# ────────────────────────────────────────

def play_music(query: str) -> str:
    """Spotify'da müzik arar ve çalar."""
    try:
        # Önce Spotify'ı aç
        subprocess.run(["open", "-a", "Spotify"], capture_output=True)
        
        # Spotify URI ile arama
        search_url = f"spotify:search:{urllib.parse.quote(query)}"
        subprocess.run(["open", search_url], capture_output=True)
        
        if DEBUG:
            print(f"🎵 Spotify'da aranıyor: {query}")
        
        return f"{query} Spotify'da aranıyor efendim."
    except Exception as e:
        # Fallback: web tarayıcıda Spotify Web Player
        url = f"https://open.spotify.com/search/{urllib.parse.quote(query)}"
        webbrowser.open(url)
        return f"{query} için Spotify web'de arama açıldı."


def pause_music() -> str:
    """Müziği duraklatır/devam ettirir (Spotify)."""
    script = '''
    tell application "Spotify"
        playpause
    end tell
    '''
    run_applescript(script)
    return "Müzik duraklatıldı efendim."


def next_track() -> str:
    """Sonraki şarkıya geçer."""
    script = '''
    tell application "Spotify"
        next track
    end tell
    '''
    run_applescript(script)
    return "Sonraki şarkıya geçildi efendim."


def previous_track() -> str:
    """Önceki şarkıya geçer."""
    script = '''
    tell application "Spotify"
        previous track
    end tell
    '''
    run_applescript(script)
    return "Önceki şarkıya dönüldü efendim."


# ────────────────────────────────────────
# 🔊 Ses Kontrolü
# ────────────────────────────────────────

def set_volume(level: int) -> str:
    """Sistem ses seviyesini ayarlar (0-100)."""
    level = max(0, min(100, level))  # 0-100 arası sınırla
    # macOS ses seviyesi 0-7 arası, 100'lük ölçeği çeviriyoruz
    mac_level = int(level * 7 / 100)
    script = f'set volume output volume {level}'
    run_applescript(script)
    return f"Ses seviyesi %{level} olarak ayarlandı efendim."


# ────────────────────────────────────────
# 💡 Parlaklık Kontrolü
# ────────────────────────────────────────

def set_brightness(level: float) -> str:
    """Ekran parlaklığını ayarlar (0.0-1.0)."""
    level = max(0.0, min(1.0, level))
    try:
        # brightness komutu yüklüyse kullan
        subprocess.run(["brightness", str(level)], check=True, capture_output=True)
        return f"Parlaklık %{int(level * 100)} olarak ayarlandı efendim."
    except FileNotFoundError:
        # AppleScript ile dene
        percent = int(level * 100)
        return f"Parlaklık ayarı için 'brightness' komutu gerekiyor. Sistem Ayarları'ndan ayarlayabilirsiniz efendim."


# ────────────────────────────────────────
# 🕐 Zaman & Bilgi
# ────────────────────────────────────────

def get_current_time() -> str:
    """Mevcut saati döndürür."""
    now = datetime.now()
    time_str = now.strftime("%H:%M")
    months = [
        "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
        "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
    ]
    days = [
        "Pazartesi", "Salı", "Çarşamba", "Perşembe",
        "Cuma", "Cumartesi", "Pazar",
    ]
    date_str = f"{now.day:02d} {months[now.month - 1]} {now.year}, {days[now.weekday()]}"
    return f"Saat {time_str}, tarih {date_str} efendim."


def _weather_description(value: str) -> str:
    """Translate common wttr.in weather descriptions to natural Turkish."""
    text = (value or "").lower()
    mapping = [
        ("clear", "açık"),
        ("sunny", "güneşli"),
        ("partly cloudy", "parçalı bulutlu"),
        ("cloudy", "bulutlu"),
        ("overcast", "kapalı"),
        ("mist", "puslu"),
        ("fog", "sisli"),
        ("rain", "yağmurlu"),
        ("drizzle", "çiseleyen yağmurlu"),
        ("snow", "karlı"),
        ("sleet", "karla karışık yağmurlu"),
        ("thunder", "gök gürültülü"),
    ]
    for needle, translated in mapping:
        if needle in text:
            return translated
    return value or "bilgi yok"


def _chance_of_precipitation(weather_day: dict) -> str:
    chances = []
    for hour in weather_day.get("hourly", []):
        chance = hour.get("chanceofrain") or hour.get("chanceofsnow")
        if chance not in ("", None):
            try:
                chances.append(int(chance))
            except ValueError:
                pass
    if not chances:
        return "bilgi yok"
    return f"%{max(chances)}"


def _fetch_json(url: str, timeout: int = 8) -> dict:
    """Fetch JSON with curl to avoid Python TLS/keychain edge cases on macOS."""
    result = subprocess.run(
        ["curl", "-fsSL", "--max-time", str(timeout), url],
        capture_output=True,
        text=True,
        timeout=timeout + 2,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "curl ile veri alınamadı")
    return json.loads(result.stdout)


def _clean_llm_answer(answer: str) -> str:
    """Clean common formatting artifacts from local LLM web summaries."""
    answer = answer.strip()
    answer = answer.replace("```json", "").replace("```", "").strip()
    answer = re.sub(r"^(cevap|yanıt)\s*:\s*", "", answer, flags=re.IGNORECASE)
    answer = re.sub(r"\s+", " ", answer)
    return answer


def get_weather(location: str, detail: str = "summary") -> str:
    """
    Current weather from wttr.in JSON.

    This is intentionally deterministic: weather questions should not depend
    on a general LLM summary, because users expect numbers.
    """
    location = location.strip()
    if not location:
        return "Hangi şehir için hava durumunu istediğinizi anlayamadım."

    try:
        encoded = urllib.parse.quote(location)
        url = f"https://wttr.in/{encoded}?format=j1&lang=tr"
        payload = _fetch_json(url)

        current = (payload.get("current_condition") or [{}])[0]
        today = (payload.get("weather") or [{}])[0]

        temp = current.get("temp_C", "?")
        feels = current.get("FeelsLikeC", "?")
        humidity = current.get("humidity", "?")
        wind = current.get("windspeedKmph", "?")
        precip_mm = current.get("precipMM", "0")
        description = _weather_description(
            ((current.get("weatherDesc") or [{}])[0]).get("value", "")
        )
        min_temp = today.get("mintempC", "?")
        max_temp = today.get("maxtempC", "?")
        rain_chance = _chance_of_precipitation(today)

        if detail == "precipitation":
            return (
                f"{location} için bugün yağış ihtimali {rain_chance}. "
                f"Şu an ölçülen yağış {precip_mm} mm görünüyor."
            )
        if detail == "temperature":
            return (
                f"{location} şu an {temp} derece; hissedilen {feels} derece. "
                f"Bugün en düşük {min_temp}, en yüksek {max_temp} derece bekleniyor."
            )
        if detail == "wind":
            return f"{location} için rüzgar hızı şu an yaklaşık {wind} km/s."
        if detail == "humidity":
            return f"{location} için nem oranı şu an %{humidity}."

        return (
            f"{location} için hava şu an {description}, {temp} derece "
            f"(hissedilen {feels}). Bugün {min_temp}-{max_temp} derece aralığı "
            f"ve yağış ihtimali {rain_chance} görünüyor."
        )

    except Exception as e:
        if DEBUG:
            print(f"⚠️ Hava durumu hatası: {e}")
        return web_search(f"{location} bugün hava durumu yağış ihtimali sıcaklık")


# ────────────────────────────────────────
# 🌐 Web Arama
# ────────────────────────────────────────

def web_search(query: str) -> str:
    """İnternette arama yapar ve LLM ile özetler."""
    import urllib.parse
    import webbrowser
    
    query = " ".join(str(query or "").split())
    if not query:
        return "Ne araştırmamı istediğinizi anlayamadım."

    if DEBUG:
        print(f"🌐 İnternette aranıyor: {query}")
        
    try:
        from core.loader import global_loader

        ddgs_module = global_loader.get("web_search")
        if ddgs_module is None:
            raise ImportError("ddgs modülü yüklenemedi")
        DDGS = ddgs_module.DDGS
        
        # 1. DDG üzerinden arama yap
        with DDGS() as ddgs:
            try:
                results = [r for r in ddgs.text(
                    query,
                    region="tr-tr",
                    safesearch="moderate",
                    max_results=6,
                )]
            except TypeError:
                results = [r for r in ddgs.text(query, max_results=6)]
            
        if not results:
            return f"'{query}' için internette herhangi bir sonuç bulamadım efendim."
            
        # 2. Sonuçları metin olarak birleştir
        try:
            from assistant.config import WEB_SEARCH_USE_LLM_SUMMARY
        except ImportError:
            WEB_SEARCH_USE_LLM_SUMMARY = False

        if not WEB_SEARCH_USE_LLM_SUMMARY:
            return _fallback_search_answer(query, results)

        context_lines = []
        for index, result in enumerate(results, start=1):
            title = result.get("title", "Başlıksız")
            body = result.get("body", "")
            href = result.get("href") or result.get("url") or ""
            context_lines.append(f"{index}. Başlık: {title}\n   Özet: {body}\n   Kaynak: {href}")
        context = "\n".join(context_lines)
        
        # 3. LLM'e özetlet
        ollama = global_loader.get("llm")
        if ollama:
            try:
                from assistant.config import OLLAMA_KEEP_ALIVE
            except ImportError:
                OLLAMA_KEEP_ALIVE = "30m"

            today = datetime.now().strftime("%Y-%m-%d")
            prompt = (
                "Sen Jarvis'sin. Aşağıdaki web arama sonuçlarını kullanıcıya Türkçe, kısa ve anlaşılır biçimde özetle.\n"
                "Kurallar:\n"
                "- Asla JSON üretme.\n"
                "- Snippet metinlerini aynen kopyalama; bozuk çeviri gibi duran ifadeleri düzelt.\n"
                "- Emin olmadığın sayısal değerleri kesinmiş gibi söyleme.\n"
                "- Sonuçlar soruyu doğrudan cevaplamıyorsa bunu açıkça söyle.\n"
                "- Güncel bilgi sorularında tarihin önemli olduğunu unutma.\n"
                "- Cevabı 1-4 kısa cümleyle ver.\n\n"
                f"Bugünün tarihi: {today}\n"
                f"Kullanıcının sorusu: {query}\n\n"
                f"Arama Sonuçları:\n{context}"
            )
            
            response = ollama.chat(
                model=global_loader.get_llm_model(),
                messages=[{"role": "user", "content": prompt}],
                keep_alive=OLLAMA_KEEP_ALIVE,
                options={"temperature": 0.1, "top_p": 0.8},
            )
            
            answer = _clean_llm_answer(response["message"]["content"])
            if answer:
                return answer
            return _fallback_search_answer(query, results)
        else:
            return _fallback_search_answer(query, results)
            
    except Exception as e:
        if DEBUG:
            print(f"⚠️ Web arama hatası: {e}")
        # Hata durumunda (örn. rate limit, bağlantı sorunu) eski usul tarayıcıyı aç
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        webbrowser.open(url)
        return f"İnternet bağlantısında bir sorun yaşadım, bu yüzden arama sonuçlarını tarayıcınızda açtım efendim."


def _fallback_search_answer(query: str, results: list[dict]) -> str:
    """Readable fallback when the LLM is unavailable."""
    first = results[0]
    title = first.get("title", "İlk sonuç")
    body = first.get("body", "")
    if body:
        return f"{query} için bulduğum en ilgili sonuç: {title}. {body}"
    return f"{query} için en ilgili sonuç: {title}."


# ────────────────────────────────────────
# 🖥️ Sistem Komutları
# ────────────────────────────────────────

def lock_screen() -> str:
    """Ekranı kilitler."""
    script = 'tell application "System Events" to keystroke "q" using {control down, command down}'
    run_applescript(script)
    return "Ekran kilitleniyor efendim."


def empty_trash() -> str:
    """Çöp kutusunu boşaltır."""
    script = '''
    tell application "Finder"
        empty the trash
    end tell
    '''
    run_applescript(script)
    return "Çöp kutusu boşaltıldı efendim."


def toggle_dark_mode() -> str:
    """Karanlık mod açar/kapatır."""
    script = '''
    tell application "System Events"
        tell appearance preferences
            set dark mode to not dark mode
        end tell
    end tell
    '''
    run_applescript(script)
    return "Karanlık mod değiştirildi efendim."


def screenshot() -> str:
    """Ekran görüntüsü alır."""
    subprocess.run(["screencapture", "-x", f"screenshot_{datetime.now().strftime('%H%M%S')}.png"])
    return "Ekran görüntüsü alındı efendim."


# ────────────────────────────────────────
# 📅 TAKVİM — macOS Calendar Entegrasyonu
# ────────────────────────────────────────

def create_calendar_event(
    title: str,
    date: str = "",
    time_str: str = "",
    duration: int = 60,
    all_day: bool = False,
) -> str:
    """
    macOS Takvim uygulamasında etkinlik oluşturur.
    
    Args:
        title: Etkinlik başlığı
        date: Tarih (örn: "2026-04-15" veya "yarın")
        time_str: Saat (örn: "14:00")
        duration: Süre (dakika)
        all_day: Saat yoksa günü işaretleyen tüm gün etkinliği
    """
    try:
        # Tarih/saat hesaplama
        now = datetime.now()
        
        if not date or date.lower() in ["bugün", "today"]:
            event_date = now
        elif date.lower() in ["yarın", "yarin", "tomorrow"]:
            event_date = now + timedelta(days=1)
        else:
            try:
                event_date = datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                try:
                    event_date = datetime.strptime(date.replace(".", "/"), "%d/%m/%Y")
                except ValueError:
                    event_date = now
        
        # Saat ayarla
        if all_day:
            event_date = event_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_str:
            try:
                parts = time_str.replace(".", ":").split(":")
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
                event_date = event_date.replace(hour=hour, minute=minute, second=0)
            except (ValueError, IndexError):
                event_date = event_date.replace(hour=now.hour + 1, minute=0, second=0)
        else:
            event_date = event_date.replace(hour=now.hour + 1, minute=0, second=0)
        
        # Bitiş zamanı
        if all_day:
            end_date = event_date + timedelta(days=1)
        else:
            duration = duration if duration > 0 else 60
            end_date = event_date + timedelta(minutes=duration)

        all_day_prop = "true" if all_day else "false"
        
        script = f'''
        {applescript_date_var("startDate", event_date)}
        {applescript_date_var("endDate", end_date)}
        tell application "Calendar"
            set targetCalendar to first calendar
            tell targetCalendar
                set newEvent to make new event at end of events with properties {{summary:{applescript_quote(title)}, start date:startDate, end date:endDate, allday event:{all_day_prop}}}
            end tell
            activate
            show newEvent
        end tell
        '''
        
        result = run_applescript(script)
        if result.startswith("Hata:"):
            return f"Takvim etkinliği oluşturulamadı efendim: {result[5:].strip()}"
        
        display_time = event_date.strftime("%d/%m/%Y") if all_day else event_date.strftime("%d/%m/%Y %H:%M")
        if DEBUG:
            print(f"📅 Takvim etkinliği oluşturuldu: {title} — {display_time}")
        
        if all_day:
            return f"'{title}' etkinliği {display_time} gününe tüm gün olarak eklendi efendim."
        return f"'{title}' etkinliği {display_time} için takvime eklendi efendim."
        
    except Exception as e:
        if DEBUG:
            print(f"❌ Takvim hatası: {e}")
        return f"Takvim etkinliği oluşturulurken bir hata oluştu efendim: {e}"


# ────────────────────────────────────────
# 📝 NOT ALMA — Apple Notes Entegrasyonu
# ────────────────────────────────────────

def create_note(title: str = "", content: str = "") -> str:
    """
    Apple Notes uygulamasında not oluşturur.
    
    Args:
        title: Not başlığı
        content: Not içeriği
    """
    try:
        now = datetime.now()
        
        if not title:
            title = f"Jarvis Notu — {now.strftime('%d/%m/%Y %H:%M')}"
        
        if not content:
            content = title
        
        script = f'''
        tell application "Notes"
            tell account "iCloud"
                make new note at folder "Notes" with properties {{name:{applescript_quote(title)}, body:{applescript_quote(content)}}}
            end tell
            activate
        end tell
        '''
        
        run_applescript(script)
        
        if DEBUG:
            print(f"📝 Not oluşturuldu: {title}")
        
        return f"'{title}' başlıklı not oluşturuldu efendim."
        
    except Exception as e:
        if DEBUG:
            print(f"❌ Not hatası: {e}")
        return f"Not oluşturulurken bir hata oluştu efendim: {e}"


# ────────────────────────────────────────
# ⏰ ALARM / ZAMANLAYICI
# ────────────────────────────────────────

_active_timers = []


def set_timer(duration: int, unit: str = "dakika", label: str = "") -> str:
    """
    Zamanlayıcı/alarm kurar. Süre dolduğunda sesli bildirim verir.
    
    Args:
        duration: Süre miktarı
        unit: Birim ("saniye", "dakika", "saat")
        label: Alarm etiketi
    """
    try:
        # Birimi saniyeye çevir
        multipliers = {
            "saniye": 1, "sn": 1, "second": 1, "seconds": 1,
            "dakika": 60, "dk": 60, "minute": 60, "minutes": 60,
            "saat": 3600, "hr": 3600, "hour": 3600, "hours": 3600,
        }
        
        seconds = duration * multipliers.get(unit.lower(), 60)
        
        if not label:
            label = f"{duration} {unit} zamanlayıcı"
        
        def _timer_callback(secs, lbl):
            """Arka planda çalışan zamanlayıcı."""
            time.sleep(secs)
            
            # macOS bildirimi
            notif_script = f'''
            display notification {applescript_quote(f"{lbl} - Süre doldu!")} with title "Jarvis Alarm" sound name "Glass"
            '''
            run_applescript(notif_script)
            
            # Sesli uyarı
            subprocess.run(["say", "-v", "Yelda", f"Efendim, {lbl} süresi doldu."], capture_output=True)
            
            # Alarm sesi çal
            subprocess.run([
                "afplay", "/System/Library/Sounds/Glass.aiff"
            ], capture_output=True)
            
            if DEBUG:
                print(f"⏰ Alarm: {lbl} — Süre doldu!")
        
        # Thread ile arka planda çalıştır
        timer_thread = threading.Thread(
            target=_timer_callback,
            args=(seconds, label),
            daemon=True
        )
        timer_thread.start()
        _active_timers.append({"label": label, "seconds": seconds, "thread": timer_thread})
        
        # İnsan dostu süre gösterimi
        if seconds >= 3600:
            display = f"{seconds // 3600} saat {(seconds % 3600) // 60} dakika"
        elif seconds >= 60:
            display = f"{seconds // 60} dakika"
        else:
            display = f"{seconds} saniye"
        
        if DEBUG:
            print(f"⏰ Zamanlayıcı kuruldu: {label} — {display}")
        
        return f"{display}lık zamanlayıcı kuruldu efendim. Süre dolduğunda haber vereceğim."
        
    except Exception as e:
        if DEBUG:
            print(f"❌ Zamanlayıcı hatası: {e}")
        return f"Zamanlayıcı kurulurken bir hata oluştu efendim: {e}"


def set_alarm(time_str: str, label: str = "") -> str:
    """
    Belirli bir saat için alarm kurar.
    
    Args:
        time_str: Saat (örn: "14:30", "8:00")
        label: Alarm etiketi
    """
    try:
        now = datetime.now()
        
        parts = time_str.replace(".", ":").split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        
        alarm_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # Eğer belirtilen saat geçmişse, yarın için kur
        if alarm_time <= now:
            alarm_time += timedelta(days=1)
        
        seconds_until = (alarm_time - now).total_seconds()
        
        if not label:
            label = f"{alarm_time.strftime('%H:%M')} alarmı"
        
        # Timer fonksiyonunu kullan
        return set_timer(
            duration=int(seconds_until),
            unit="saniye",
            label=label
        )
        
    except (ValueError, IndexError):
        return "Saat formatını anlayamadım efendim. Lütfen '14:30' gibi bir format kullanın."
    except Exception as e:
        return f"Alarm kurulurken bir hata oluştu efendim: {e}"


# ────────────────────────────────────────
# 🎯 ANA ROUTER — JSON Komutlarını Yönlendirir
# ────────────────────────────────────────

_action_registry = None
_pending_confirmation = None


def _to_int(value: object, default: int) -> int:
    try:
        if value in ("", None):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: object, default: float) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _text(command: dict, key: str, default: str = "") -> str:
    value = command.get(key, default)
    return str(value) if value is not None else default


def _confirm_pending_action(command: dict, context: ActionContext) -> str:
    """Execute the last action waiting for explicit confirmation."""
    global _pending_confirmation
    if not _pending_confirmation:
        return "Onay bekleyen bir işlem yok efendim."

    confirmed_command = dict(_pending_confirmation)
    confirmed_command["confirmed"] = True
    _pending_confirmation = None
    return execute_action(confirmed_command)


def _cancel_pending_action(command: dict, context: ActionContext) -> str:
    """Clear the last action waiting for confirmation."""
    global _pending_confirmation
    if not _pending_confirmation:
        return "İptal edilecek bekleyen bir işlem yok efendim."

    action = _pending_confirmation.get("action", "işlem")
    _pending_confirmation = None
    return f"{action} işlemi iptal edildi efendim."


def _build_action_registry() -> ActionRegistry:
    """Create the default Strategy registry for built-in actions."""
    registry = ActionRegistry()
    registry.register_many([
        FunctionActionPlugin(
            "open_app",
            lambda cmd, ctx: open_app(_text(cmd, "target")),
            "Uygulama aç",
            required_fields=("target",),
        ),
        FunctionActionPlugin(
            "close_app",
            lambda cmd, ctx: close_app(_text(cmd, "target")),
            "Uygulama kapat",
            required_fields=("target",),
        ),
        FunctionActionPlugin(
            "play_music",
            lambda cmd, ctx: play_music(_text(cmd, "target")),
            "Spotify araması başlat",
            required_fields=("target",),
        ),
        FunctionActionPlugin("pause_music", lambda cmd, ctx: pause_music(), "Müziği duraklat/devam ettir"),
        FunctionActionPlugin("next_track", lambda cmd, ctx: next_track(), "Sonraki parçaya geç"),
        FunctionActionPlugin("previous_track", lambda cmd, ctx: previous_track(), "Önceki parçaya dön"),
        FunctionActionPlugin(
            "set_volume",
            lambda cmd, ctx: set_volume(_to_int(cmd.get("value"), 50)),
            "Ses seviyesini ayarla",
        ),
        FunctionActionPlugin(
            "set_brightness",
            lambda cmd, ctx: set_brightness(_to_float(cmd.get("value"), 0.5)),
            "Ekran parlaklığını ayarla",
        ),
        FunctionActionPlugin("get_time", lambda cmd, ctx: get_current_time(), "Saat ve tarihi oku"),
        FunctionActionPlugin(
            "get_weather",
            lambda cmd, ctx: get_weather(_text(cmd, "target"), _text(cmd, "detail", "summary")),
            "Hava durumunu oku",
            required_fields=("target",),
        ),
        FunctionActionPlugin(
            "web_search",
            lambda cmd, ctx: web_search(_text(cmd, "target")),
            "DuckDuckGo araması yap ve yerel LLM ile özetle",
            required_fields=("target",),
        ),
        FunctionActionPlugin("lock_screen", lambda cmd, ctx: lock_screen(), "Ekranı kilitle"),
        FunctionActionPlugin(
            "empty_trash",
            lambda cmd, ctx: empty_trash(),
            "Çöp kutusunu boşalt",
            requires_confirmation=True,
        ),
        FunctionActionPlugin("dark_mode", lambda cmd, ctx: toggle_dark_mode(), "Karanlık modu değiştir"),
        FunctionActionPlugin("screenshot", lambda cmd, ctx: screenshot(), "Ekran görüntüsü al"),
        FunctionActionPlugin(
            "create_event",
            lambda cmd, ctx: create_calendar_event(
                _text(cmd, "target"),
                _text(cmd, "date"),
                _text(cmd, "time"),
                _to_int(cmd.get("duration"), 60),
                bool(cmd.get("all_day", False)),
            ),
            "Takvim etkinliği oluştur",
            required_fields=("target",),
        ),
        FunctionActionPlugin(
            "create_note",
            lambda cmd, ctx: create_note(_text(cmd, "target"), _text(cmd, "content")),
            "Apple Notes notu oluştur",
        ),
        FunctionActionPlugin(
            "set_timer",
            lambda cmd, ctx: set_timer(
                _to_int(cmd.get("value") or cmd.get("duration"), 5),
                _text(cmd, "unit", "dakika"),
                _text(cmd, "label"),
            ),
            "Zamanlayıcı kur",
        ),
        FunctionActionPlugin(
            "set_alarm",
            lambda cmd, ctx: set_alarm(_text(cmd, "time") or _text(cmd, "target"), _text(cmd, "label")),
            "Alarm kur",
        ),
        FunctionActionPlugin(
            "general_response",
            lambda cmd, ctx: _text(cmd, "response", "Evet efendim?"),
            "Sohbet yanıtı",
        ),
        FunctionActionPlugin(
            "confirm_action",
            _confirm_pending_action,
            "Bekleyen işlemi onayla",
            aliases=("confirm", "approve_action"),
        ),
        FunctionActionPlugin(
            "cancel_action",
            _cancel_pending_action,
            "Bekleyen işlemi iptal et",
            aliases=("cancel", "reject_action"),
        ),
    ])
    return registry


def get_action_registry() -> ActionRegistry:
    """Return the lazily created action registry."""
    global _action_registry
    if _action_registry is None:
        _action_registry = _build_action_registry()
    return _action_registry


def get_action_metadata() -> list[dict[str, object]]:
    """Expose action/plugin metadata for diagnostics and documentation."""
    return list(get_action_registry().metadata())


def execute_action(command: dict) -> str:
    """
    Brain modülünden gelen JSON komutunu alır,
    registry'deki doğru Strategy plugin'ine yönlendirir ve sonucu döndürür.
    """
    global _pending_confirmation

    if not isinstance(command, dict):
        return "Geçersiz komut formatı aldım efendim."

    action = str(command.get("action", "")).strip()
    target = command.get("target", "")
    value = command.get("value", "")

    if DEBUG:
        print(f"🎯 Aksiyon: {action} | Hedef: {target} | Değer: {value}")

    plugin = get_action_registry().get(action)
    if not plugin:
        return f"'{action}' aksiyonunu tanımıyorum efendim."

    if plugin.requires_confirmation and not command.get("confirmed"):
        _pending_confirmation = dict(command)
        return (
            f"{plugin.description} işlemi onay gerektiriyor efendim. "
            "Onaylamak için 'onaylıyorum', vazgeçmek için 'iptal et' diyebilirsiniz."
        )

    try:
        return plugin.execute(command, ActionContext(debug=DEBUG))
    except CommandValidationError as e:
        return f"Komut eksik veya hatalı efendim: {e}"
    except Exception as e:
        if DEBUG:
            print(f"❌ Aksiyon hatası: {e}")
        return f"Bu komutu çalıştırırken bir hata oluştu efendim: {e}"


# --- TEST ---
if __name__ == "__main__":
    print("🖐️  Hands modülü test ediliyor...")
    
    # Test: Saat
    print(execute_action({"action": "get_time"}))
    
    # Test: Web arama
    # print(execute_action({"action": "web_search", "target": "Python tutorials"}))
    
    # Test: Genel yanıt
    print(execute_action({"action": "general_response", "response": "Merhaba efendim!"}))

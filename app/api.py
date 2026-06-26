import asyncio
import threading
import traceback
import json
import subprocess
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from core.loader import global_loader
from core.metrics import LatencyTracker
from assistant.config import DEBUG, WAKE_WORD_ENABLED

MODEL_CATALOG = [
    {
        "name": "llama3.2:latest",
        "label": "Llama 3.2",
        "size": "2.0 GB",
        "min_ram_mb": 8192,
        "tone": "En hafif",
        "description": "RAM'i en az yorar; basit komutlarda hızlıdır.",
    },
    {
        "name": "qwen2.5:7b",
        "label": "Qwen 2.5 7B",
        "size": "4.7 GB",
        "min_ram_mb": 8192,
        "tone": "Önerilen",
        "description": "Türkçe komut, JSON ve araç takibinde en iyi denge.",
    },
    {
        "name": "qwen3:8b",
        "label": "Qwen 3 8B",
        "size": "5.2 GB",
        "min_ram_mb": 8192,
        "tone": "Daha zeki",
        "description": "Daha iyi Türkçe komut ve araç takibi; 8 GB'de çalışır ama daha yavaştır.",
    },
    {
        "name": "llama3.1:8b",
        "label": "Llama 3.1 8B",
        "size": "4.9 GB",
        "min_ram_mb": 12288,
        "tone": "Alternatif",
        "description": "Genel amaçlı güçlü yerel model; biraz daha ağırdır.",
    },
    {
        "name": "gemma3:12b",
        "label": "Gemma 3 12B",
        "size": "8.1 GB",
        "min_ram_mb": 16384,
        "tone": "Güçlü",
        "description": "Kalite odaklıdır; 16 GB ve üstü RAM önerilir.",
    },
]


def _installed_ollama_models() -> tuple[set[str], bool]:
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return set(), False

    if result.returncode != 0:
        return set(), False

    installed = set()
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if parts:
            installed.add(parts[0])
    return installed, True


def _is_model_installed(model_name: str, installed: set[str]) -> bool:
    if model_name in installed:
        return True
    base = model_name.split(":", 1)[0]
    return f"{base}:latest" in installed


def _ollama_model_names(models_info) -> set[str]:
    models = models_info.get("models", []) if isinstance(models_info, dict) else getattr(models_info, "models", [])
    names = set()
    for model in models:
        if isinstance(model, dict):
            name = model.get("name") or model.get("model")
        else:
            name = getattr(model, "name", "") or getattr(model, "model", "")
        if name:
            names.add(name)
    return names


def _response_value(response, key: str, default=None):
    if isinstance(response, dict):
        return response.get(key, default)
    return getattr(response, key, default)


def _recommended_model_for_ram(total_mb: int, pressure: str) -> tuple[str, str]:
    if total_mb >= 16384:
        return (
            "qwen3:8b",
            "RAM'iniz güçlü; daha akıllı yanıtlar için Qwen 3 8B iyi seçim.",
        )
    if total_mb >= 12288:
        return (
            "qwen2.5:7b",
            "RAM'i dengeli kullanıp Türkçe komutları iyi anlaması için Qwen 2.5 7B önerilir.",
        )
    if pressure == "high":
        return (
            "llama3.2:latest",
            "Bellek baskısı yüksek; RAM'i yormamak için en hafif model öneriliyor.",
        )
    if total_mb >= 8192:
        return (
            "qwen2.5:7b",
            "RAM'inizi yormayacak en dengeli seçenek Qwen 2.5 7B; daha hızlı isterseniz Llama 3.2 seçilebilir.",
        )
    return (
        "qwen2.5:7b",
        "8 GB RAM'de Türkçe kalite ve bellek dengesi için en uygun model bu.",
    )


def _current_llm_model() -> str:
    try:
        from assistant import config
        return str(config.OLLAMA_MODEL)
    except Exception:
        return global_loader.get_llm_model()


def _set_current_llm_model(model_name: str) -> None:
    from assistant import config
    from core.user_settings import save_settings

    config.OLLAMA_MODEL = model_name
    save_settings({"OLLAMA_MODEL": model_name})
    global_loader.unload("llm")


def build_model_setup_info(recs: dict) -> dict:
    installed, ollama_available = _installed_ollama_models()
    recommended_name, reason = _recommended_model_for_ram(
        int(recs.get("total_ram_mb") or 0),
        str(recs.get("pressure") or "unknown"),
    )
    current = _current_llm_model()
    models = []
    for item in MODEL_CATALOG:
        model = dict(item)
        model["installed"] = _is_model_installed(item["name"], installed)
        model["recommended"] = item["name"] == recommended_name
        model["current"] = item["name"] == current
        models.append(model)

    return {
        "models": models,
        "installed_models": sorted(installed),
        "recommended_model": recommended_name,
        "current_model": current,
        "recommendation_reason": reason,
        "ollama_available": ollama_available,
    }

# WebSocket bağlantı yöneticisi
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        await self.send_system_info()

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass
                
    async def send_system_info(self):
        from core.first_run import run_checks

        recs = global_loader.get_recommendations()
        stats = global_loader.status()
        model_setup = build_model_setup_info(recs)
        await self.broadcast({
            "type": "system_info",
            "data": {
                "recommendations": recs,
                "status_text": stats,
                "model_setup": model_setup,
                "setup_checks": [check.as_dict() for check in run_checks()]
            }
        })

    async def download_model(self, websocket: WebSocket, model_name: str):
        try:
            from ollama import AsyncClient
            client = AsyncClient()
            valid_models = {model["name"] for model in MODEL_CATALOG}
            if model_name not in valid_models:
                await websocket.send_json({
                    "type": "download_progress",
                    "data": {"status": "Bilinmeyen model seçildi.", "percent": -1}
                })
                return
            
            # Yüklü modelleri kontrol et
            try:
                models_info = await client.list()
            except Exception:
                # Ollama kapalıysa otomatik başlatmayı dene
                await websocket.send_json({
                    "type": "download_progress", 
                    "data": {"status": "Ollama servisi arka planda başlatılıyor...", "percent": 0}
                })
                import subprocess
                try:
                    subprocess.Popen(
                        ["ollama", "serve"], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )
                    await asyncio.sleep(3) # Servisin açılması için bekle
                    models_info = await client.list()
                except Exception as e:
                    await websocket.send_json({
                        "type": "download_progress", 
                        "data": {"status": "Ollama otomatik başlatılamadı. Lütfen terminale 'ollama serve' yazın.", "percent": -1}
                    })
                    return
            
            models = _ollama_model_names(models_info)
            
            # Model var mı kontrol et
            model_exists = _is_model_installed(model_name, models)
                    
            if model_exists:
                _set_current_llm_model(model_name)
                await self.send_system_info()
                await websocket.send_json({
                    "type": "download_progress", 
                    "data": {"status": "success", "percent": 100, "model": model_name}
                })
                threading.Thread(target=preload_runtime_modules, daemon=True).start()
                return

            # Modeli asenkron olarak indir
            async for progress in await client.pull(model_name, stream=True):
                status = _response_value(progress, "status", "İndiriliyor...")
                completed = _response_value(progress, "completed", 0) or 0
                total = _response_value(progress, "total", 1) or 1
                
                percent = int((completed / total) * 100) if total > 0 else 0
                
                # Küçük bir çeviri/düzenleme
                if "pulling manifest" in status:
                    status = "Manifest indiriliyor..."
                    percent = 0
                elif "downloading" in status:
                    status = "Model dosyaları indiriliyor..."
                elif "verifying" in status:
                    status = "Doğrulanıyor..."
                elif "writing manifest" in status:
                    status = "Kurulum tamamlanıyor..."
                    
                await websocket.send_json({
                    "type": "download_progress", 
                    "data": {"status": status, "percent": percent}
                })
                
            # İndirme başarıyla bitti
            _set_current_llm_model(model_name)
            await self.send_system_info()
            await websocket.send_json({
                "type": "download_progress", 
                "data": {"status": "success", "percent": 100, "model": model_name}
            })
            threading.Thread(target=preload_runtime_modules, daemon=True).start()
            
        except Exception as e:
            await websocket.send_json({
                "type": "download_progress", 
                "data": {"status": f"Hata: {str(e)}", "percent": -1}
            })

manager = ConnectionManager()
loop_ref = None
voice_command_lock = asyncio.Lock()

def send_event_from_thread(event_type: str, data: str):
    """Arka plan thread'inden WebSocket event'i fırlatır."""
    if loop_ref is not None:
        asyncio.run_coroutine_threadsafe(
            manager.broadcast({"type": event_type, "data": data}), 
            loop_ref
        )

def send_system_info_from_thread():
    if loop_ref is not None:
        asyncio.run_coroutine_threadsafe(
            manager.send_system_info(), 
            loop_ref
        )


def preload_runtime_modules():
    """Warm up heavy local modules after the web server starts."""
    preload_steps = [
        ("web_search", "Web arama hazırlanıyor..."),
        ("whisper", "Ses algılama modeli hazırlanıyor..."),
        ("llm", "Yerel zeka modeli hazırlanıyor..."),
    ]

    for module_name, status in preload_steps:
        try:
            send_event_from_thread("preload", status)
            global_loader.get(module_name)
        except Exception as exc:
            if DEBUG:
                print(f"⚠️ Preload hatası ({module_name}): {exc}")

    try:
        from assistant import brain

        # Tam brain yolunu ısıt: model, JSON formatı ve sistem prompt'u aynı anda cache'e girer.
        brain.process_command("Hazır mısın?")
        brain.clear_history()
    except Exception as exc:
        if DEBUG:
            print(f"⚠️ LLM ısıtma hatası: {exc}")

    send_event_from_thread("preload", "Hazırlık tamamlandı.")
    send_system_info_from_thread()

# ────────────────────────────────────────
# 🚀 ARKA PLAN JARVIS DÖNGÜSÜ
# ────────────────────────────────────────
def jarvis_background_loop():
    from assistant import brain, ear, hands, mouth

    send_event_from_thread("status", "Hazır ve Bekliyor...")
    
    while True:
        try:
            mode = "Hey Jarvis" if WAKE_WORD_ENABLED else "Push-to-Talk"
            send_event_from_thread("status", f"Dinlemeye Hazır ({mode})")
            send_system_info_from_thread()
            
            # 1. Wake word bekle
            if not ear.listen_for_wake_word():
                continue
                
            send_event_from_thread("status", "Dinliyor...")
            mouth.speak("Buyurun efendim.")
            tracker = LatencyTracker()
            
            # 2. Komutu al
            command_text = ear.record_and_transcribe()
            tracker.mark("stt")
            
            if not command_text:
                mouth.speak("Sizi anlayamadım efendim, tekrar söyler misiniz?")
                send_event_from_thread("error", "Anlaşılamadı.")
                continue
                
            send_event_from_thread("transcript", command_text)
            send_event_from_thread("status", "Düşünüyor...")
            
            # Çıkış komutları
            exit_commands = ["çık", "kapat", "durdur", "kapa kendini", "güle güle", "bye"]
            if any(cmd in command_text.lower() for cmd in exit_commands):
                mouth.speak("Hoşça kalın efendim.")
                send_event_from_thread("status", "Kapatıldı.")
                import os
                os._exit(0)
            
            # 3. LLM'e gönder
            command_json = brain.process_command(command_text)
            tracker.mark("llm")
            
            if not command_json:
                msg = "Bu komutu işleyemedim efendim. Sistem belleği yetersiz veya model kapalı olabilir."
                mouth.speak(msg)
                send_event_from_thread("error", "Komut İşlenemedi.")
                continue
                
            send_event_from_thread("status", "Uyguluyor...")
            
            # 4. Eylemi gerçekleştir
            result = hands.execute_action(command_json)
            tracker.mark("action")
            
            # 5. Sonucu söyle
            if result:
                send_event_from_thread("response", result)
                mouth.speak(result)
            tracker.mark("tts")

            if DEBUG:
                print(f"⏱️  Latency: {tracker.summary()}")
            send_event_from_thread("latency", tracker.as_dict())
                
            send_system_info_from_thread()
            
        except Exception as e:
            if DEBUG:
                traceback.print_exc()
            send_event_from_thread("error", f"Hata: {str(e)}")

async def process_text_command(text: str):
    from assistant import brain, hands, mouth
    
    # 1. Kullanıcı mesajını göster ve duruma geç
    await manager.broadcast({"type": "transcript", "data": text})
    await manager.broadcast({"type": "status", "data": "Düşünüyor..."})
    
    loop = asyncio.get_running_loop()
    tracker = LatencyTracker()
    try:
        # Çıkış komutları
        exit_commands = ["çık", "kapat", "durdur", "kapa kendini", "güle güle", "bye"]
        if any(cmd in text.lower() for cmd in exit_commands):
            await loop.run_in_executor(None, mouth.speak, "Hoşça kalın efendim.")
            await manager.broadcast({"type": "status", "data": "Kapatıldı."})
            import os
            os._exit(0)
            
        # 2. LLM'e gönder
        command_json = await loop.run_in_executor(None, brain.process_command, text)
        tracker.mark("llm")
        
        if not command_json:
            msg = "Bu komutu işleyemedim efendim. Sistem belleği yetersiz veya model kapalı olabilir."
            await loop.run_in_executor(None, mouth.speak, msg)
            await manager.broadcast({"type": "error", "data": "Komut İşlenemedi."})
            return
            
        await manager.broadcast({"type": "status", "data": "Uyguluyor..."})

        if command_json.get("action") == "open_app":
            target = str(command_json.get("target") or "uygulama").strip()
            optimistic_result = f"{target.title()} açılıyor efendim."
            await manager.broadcast({"type": "response", "data": optimistic_result})
            loop.run_in_executor(None, mouth.speak, optimistic_result)
            loop.run_in_executor(None, hands.execute_action, command_json)
            tracker.mark("action")
            tracker.mark("tts")
            await manager.broadcast({"type": "latency", "data": tracker.as_dict()})
            await manager.broadcast({"type": "status", "data": "Dinlemeye Hazır"})
            return
        
        # 3. Eylemi gerçekleştir
        result = await loop.run_in_executor(None, hands.execute_action, command_json)
        tracker.mark("action")
        
        # 4. Sonucu ekrana hemen gönder, TTS'i arka planda başlat.
        if result:
            await manager.broadcast({"type": "response", "data": result})
            loop.run_in_executor(None, mouth.speak, result)
        tracker.mark("tts")
        await manager.broadcast({"type": "latency", "data": tracker.as_dict()})
        if DEBUG:
            print(f"⏱️  Latency: {tracker.summary()}")
            
        await manager.send_system_info()
        await manager.broadcast({"type": "status", "data": "Dinlemeye Hazır"})
        
    except Exception as e:
        if DEBUG:
            traceback.print_exc()
        await manager.broadcast({"type": "error", "data": f"Hata: {str(e)}"})


async def process_voice_command():
    if voice_command_lock.locked():
        await manager.broadcast({"type": "status", "data": "Zaten dinliyor..."})
        return

    async with voice_command_lock:
        from assistant import ear

        loop = asyncio.get_running_loop()
        await manager.broadcast({"type": "status", "data": "Dinliyor..."})

        try:
            command_text = await loop.run_in_executor(None, ear.record_and_transcribe)
        except Exception as e:
            if DEBUG:
                traceback.print_exc()
            await manager.broadcast({"type": "error", "data": f"Ses alınamadı: {str(e)}"})
            await manager.broadcast({"type": "status", "data": "Dinlemeye Hazır"})
            return

        if not command_text:
            detail = ""
            if hasattr(ear, "get_last_audio_error"):
                detail = ear.get_last_audio_error()
            message = f"Ses anlaşılamadı: {detail}" if detail else "Ses anlaşılamadı."
            await manager.broadcast({"type": "error", "data": message})
            await manager.broadcast({"type": "status", "data": "Dinlemeye Hazır"})
            return

        await process_text_command(command_text)

# ────────────────────────────────────────
# 🌐 FASTAPI UYGULAMASI
# ────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global loop_ref
    loop_ref = asyncio.get_running_loop()
    
    # Ağır yerel modülleri arkaplanda ısıt
    threading.Thread(target=preload_runtime_modules, daemon=True).start()
    # Asistanı arkaplanda başlat
    threading.Thread(target=jarvis_background_loop, daemon=True).start()
    yield
    # Kapanış işlemleri (gerekirse)

app = FastAPI(lifespan=lifespan)

# Statik dosyalar (HTML, CSS, JS)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def get_index():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "start_setup":
                    llm_model = msg.get("llm_model")
                    if llm_model and llm_model != "Hesaplanıyor...":
                        asyncio.create_task(manager.download_model(websocket, llm_model))
                elif msg.get("action") == "select_model":
                    llm_model = msg.get("llm_model")
                    if llm_model and llm_model != "Hesaplanıyor...":
                        asyncio.create_task(manager.download_model(websocket, llm_model))
                elif msg.get("action") == "chat":
                    text = msg.get("text")
                    if text:
                        # Process text asynchronously
                        asyncio.create_task(process_text_command(text))
                elif msg.get("action") == "voice_command":
                    asyncio.create_task(process_voice_command())
                elif msg.get("action") == "clear_history":
                    from assistant import brain
                    brain.clear_history()
                    await websocket.send_json({
                        "type": "history_cleared",
                        "data": {"status": "success"}
                    })
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    print("🚀 Jarvis Web Dashboard başlatılıyor (http://localhost:8000)")
    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, reload=False)

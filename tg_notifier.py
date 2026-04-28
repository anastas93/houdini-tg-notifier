import hou
import threading
import time
import urllib.request
import json
import os
import re
import glob
from datetime import datetime

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".houdini_tg_notifier.json")

DEFAULT_SETTINGS = {
    "bot_token": "",
    "chat_ids": [],
    "send_errors":   True,
    "send_warnings": True,
    "send_messages": True,
    "send_render":   True,
    "scene_name_in_msg": True,
    "monitor_enabled": False,
    "cooldown": 15,
    "frame_progress_every": 10,  # прогресс каждые N кадров (0 = выкл)
    "send_preview": True,        # отправлять превью последнего кадра
    "bot_polling": False,        # polling для команд /status /stop
}

RENDER_PATTERNS = [
    re.compile(r, re.IGNORECASE) for r in [
        r"render\s+complete",
        r"rendered?\s+frame",
        r"mantra.*finished",
        r"karma.*finished",
        r"rendering\s+done",
        r"ifd.*written",
        r"render\s+time\s*:",
        r"frame\s+\d+.*done",
        r"cook\s+complete",
    ]
]

# Глобальное состояние рендера (для /status и прогресса)
_render_state = {
    "active": False,
    "start_time": None,
    "scene": "",
    "rop": "",
    "cam": "",
    "out_path": "",
    "f1": 1, "f2": 1,
    "current_frame": 0,
}


# ── Настройки ─────────────────────────────────────────────────────────────────

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        s = DEFAULT_SETTINGS.copy()
        s.update(data)
        if "chat_id" in data and "chat_ids" not in data:
            old = data.get("chat_id", "")
            s["chat_ids"] = [c.strip() for c in old.split(",") if c.strip()] if old else []
        return s
    return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


# ── Telegram API ──────────────────────────────────────────────────────────────

def _send_one(token, chat_id, text):
    url = "https://api.telegram.org/bot{}/sendMessage".format(token)
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
        if not result.get("ok"):
            raise RuntimeError(str(result))


def send_telegram(token, chat_ids, text):
    if not token:
        return False, "bot_token not set"
    if isinstance(chat_ids, str):
        chat_ids = [c.strip() for c in chat_ids.split(",") if c.strip()]
    chat_ids = [str(c).strip() for c in chat_ids if str(c).strip()]
    if not chat_ids:
        return False, "no chat_ids configured"
    errors = []
    for cid in chat_ids:
        try: _send_one(token, cid, text)
        except Exception as e: errors.append("{}: {}".format(cid, e))
    return (True, "") if not errors else (False, "; ".join(errors))


def send_photo_telegram(token, chat_ids, image_path, caption=""):
    """Отправить фото. EXR конвертируется через OpenImageIO (встроен в Houdini)."""
    if not token or not chat_ids:
        return False, "not configured"
    if isinstance(chat_ids, str):
        chat_ids = [c.strip() for c in chat_ids.split(",") if c.strip()]
    chat_ids = [str(c).strip() for c in chat_ids if str(c).strip()]

    send_path = image_path
    tmp_png = None

    # EXR → PNG через OpenImageIO
    if image_path.lower().endswith(".exr"):
        tmp_png = image_path + "_tg_preview.png"
        converted = False
        try:
            import OpenImageIO as oiio
            buf = oiio.ImageBuf(image_path)
            # Tone map: linear → sRGB
            buf = oiio.ImageBufAlgo.colorconvert(buf, "linear", "sRGB")
            # Обрезаем до 1280px по ширине для превью
            spec = buf.spec()
            if spec.width > 1280:
                scale = 1280.0 / spec.width
                new_w = 1280
                new_h = int(spec.height * scale)
                buf = oiio.ImageBufAlgo.resize(buf, roi=oiio.ROI(0, new_w, 0, new_h))
            buf.write(tmp_png)
            send_path = tmp_png
            converted = True
        except Exception as e:
            print("[TG Notifier] EXR convert error:", e)
        if not converted:
            return False, "Cannot convert EXR (no OpenImageIO)"

    if not os.path.exists(send_path):
        return False, "File not found: " + send_path

    errors = []
    for cid in chat_ids:
        try:
            url = "https://api.telegram.org/bot{}/sendPhoto".format(token)
            with open(send_path, "rb") as img_f:
                img_data = img_f.read()
            boundary = "TGNboundary9876"
            body = (
                ("--" + boundary + "\r\n"
                 "Content-Disposition: form-data; name=\"chat_id\"\r\n\r\n"
                 + str(cid) + "\r\n").encode()
                + ("--" + boundary + "\r\n"
                   "Content-Disposition: form-data; name=\"caption\"\r\n\r\n"
                   + caption[:1024] + "\r\n").encode()
                + ("--" + boundary + "\r\n"
                   "Content-Disposition: form-data; name=\"photo\"; filename=\"preview.png\"\r\n"
                   "Content-Type: image/png\r\n\r\n").encode()
                + img_data
                + ("\r\n--" + boundary + "--\r\n").encode()
            )
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "multipart/form-data; boundary=" + boundary}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
                if not result.get("ok"):
                    errors.append("{}: {}".format(cid, result))
        except Exception as e:
            errors.append("{}: {}".format(cid, e))

    if tmp_png and os.path.exists(tmp_png):
        try: os.remove(tmp_png)
        except: pass

    return (True, "") if not errors else (False, "; ".join(errors))


def _resolve_path(template, frame):
    """Находит реальный файл рендера. Поддерживает Octane-стиль (путь без расширения)."""
    if not template or template == "unknown":
        return None

    EXTENSIONS = [".exr", ".png", ".jpg", ".tiff", ".tif", ".hdr", ".pic", ".tga"]

    # Путь уже готовый
    if os.path.exists(template):
        return template

    # Octane: путь без расширения, добавляем .NNNN.ext
    base = re.sub(r"\.\d+$", "", template)  # убираем .0001 если есть
    for ext in EXTENSIONS:
        # Точный кадр
        candidate = "{}.{:04d}{}".format(base, frame, ext)
        if os.path.exists(candidate):
            return candidate
        # Последний доступный кадр
        matches = sorted(glob.glob(base + ".*" + ext))
        if matches:
            return matches[-1]

    # Houdini переменные
    p = template
    p = re.sub(r"\$F(\d*)", lambda m: "{:0{}d}".format(frame, int(m.group(1)) if m.group(1) else 1), p)
    for var in ("$OCTANE_PASS", "$OCTANE_LAYER", "$OS"):
        p = p.replace(var, "*")
    try:
        p = p.replace("$HIPNAME", os.path.splitext(os.path.basename(hou.hipFile.name()))[0])
        p = p.replace("$HIP", os.path.dirname(hou.hipFile.name()))
    except Exception:
        pass
    if "*" in p:
        matches = sorted(glob.glob(p))
        if matches:
            beauty = [m for m in matches if "beauty" in m.lower()]
            return beauty[0] if beauty else matches[0]
    elif os.path.exists(p):
        return p

    # Последний файл в папке
    try:
        folder = os.path.dirname(template)
        if os.path.isdir(folder):
            all_files = []
            for ext in EXTENSIONS:
                all_files.extend(glob.glob(os.path.join(folder, "*" + ext)))
            if all_files:
                return sorted(all_files)[-1]
    except Exception:
        pass

    return None


# ── Bot Polling ───────────────────────────────────────────────────────────────

_bot_offset = 0
_bot_polling_active = False


def _bot_poll_loop(token, chat_ids):
    global _bot_offset, _bot_polling_active
    allowed = [str(c) for c in chat_ids]
    while _bot_polling_active:
        try:
            url = "https://api.telegram.org/bot{}/getUpdates?offset={}&timeout=10".format(token, _bot_offset)
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read())
            if data.get("ok"):
                for upd in data.get("result", []):
                    _bot_offset = upd["update_id"] + 1
                    msg = upd.get("message", {})
                    text = msg.get("text", "").strip().lower()
                    from_id = str(msg.get("chat", {}).get("id", ""))
                    if from_id not in allowed:
                        continue
                    if text == "/status":
                        _handle_status(token, from_id)
                    elif text == "/stop":
                        _handle_stop(token, from_id)
                    elif text == "/help":
                        _handle_help(token, from_id)
        except Exception:
            pass
        time.sleep(2)


def _handle_status(token, chat_id):
    rs = _render_state
    if rs["active"] and rs["start_time"]:
        elapsed = int(time.time() - rs["start_time"])
        m, s = divmod(elapsed, 60)
        elapsed_str = "{}м {}с".format(m, s)
        pct = 0
        if rs["f2"] > rs["f1"]:
            pct = int((rs["current_frame"] - rs["f1"]) / max(rs["f2"] - rs["f1"], 1) * 100)
        frame_info = "\n🖼 <b>Кадр:</b> {} / {} ({}%)".format(rs["current_frame"], rs["f2"], pct)
        text = (
            "📊 <b>СТАТУС HOUDINI</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            "🎬 Рендер: <b>АКТИВЕН</b>\n"
            "📁 <b>Сцена:</b> <i>{scene}</i>\n"
            "🎥 <b>Камера:</b> <code>{cam}</code>\n"
            "⏱ <b>Идёт:</b> <code>{elapsed}</code>{frame_info}"
        ).format(scene=rs["scene"], cam=rs["cam"], elapsed=elapsed_str, frame_info=frame_info)
    else:
        try: scene = os.path.basename(hou.hipFile.name())
        except: scene = "unknown"
        text = (
            "📊 <b>СТАТУС HOUDINI</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            "💤 Рендер: <b>не активен</b>\n"
            "📁 <b>Сцена:</b> <i>{}</i>"
        ).format(scene)
    try: _send_one(token, chat_id, text)
    except Exception: pass


def _handle_stop(token, chat_id):
    try:
        hou.hscript("render -a")
        _send_one(token, chat_id, "🛑 <b>Рендер остановлен</b>")
    except Exception as e:
        try: _send_one(token, chat_id, "❌ Не удалось остановить: {}".format(e))
        except: pass


def _handle_help(token, chat_id):
    text = (
        "🤖 <b>Houdini TG Notifier</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "/status — статус рендера\n"
        "/stop — остановить рендер\n"
        "/help — эта справка"
    )
    try: _send_one(token, chat_id, text)
    except Exception: pass


# ── Основной класс ────────────────────────────────────────────────────────────

class TGNotifier:
    def __init__(self):
        self.settings = load_settings()
        self._last_sent = {}
        self._lock = threading.Lock()
        self._sink = None
        self._poll_thread = None
        self._active = False
        self._history = []
        self._history_max = 200
        if self.settings.get("monitor_enabled"):
            self.start()

    def start(self):
        if self._active:
            return True, "Already running"
        self._active = True
        self.settings["monitor_enabled"] = True
        save_settings(self.settings)
        self._start_memory_sink()
        self._start_bot_polling()
        return True, "Monitor started"

    def stop(self):
        global _bot_polling_active
        self._active = False
        _bot_polling_active = False
        self.settings["monitor_enabled"] = False
        save_settings(self.settings)
        if self._sink:
            try:
                for src in self._sink.connectedSources():
                    try: self._sink.disconnect(src)
                    except: pass
            except: pass
            self._sink = None

    def _start_memory_sink(self):
        ms = hou.logging.MemorySink()
        connected = []
        for src_name in hou.logging.defaultSink().connectedSources():
            try:
                ms.connect(src_name)
                connected.append(src_name)
            except Exception:
                pass
        self._sink = ms
        print("[TG Notifier] Connected to:", connected)

        def _poll():
            while self._active:
                try:
                    entries = ms.stealLogEntries()
                    for e in entries:
                        self._on_entry(e.severity(), e.message(), "")
                except Exception:
                    pass
                time.sleep(0.5)

        self._poll_thread = threading.Thread(target=_poll, daemon=True)
        self._poll_thread.start()

    def _start_bot_polling(self):
        global _bot_polling_active
        s = load_settings()
        if not s.get("bot_polling", False):
            return
        if not s.get("bot_token") or not s.get("chat_ids"):
            return
        _bot_polling_active = True
        threading.Thread(
            target=_bot_poll_loop,
            args=(s["bot_token"], s["chat_ids"]),
            daemon=True
        ).start()
        print("[TG Notifier] Bot polling started")

    def _on_entry(self, severity, message, source=""):
        self.settings = load_settings()
        s = self.settings
        with self._lock:
            self._history.append((severity, message))
            if len(self._history) > self._history_max:
                self._history.pop(0)
        is_render = any(p.search(message) for p in RENDER_PATTERNS)
        want = False
        if is_render and s.get("send_render", True): want = True
        elif severity in (hou.severityType.Error, hou.severityType.Fatal) and s["send_errors"]: want = True
        elif severity == hou.severityType.Warning and s["send_warnings"]: want = True
        elif severity == hou.severityType.Message and s["send_messages"]: want = True
        if not want: return
        with self._lock:
            now = time.time()
            key = message[:100]
            if now - self._last_sent.get(key, 0) < s["cooldown"]: return
            self._last_sent[key] = now
        threading.Thread(target=self._send, args=(severity, message, source, is_render), daemon=True).start()

    def _send(self, severity, message, source="", is_render=False):
        s = self.settings
        if is_render:
            icon, label = "OK", "RENDER"
        else:
            icon, label = {
                hou.severityType.Fatal:   ("!!", "FATAL"),
                hou.severityType.Error:   ("X",  "ERROR"),
                hou.severityType.Warning: ("!",  "WARNING"),
                hou.severityType.Message: ("i",  "MESSAGE"),
            }.get(severity, ("-", "INFO"))
        scene = ""
        if s.get("scene_name_in_msg"):
            try: scene = "\n<b>Scene:</b> {}".format(os.path.basename(hou.hipFile.name()))
            except: pass
        ts = datetime.now().strftime("%H:%M:%S")
        text = "[{}] <b>{}</b>\n<b>Time:</b> {}{}\n<code>{}</code>".format(
            icon, label, ts, scene, message[:800])
        if source: text += "\n<i>Source: {}</i>".format(source)
        send_telegram(s["bot_token"], s.get("chat_ids", []), text)

    def send_last_errors(self, n=15):
        lines = []
        try:
            entries = list(hou.logging.defaultSink().logEntries())[-n:]
            for e in entries:
                tag = {hou.severityType.Fatal: "FATAL", hou.severityType.Error: "ERR",
                       hou.severityType.Warning: "WARN"}.get(e.severity(), "MSG")
                lines.append("[{}] {}".format(tag, e.message()[:200]))
        except Exception:
            pass
        if not lines:
            with self._lock: raw = self._history[-n:]
            if not raw: return True, "History empty"
            for sev, msg in raw:
                tag = {hou.severityType.Fatal: "FATAL", hou.severityType.Error: "ERR",
                       hou.severityType.Warning: "WARN"}.get(sev, "MSG")
                lines.append("[{}] {}".format(tag, msg[:200]))
        if not lines: return True, "No log entries"
        s = self.settings
        scene = ""
        if s.get("scene_name_in_msg"):
            try: scene = "\n<b>Scene:</b> {}".format(os.path.basename(hou.hipFile.name()))
            except: pass
        text = "<b>Houdini Log</b>{}\n\n<code>{}</code>".format(scene, "\n".join(lines))
        return send_telegram(s["bot_token"], s.get("chat_ids", []), text)

    def update_settings(self, **kwargs):
        self.settings.update(kwargs)
        save_settings(self.settings)


_instance = None


def get_notifier():
    global _instance
    if _instance is None:
        _instance = TGNotifier()
    return _instance

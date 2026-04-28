# Houdini → Telegram Notifier

Плагин для Houdini + Octane — уведомления о рендере и ошибках прямо в Telegram.

---

## Возможности

- 🔴 **Ошибки** (Error / Fatal) из консоли Houdini в реальном времени
- 🟡 **Предупреждения** (Warning)
- ℹ️ **Сообщения** (Message / print)
- 🎬 **Старт рендера** — камера, диапазон кадров, путь файла
- ✅ **Завершение рендера** — имя и путь файла
- 📤 **Ручная отправка** последних записей лога
- 💬 **Несколько чатов** — отправка одновременно в любое количество чатов/каналов
- ⚙️ **UI панель** прямо в Houdini (Python Panel)
- 🔄 **Автозапуск** при каждом старте Houdini

---

## Файлы

| Файл | Куда положить | Описание |
|---|---|---|
| `tg_notifier.py` | `~/houdini_tg_notifier/` | Ядро: мониторинг лога, Telegram API |
| `tg_notifier_panel.py` | `~/houdini_tg_notifier/` | Python Panel UI |
| `123.py` | `~/Documents/houdini21.0/scripts/` | Автозапуск при старте Houdini |

---

## Установка

### 1. Создать Telegram бота

1. Написать [@BotFather](https://t.me/BotFather) → `/newbot` → скопировать **Token**
2. Написать боту любое сообщение
3. Узнать **Chat ID** — написать [@userinfobot](https://t.me/userinfobot), он ответит твоим ID
   - Для группы/канала: добавить бота туда, открыть `https://api.telegram.org/bot<TOKEN>/getUpdates`

### 2. Скопировать файлы

```
C:\Users\<user>\houdini_tg_notifier\
  tg_notifier.py
  tg_notifier_panel.py

C:\Users\<user>\Documents\houdini21.0\scripts\
  123.py
```

### 3. Добавить Python Panel

1. Houdini → **Windows → Python Panel Editor → (+) New Panel**
2. Заполнить:
   - **Label:** `TG Notifier`
   - **Name:** `tg_notifier`
3. Вкладка **Interface** → поле **Script**, вставить:
   ```python
   exec(open(r"C:/Users/<user>/houdini_tg_notifier/tg_notifier_panel.py", encoding="utf-8").read())
   ```
4. **Apply → Accept**
5. Открыть: **Windows → TG Notifier**

### 4. Первый запуск

1. Вставить **Bot Token** и **Chat ID** (кнопка `+` для добавления)
2. Нажать **Test All** — придёт тестовое сообщение
3. Нажать **Save**
4. Нажать **Start Monitor**

---

## Скрипты для Octane ROP

Вставить в параметры ноды `OctaneRenderSetup` → вкладка **Scripts** → тип **Python**:

### Pre-Render Script (старт рендера)

```python
import sys, os
_plugin = os.path.join(os.path.expanduser('~'), 'houdini_tg_notifier')
if _plugin not in sys.path:
    sys.path.insert(0, _plugin)
from tg_notifier import get_notifier, send_telegram
from datetime import datetime
import hou as _hou
s = get_notifier().settings
if s.get('send_render', True):
    ts = datetime.now().strftime('%H:%M:%S')
    scene = os.path.basename(_hou.hipFile.name())
    node = _hou.pwd()
    try: cam = node.parm('HO_renderCamera').eval()
    except: cam = 'unknown'
    try:
        f1 = int(node.parm('f1').eval())
        f2 = int(node.parm('f2').eval())
        f3 = node.parm('f3').eval()
        total = int((f2 - f1) / f3) + 1
        frames = '{} - {} ({} кадров)'.format(f1, f2, total)
    except: frames = 'unknown'
    try: out_path = node.parm('HO_img_fileName').eval()
    except: out_path = 'unknown'
    out_name = os.path.basename(out_path)
    text = (
        '\U0001f3ac <b>РЕНДЕР ЗАПУЩЕН</b>\n'
        '\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n'
        '\U0001f550 <b>Время:</b>  <code>{ts}</code>\n'
        '\U0001f4c1 <b>Сцена:</b>  <i>{scene}</i>\n'
        '\U0001f3a5 <b>Камера:</b> <code>{cam}</code>\n'
        '\U0001f5bc <b>Кадры:</b>  <code>{frames}</code>\n'
        '\U0001f4be <b>Файл:</b>   <code>{name}</code>\n'
        '\U0001f4c2 <b>Путь:</b>\n<code>{path}</code>'
    ).format(ts=ts, scene=scene, cam=cam, frames=frames, name=out_name, path=out_path)
    send_telegram(s['bot_token'], s.get('chat_ids', []), text)
```

### Post-Render Script (завершение рендера)

```python
import sys, os
_plugin = os.path.join(os.path.expanduser('~'), 'houdini_tg_notifier')
if _plugin not in sys.path:
    sys.path.insert(0, _plugin)
from tg_notifier import get_notifier, send_telegram
from datetime import datetime
import hou as _hou
s = get_notifier().settings
if s.get('send_render', True):
    ts = datetime.now().strftime('%H:%M:%S')
    scene = os.path.basename(_hou.hipFile.name())
    node = _hou.pwd()
    try: out_path = node.parm('HO_img_fileName').eval()
    except: out_path = 'unknown'
    out_name = os.path.basename(out_path)
    text = (
        '\u2705 <b>РЕНДЕР ЗАВЕРШЁН</b>\n'
        '\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n'
        '\U0001f550 <b>Время:</b> <code>{ts}</code>\n'
        '\U0001f4c1 <b>Сцена:</b> <i>{scene}</i>\n'
        '\U0001f4be <b>Файл:</b>  <code>{name}</code>\n'
        '\U0001f4c2 <b>Путь:</b>\n<code>{path}</code>'
    ).format(ts=ts, scene=scene, name=out_name, path=out_path)
    send_telegram(s['bot_token'], s.get('chat_ids', []), text)
```

---

## Пример сообщений в Telegram

**Старт:**
```
🎬 РЕНДЕР ЗАПУЩЕН
━━━━━━━━━━━━━━━━
🕐 Время:  14:05:11
📁 Сцена:  project_v04.hip
🎥 Камера: /obj/cam1
🖼 Кадры:  1 - 240 (240 кадров)
💾 Файл:   beauty.$F4.exr
📂 Путь:
D:/renders/project/beauty.$F4.exr
```

**Завершение:**
```
✅ РЕНДЕР ЗАВЕРШЁН
━━━━━━━━━━━━━━━━
🕐 Время: 17:42:05
📁 Сцена: project_v04.hip
💾 Файл:  beauty.0240.exr
📂 Путь:
D:/renders/project/beauty.0240.exr
```

**Ошибка:**
```
[X] ERROR
Time: 14:23:07
Scene: project_v04.hip
AttributeError: 'NoneType' object has no attribute 'geometry'
```

---

## Настройки

Хранятся в `~/.houdini_tg_notifier.json`, редактируются через UI панели:

```json
{
  "bot_token": "123456:ABC-DEF...",
  "chat_ids": ["-100123456789", "987654321"],
  "send_errors": true,
  "send_warnings": true,
  "send_messages": true,
  "send_render": true,
  "scene_name_in_msg": true,
  "monitor_enabled": true,
  "cooldown": 15
}
```

| Параметр | Описание |
|---|---|
| `bot_token` | Токен от @BotFather |
| `chat_ids` | Список chat ID (чаты, группы, каналы) |
| `send_errors` | Отправлять Error / Fatal |
| `send_warnings` | Отправлять Warning |
| `send_messages` | Отправлять Message |
| `send_render` | Отправлять события рендера |
| `cooldown` | Пауза (сек) между повторами одного сообщения |
| `monitor_enabled` | Автозапуск мониторинга при старте Houdini |

---

## Как работает мониторинг

- **Houdini 19.5+** — `hou.logging.LogSink` (нативный callback, нулевая задержка)
- **Старше** — fallback через опрос `$HOUDINI_TEMP_DIR/houdini.log` каждые 2 сек
- **Octane рендер** — через Pre/Post Render Script в параметрах ноды `OctaneRenderSetup`

---

## Совместимость

| | |
|---|---|
| Houdini | 19.5+ (LogSink) / 18.x (fallback) |
| Octane | Любая версия для Houdini |
| ОС | Windows, Linux, macOS |
| Python | 3.9+ |

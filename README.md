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
- 💬 **Несколько чатов** одновременно
- ⚙️ **UI панель** в Houdini (Python Panel)
- 🔄 **Автозапуск** при каждом старте Houdini

---

## Файлы

| Файл | Куда положить | Описание |
|---|---|---|
| `tg_notifier.py` | `~/houdini_tg_notifier/` | Ядро: мониторинг, Telegram API |
| `tg_notifier_panel.py` | `~/houdini_tg_notifier/` | Python Panel UI |
| `123.py` | `~/Documents/houdiniXX.X/scripts/` | Автозапуск при старте Houdini |

---

## Установка

### 1. Создать Telegram бота

1. [@BotFather](https://t.me/BotFather) → `/newbot` → скопировать **Token**
2. Написать боту любое сообщение
3. Узнать **Chat ID** через [@userinfobot](https://t.me/userinfobot)
   - Для группы/канала: `https://api.telegram.org/bot<TOKEN>/getUpdates`

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
2. **Label:** `TG Notifier`, **Name:** `tg_notifier`
3. Вкладка **Interface** → поле **Script**:
```python
exec(open(r"C:/Users/<user>/houdini_tg_notifier/tg_notifier_panel.py", encoding="utf-8").read())
```
4. **Apply → Accept** → открыть: **Windows → TG Notifier**

### 4. Первый запуск

1. Вставить **Bot Token**, добавить **Chat ID** кнопкой `+`
2. Нажать **Test All** — придёт тестовое сообщение
3. **Save** → **Start Monitor**

---

## Скрипты для Octane ROP

Вставить в ноду `OctaneRenderSetup` → вкладка **Scripts** → тип **Python**.

### Pre-Render Script

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
        '🎬 <b>РЕНДЕР ЗАПУЩЕН</b>\n'
        '━━━━━━━━━━━━━━━━\n'
        '🕐 <b>Время:</b>  <code>{ts}</code>\n'
        '📁 <b>Сцена:</b>  <i>{scene}</i>\n'
        '🎥 <b>Камера:</b> <code>{cam}</code>\n'
        '🖼 <b>Кадры:</b>  <code>{frames}</code>\n'
        '💾 <b>Файл:</b>   <code>{name}</code>\n'
        '📂 <b>Путь:</b>\n<code>{path}</code>'
    ).format(ts=ts, scene=scene, cam=cam, frames=frames, name=out_name, path=out_path)
    send_telegram(s['bot_token'], s.get('chat_ids', []), text)
```

### Post-Render Script

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
        '✅ <b>РЕНДЕР ЗАВЕРШЁН</b>\n'
        '━━━━━━━━━━━━━━━━\n'
        '🕐 <b>Время:</b> <code>{ts}</code>\n'
        '📁 <b>Сцена:</b> <i>{scene}</i>\n'
        '💾 <b>Файл:</b>  <code>{name}</code>\n'
        '📂 <b>Путь:</b>\n<code>{path}</code>'
    ).format(ts=ts, scene=scene, name=out_name, path=out_path)
    send_telegram(s['bot_token'], s.get('chat_ids', []), text)
```

---

## Пример сообщений

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

```
✅ РЕНДЕР ЗАВЕРШЁН
━━━━━━━━━━━━━━━━
🕐 Время: 17:42:05
📁 Сцена: project_v04.hip
💾 Файл:  beauty.0240.exr
📂 Путь:
D:/renders/project/beauty.0240.exr
```

---

## Настройки (`~/.houdini_tg_notifier.json`)

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
- **Старше 19.5** — fallback через опрос `$HOUDINI_TEMP_DIR/houdini.log` каждые 2 сек
- **Octane рендер** — через Pre/Post Render Script в параметрах `OctaneRenderSetup`

---

## Совместимость

| | |
|---|---|
| Houdini | 19.5+ (LogSink) / 18.x (fallback) |
| Octane | Любая версия для Houdini |
| ОС | Windows, Linux, macOS |
| Python | 3.9+ |
# Octane ROP — Scripts for Telegram Notifier

Скрипты для вставки в ноду `OctaneRenderSetup` → вкладка **Scripts** → тип **Python**.

---

## Pre-Render Script (старт рендера)

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

---

## Post-Render Script (завершение рендера)

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
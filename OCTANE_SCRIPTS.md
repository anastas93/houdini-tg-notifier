# Octane ROP — Scripts for Telegram Notifier

Вставить в ноду `OctaneRenderSetup` → вкладка **Scripts** → тип **Python**.

---

## Pre-Render Script (старт + прогресс)

```python
import sys, os, time, threading
_plugin = os.path.join(os.path.expanduser('~'), 'houdini_tg_notifier')
if _plugin not in sys.path:
    sys.path.insert(0, _plugin)
from tg_notifier import get_notifier, send_telegram, _render_state
from datetime import datetime
import hou as _hou

s = get_notifier().settings
if s.get('send_render', True):
    node = _hou.pwd()
    ts = datetime.now().strftime('%H:%M:%S')
    scene = os.path.basename(_hou.hipFile.name())

    try: cam = node.parm('HO_renderCamera').eval()
    except: cam = 'unknown'

    try:
        f1 = int(node.parm('f1').eval())
        f2 = int(node.parm('f2').eval())
        f3 = node.parm('f3').eval()
        total = int((f2 - f1) / f3) + 1
        frames_str = '{} - {} ({} кадров)'.format(f1, f2, total)
    except:
        f1, f2, total = 1, 1, 1
        frames_str = 'unknown'

    try: out_path = node.parm('HO_img_fileName').eval()
    except: out_path = 'unknown'
    out_name = os.path.basename(out_path)

    _render_state.update({
        'active': True,
        'start_time': time.time(),
        'scene': scene,
        'rop': node.path(),
        'cam': cam,
        'out_path': out_path,
        'f1': f1, 'f2': f2,
        'current_frame': f1,
    })

    text = (
        '🎬 <b>РЕНДЕР ЗАПУЩЕН</b>\n'
        '━━━━━━━━━━━━━━━━\n'
        '🕐 <b>Время:</b>  <code>{ts}</code>\n'
        '📁 <b>Сцена:</b>  <i>{scene}</i>\n'
        '🎥 <b>Камера:</b> <code>{cam}</code>\n'
        '🖼 <b>Кадры:</b>  <code>{frames}</code>\n'
        '💾 <b>Файл:</b>   <code>{name}</code>\n'
        '📂 <b>Путь:</b>\n<code>{path}</code>'
    ).format(ts=ts, scene=scene, cam=cam, frames=frames_str, name=out_name, path=out_path)
    send_telegram(s['bot_token'], s.get('chat_ids', []), text)

    # Прогресс-поток: опрашивает hou.frame() каждые N секунд
    every = s.get('frame_progress_every', 10)
    if every > 0:
        def _progress_loop():
            last_sent_frame = f1 - 1
            while _render_state.get('active'):
                time.sleep(5)
                try:
                    cur = int(_hou.frame())
                    _render_state['current_frame'] = cur
                    done = cur - f1 + 1
                    total_fr = max(f2 - f1 + 1, 1)
                    # Отправляем каждые every кадров
                    if cur != last_sent_frame and done % every == 0 and cur <= f2:
                        last_sent_frame = cur
                        pct = int(done / total_fr * 100)
                        elapsed = int(time.time() - _render_state['start_time'])
                        per_frame = elapsed / max(done, 1)
                        eta = int(per_frame * (total_fr - done))
                        m_e, s_e = divmod(elapsed, 60)
                        m_eta, s_eta = divmod(eta, 60)
                        filled = int(pct / 10)
                        bar = '█' * filled + '░' * (10 - filled)
                        s2 = get_notifier().settings
                        msg = (
                            '🖼 <b>ПРОГРЕСС РЕНДЕРА</b>\n'
                            '━━━━━━━━━━━━━━━━\n'
                            '📁 <b>Сцена:</b> <i>{scene}</i>\n'
                            '🎞 <b>Кадр:</b> <code>{cur} / {f2} ({pct}%)</code>\n'
                            '<code>[{bar}]</code>\n'
                            '⏱ <b>Прошло:</b> <code>{me}м {se}с</code>\n'
                            '🔮 <b>Осталось:</b> <code>{meta}м {seta}с</code>'
                        ).format(
                            scene=scene, cur=cur, f2=f2, pct=pct, bar=bar,
                            me=m_e, se=s_e, meta=m_eta, seta=s_eta
                        )
                        send_telegram(s2['bot_token'], s2.get('chat_ids', []), msg)
                except Exception:
                    pass
        threading.Thread(target=_progress_loop, daemon=True).start()

```

---

## Post-Render Script (завершение + превью)

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

## Post-Frame Script

> ⚠️ Octane не вызывает Post-Frame пофреймово — прогресс реализован через фоновый поток в Pre-Render скрипте (см. выше). Post-Frame Script не нужен.

---

## Пример сообщений

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

**Прогресс (каждые N кадров):**
```
🖼 ПРОГРЕСС РЕНДЕРА
━━━━━━━━━━━━━━━━
📁 Сцена: project_v04.hip
🎞 Кадр: 120 / 240 (50%)
[█████░░░░░]
⏱ Прошло: 22м 15с
🔮 Осталось: 22м 10с
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
⏱ Время рендера: 44м 30с
```
*(+ фото превью последнего кадра)*

---

## Команды бота

Включить в панели TG Notifier → **Enable bot polling**.

| Команда | Действие |
|---|---|
| `/status` | Статус рендера, кадр, время |
| `/stop` | Остановить рендер |
| `/help` | Список команд |

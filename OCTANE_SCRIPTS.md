# Octane ROP — Scripts for Telegram Notifier

Вставить в ноду `OctaneRenderSetup` → вкладка **Scripts** → тип **Python**.

---

## Pre-Render Script (старт рендера)

```python
import sys, os, time
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
        frames = '{} - {} ({} кадров)'.format(f1, f2, total)
    except:
        f1, f2, total = 1, 1, 1
        frames = 'unknown'

    try: out_path = node.parm('HO_img_fileName').eval()
    except: out_path = 'unknown'
    out_name = os.path.basename(out_path)

    # Сохраняем состояние рендера
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
    ).format(ts=ts, scene=scene, cam=cam, frames=frames, name=out_name, path=out_path)

    send_telegram(s['bot_token'], s.get('chat_ids', []), text)
```

---

## Post-Render Script (завершение рендера)

```python
import sys, os, time
_plugin = os.path.join(os.path.expanduser('~'), 'houdini_tg_notifier')
if _plugin not in sys.path:
    sys.path.insert(0, _plugin)
from tg_notifier import get_notifier, send_telegram, send_photo_telegram, _render_state, _resolve_path
from datetime import datetime
import hou as _hou

s = get_notifier().settings
if s.get('send_render', True):
    node = _hou.pwd()
    ts = datetime.now().strftime('%H:%M:%S')
    scene = os.path.basename(_hou.hipFile.name())

    try: out_path = node.parm('HO_img_fileName').eval()
    except: out_path = _render_state.get('out_path', 'unknown')
    out_name = os.path.basename(out_path)

    # Время рендера
    elapsed_str = ''
    if _render_state.get('start_time'):
        elapsed = int(time.time() - _render_state['start_time'])
        h, rem = divmod(elapsed, 3600)
        m, s_sec = divmod(rem, 60)
        if h > 0:
            elapsed_str = '\n⏱ <b>Время рендера:</b> <code>{}ч {}м {}с</code>'.format(h, m, s_sec)
        else:
            elapsed_str = '\n⏱ <b>Время рендера:</b> <code>{}м {}с</code>'.format(m, s_sec)

    # Сбрасываем состояние
    _render_state['active'] = False

    text = (
        '✅ <b>РЕНДЕР ЗАВЕРШЁН</b>\n'
        '━━━━━━━━━━━━━━━━\n'
        '🕐 <b>Время:</b> <code>{ts}</code>\n'
        '📁 <b>Сцена:</b> <i>{scene}</i>\n'
        '💾 <b>Файл:</b>  <code>{name}</code>\n'
        '📂 <b>Путь:</b>\n<code>{path}</code>{elapsed}'
    ).format(ts=ts, scene=scene, name=out_name, path=out_path, elapsed=elapsed_str)

    send_telegram(s['bot_token'], s.get('chat_ids', []), text)

    # Превью последнего кадра
    if s.get('send_preview', True):
        try:
            f2 = _render_state.get('f2', int(node.parm('f2').eval()))
            img_file = _resolve_path(out_path, f2)
            if img_file and os.path.exists(img_file):
                caption = '🖼 {} | {}'.format(out_name, scene)
                send_photo_telegram(s['bot_token'], s.get('chat_ids', []), img_file, caption)
        except Exception as e:
            print('[TG Notifier] Preview error:', e)
```

---

## Post-Frame Script (прогресс по кадрам)

```python
import sys, os
_plugin = os.path.join(os.path.expanduser('~'), 'houdini_tg_notifier')
if _plugin not in sys.path:
    sys.path.insert(0, _plugin)
from tg_notifier import get_notifier, send_telegram, _render_state
from datetime import datetime
import hou as _hou

s = get_notifier().settings
every = s.get('frame_progress_every', 10)
if not s.get('send_render', True) or every == 0:
    pass
else:
    node = _hou.pwd()
    try: frame = int(_hou.frame())
    except: frame = 0

    _render_state['current_frame'] = frame

    f1 = _render_state.get('f1', 1)
    f2 = _render_state.get('f2', frame)
    done = frame - f1 + 1
    total = max(f2 - f1 + 1, 1)
    pct = int(done / total * 100)

    if done % every == 0 or frame == f2:
        # Время на кадр и оставшееся
        elapsed_str = ''
        eta_str = ''
        if _render_state.get('start_time') and done > 0:
            elapsed = int(__import__('time').time() - _render_state['start_time'])
            per_frame = elapsed / done
            eta = int(per_frame * (total - done))
            m_e, s_e = divmod(elapsed, 60)
            m_eta, s_eta = divmod(eta, 60)
            elapsed_str = '\n⏱ <b>Прошло:</b> <code>{}м {}с</code>'.format(m_e, s_e)
            eta_str = '\n🔮 <b>Осталось:</b> <code>{}м {}с</code>'.format(m_eta, s_eta)

        # Прогресс-бар
        filled = int(pct / 10)
        bar = '█' * filled + '░' * (10 - filled)

        text = (
            '🖼 <b>ПРОГРЕСС РЕНДЕРА</b>\n'
            '━━━━━━━━━━━━━━━━\n'
            '📁 <b>Сцена:</b> <i>{scene}</i>\n'
            '🎞 <b>Кадр:</b> <code>{frame} / {f2} ({pct}%)</code>\n'
            '<code>[{bar}]</code>'
            '{elapsed}{eta}'
        ).format(
            scene=_render_state.get('scene', os.path.basename(_hou.hipFile.name())),
            frame=frame, f2=f2, pct=pct, bar=bar,
            elapsed=elapsed_str, eta=eta_str
        )
        send_telegram(s['bot_token'], s.get('chat_ids', []), text)
```

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

**Прогресс:**
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

Включить polling в панели TG Notifier → **Bot Polling** → On.

| Команда | Действие |
|---|---|
| `/status` | Статус рендера, кадр, время |
| `/stop` | Остановить рендер |
| `/help` | Список команд |

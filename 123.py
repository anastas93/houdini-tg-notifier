import hou, sys, os

_plugin = os.path.join(os.path.expanduser('~'), 'houdini_tg_notifier')
if _plugin not in sys.path:
    sys.path.insert(0, _plugin)

try:
    from tg_notifier import get_notifier
    _n = get_notifier()
    if _n.settings.get('monitor_enabled'):
        _n.start()
        print('[TG Notifier] Monitor started')
    else:
        print('[TG Notifier] Loaded (monitor off)')
except Exception as e:
    print('[TG Notifier] Load error:', e)


def _tgn_attach_octane_hooks():
    def _make_post_cb(node_path):
        def _cb(node, event_type, **kwargs):
            if event_type != hou.ropEventType.postRender:
                return
            try:
                from tg_notifier import get_notifier, send_telegram
                from datetime import datetime
                s = get_notifier().settings
                if not s.get('send_render', True): return
                ts = datetime.now().strftime('%H:%M:%S')
                scene = os.path.basename(hou.hipFile.name())
                try: out_path = node.parm('HO_img_fileName').eval()
                except: out_path = 'unknown'
                out_name = os.path.basename(out_path)
                text = '[OK] <b>OCTANE RENDER COMPLETE</b>\n<b>Time:</b> {}\n<b>Scene:</b> {}\n<b>ROP:</b> {}\n<b>Output:</b> {}\n<b>Path:</b> <code>{}</code>'.format(ts, scene, node_path, out_name, out_path)
                send_telegram(s['bot_token'], s.get('chat_ids', []), text)
            except Exception as e:
                print('[TG Notifier] postRender error:', e)
        return _cb

    def _make_pre_cb(node_path):
        def _cb(node, event_type, **kwargs):
            if event_type != hou.ropEventType.preRender:
                return
            try:
                from tg_notifier import get_notifier, send_telegram
                from datetime import datetime
                s = get_notifier().settings
                if not s.get('send_render', True): return
                ts = datetime.now().strftime('%H:%M:%S')
                scene = os.path.basename(hou.hipFile.name())
                try: cam = node.parm('HO_renderCamera').eval()
                except: cam = 'unknown'
                try:
                    f1 = int(node.parm('f1').eval())
                    f2 = int(node.parm('f2').eval())
                    f3 = node.parm('f3').eval()
                    total = int((f2 - f1) / f3) + 1
                    frames = '{} - {} ({} frames)'.format(f1, f2, total)
                except: frames = 'unknown'
                try: out_path = node.parm('HO_img_fileName').eval()
                except: out_path = 'unknown'
                out_name = os.path.basename(out_path)
                text = '[>>] <b>OCTANE RENDER STARTED</b>\n<b>Time:</b> {}\n<b>Scene:</b> {}\n<b>ROP:</b> {}\n<b>Camera:</b> {}\n<b>Frames:</b> {}\n<b>Output:</b> {}\n<b>Path:</b> <code>{}</code>'.format(ts, scene, node_path, cam, frames, out_name, out_path)
                send_telegram(s['bot_token'], s.get('chat_ids', []), text)
            except Exception as e:
                print('[TG Notifier] preRender error:', e)
        return _cb

    def _hook_all():
        for node in hou.node('/').allSubChildren():
            try:
                t = node.type().name().lower()
                if 'octanerendersetup' in t or 'octane_rop' in t:
                    node.addEventCallback((hou.ropEventType.postRender,), _make_post_cb(node.path()))
                    node.addEventCallback((hou.ropEventType.preRender,), _make_pre_cb(node.path()))
                    print('[TG Notifier] hooked:', node.path())
            except Exception:
                pass

    _hook_all()

    def _on_scene(event_type):
        if event_type in (hou.hipFileEventType.AfterLoad, hou.hipFileEventType.AfterMerge):
            _hook_all()
    try:
        hou.hipFile.addEventCallback(_on_scene)
    except Exception:
        pass

_tgn_attach_octane_hooks()
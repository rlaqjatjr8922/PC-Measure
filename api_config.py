import config

# None = required; request value wins; otherwise use this default.
mouse = {'click': {'x': None, 'y': None, 'options': {}},
 'double_click': {'x': None, 'y': None, 'options': {}},
 'right_click': {'x': None, 'y': None, 'options': {}},
 'hover': {'x': None, 'y': None, 'options': {}},
 'scroll': {'amount': None},
 'drag': {'start_x': None, 'start_y': None, 'end_x': None, 'end_y': None, 'options': {}},
 'position': {}}

keyboard = {'type': {'text': None, 'interval': 0},
 'hotkey': {'keys': None},
 'press': {'key': None},
 'hold': {'key': None},
 'release': {'key': None}}

window = {'list': {},
 'find': {'title': None},
 'focus': {'hwnd': None},
 'maximize': {'hwnd': None},
 'minimize': {'hwnd': None},
 'close': {'hwnd': None},
 'position': {'mode': {'get': {'hwnd': None},
                       'set': {'hwnd': None, 'x': None, 'y': None, 'width': None, 'height': None}}},
 'state': {'hwnd': None},
 'window': {'mode': {'list': {},
                     'find': {'title': None},
                     'activate': {'title': None},
                     'focus': {'title': None},
                     'maximize': {'title': None},
                     'minimize': {'title': None},
                     'close': {'title': None},
                     'move': {'title': None, 'x': None, 'y': None},
                     'resize': {'title': None, 'width': None, 'height': None},
                     'state': {'title': None}}}}

system = {'status': {},
 'info': {},
 'clipboard': {'mode': {'read': {}, 'write': {'text': None}}},
 'processes': {},
 'start_app': {'executable': None, 'args': []},
 'telemetry': {}}

files = {'open': {'path': None, 'options': {}},
 'save': {'path': None, 'options': {}, 'content': None},
 'read': {'path': None, 'options': {}},
 'create': {'path': None, 'options': {}, 'content': {'text': ''}, 'kind': 'file'},
 'edit': {'path': None, 'options': {}, 'content': None},
 'move': {'path': None, 'options': {}, 'destination': None},
 'copy': {'path': None, 'options': {}, 'destination': None},
 'rename': {'path': None, 'options': {}, 'name': None},
 'delete': {'path': None, 'options': {}},
 'list': {'path': None, 'options': {}},
 'info': {'path': None, 'options': {}}}

temp = {'current': {}}

screen = {'screenshot': {'mode': {'capture': {'target': {}}, 'save': {'target': {}}, 'read': {'screenshot_id': None}}},
 'marker': {'mode': {'add': {'screenshot_id': None, 'data': None},
                     'get': {'marker_id': None},
                     'list': {'screenshot_id': None},
                     'update': {'marker_id': None, 'data': None},
                     'delete': {'marker_id': None}}},
 'capture_monitor': {'monitor': None},
 'capture': {'mode': {'full': {'monitor': 1},
                      'window': {'window': None},
                      'region': {'monitor': 1, 'x': None, 'y': None, 'width': None, 'height': None}}},
 'monitors': {'mode': {'all': {}, 'monitor': {'monitor': 1}, 'windows': {}}}}

verify = {'hash': {'target': {}},
 'diff': {'mode': {'current': {'before_id': None, 'target': {}, 'tolerance': 0},
                   'saved': {'before_id': None, 'after_id': None, 'tolerance': 0}}},
 'wait_stable': {'target': {}, 'options': {}},
 'assert_changed': {'mode': {'current': {'before_id': None, 'target': {}, 'tolerance': 0},
                             'saved': {'before_id': None, 'after_id': None, 'tolerance': 0}}},
 'assert_unchanged': {'mode': {'current': {'before_id': None, 'target': {}, 'tolerance': 0},
                               'saved': {'before_id': None, 'after_id': None, 'tolerance': 0}}}}

mission = {'plan': {'mode': {'get': {}, 'write': {'text': None}}},
 'workflow': {'mode': {'get': {}, 'write': {'text': None, 'version': None}}},
 'run': {},
 'status': {'mode': {'get': {}, 'set': {'data': None}}},
 'cancel': {'reason': None},
 'work_log': {'mode': {'list': {}, 'add': {'entry': None}}}}

history = {'create': {'name': None}, 'select': {'mission_id': None}, 'load': {'mission_id': None}, 'list': {}}

macro = {'record': {'name': None, 'source': 'automation'},
 'stop': {},
 'replay': {'macro_id': None},
 'replay_with_verify': {'macro_id': None, 'verify': {}},
 'list': {}}

watch = {'start': {}, 'status': {'watch_id': None}, 'stop': {'watch_id': None}, 'list': {}}

interaction = {'ask_user': {'question': None, 'options': []},
 'status': {'question_id': None},
 'questions': {},
 'answer': {'question_id': None, 'answer': None}}

safety = {'kill_switch': {'reason': '사용자 중지'}}

input = {'mouse': {'mode': {'move': {'x': None, 'y': None, 'duration': 0},
                    'click': {'button': 'left', 'clicks': 1, 'interval': 0},
                    'drag': {'x': None, 'y': None, 'button': 'left', 'duration': 0.5},
                    'scroll': {'amount': None},
                    'position': {},
                    'hover': {'x': None, 'y': None, 'duration': 0},
                    'double_click': {'x': None, 'y': None},
                    'right_click': {'x': None, 'y': None}}},
 'keyboard': {'mode': {'type': {'text': None, 'interval': 0},
                       'key': {'key': None},
                       'press': {'key': None},
                       'hotkey': {'keys': None},
                       'hold': {'key': None},
                       'release': {'key': None}}}}

screen["capture"]["mode"]["full"]["monitor"] = config.screen["selected_monitor"]
screen["capture"]["mode"]["region"]["monitor"] = config.screen["selected_monitor"]
screen["monitors"]["mode"]["monitor"]["monitor"] = config.screen["selected_monitor"]

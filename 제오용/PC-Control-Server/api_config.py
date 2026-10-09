history = {'list': {'query': 'all', 'status': 'all'},
 'detail': {'mission_id': ...},
 'select': {'mission_id': ...},
 'delete': {'mission_id': ...},
 'create': {'title': ..., 'goal': ..., 'plan': ...},
 'edit': {'mission_id': ..., 'title': None, 'goal': None, 'plan': None}}

log = {'config': {'enabled': None,
            'save_request': None,
            'save_response': None,
            'save_error': None,
            'save_reject': None,
            'max_days': None},
 'view': {'limit': 100, 'mission_id': None, 'type': 'all'}}

mission = {'status': {},
 'step': {'direction': 1},
 'note': {'text': ..., 'scope': 'step'},
 'complete': {'result': '완료'},
 'reject': {'reason': ...}}


# history, log, mission 항목이 MCP 도구 목록에 자동 반영됩니다.
# 도구 이름은 <그룹>_<기능>이며, 항목을 삭제하면 목록과 실행 대상에서 제외됩니다.
# ...은 필수 입력, None은 선택 입력, 나머지는 기본값입니다.
# 기능 추가 시 plugins/<그룹>/<기능>.py에 run()을 구현하세요.
mission_descriptions = {
    'status': '현재 선택된 작업의 목표, 계획, 현재 단계, 결과와 메모를 조회합니다.',
    'step': '현재 작업의 단계를 이동합니다. -1은 이전 단계, 1은 다음 단계입니다.',
    'note': '현재 단계(step) 또는 작업 전체(mission)에 메모를 기록합니다.',
    'complete': '현재 단계 결과를 저장하고 완료 처리합니다. 다음 단계로 자동 이동하지 않습니다.',
    'reject': '요청을 거절한 사유를 현재 작업에 기록합니다.',
}


remote = {'status': {}}
remote_descriptions = {'status': 'Discord에서 최신 PC 주소를 확인하고 연결 상태를 반환합니다.'}

# Individual remote MCP tools. Ellipsis (...) = required; other values = defaults.
mouse = {'click': {'x': ..., 'y': ..., 'options': {}},
 'double_click': {'x': ..., 'y': ..., 'options': {}},
 'right_click': {'x': ..., 'y': ..., 'options': {}},
 'hover': {'x': ..., 'y': ..., 'options': {}},
 'scroll': {'amount': ...},
 'drag': {'start_x': ..., 'start_y': ..., 'end_x': ..., 'end_y': ..., 'options': {}},
 'position': {}}

keyboard = {'type': {'text': ..., 'interval': 0},
 'hotkey': {'keys': ...},
 'press': {'key': ...},
 'hold': {'key': ...},
 'release': {'key': ...}}

window = {'list': {},
 'find': {'title': ...},
 'focus': {'hwnd': ...},
 'maximize': {'hwnd': ...},
 'minimize': {'hwnd': ...},
 'close': {'hwnd': ...},
 'position': {'mode': {'get': {'hwnd': ...},
                       'set': {'hwnd': ...,
                               'x': ...,
                               'y': ...,
                               'width': ...,
                               'height': ...}}},
 'state': {'hwnd': ...},
 'window': {'mode': {'list': {},
                     'find': {'title': ...},
                     'activate': {'title': ...},
                     'focus': {'title': ...},
                     'maximize': {'title': ...},
                     'minimize': {'title': ...},
                     'close': {'title': ...},
                     'move': {'title': ..., 'x': ..., 'y': ...},
                     'resize': {'title': ..., 'width': ..., 'height': ...},
                     'state': {'title': ...}}}}

system = {'status': {},
 'info': {},
 'clipboard': {'mode': {'read': {}, 'write': {'text': ...}}},
 'processes': {},
 'start_app': {'executable': ..., 'args': []},
 'telemetry': {}}

files = {'open': {'path': ..., 'options': {}},
 'save': {'path': ..., 'options': {}, 'content': ...},
 'read': {'path': ..., 'options': {}},
 'create': {'path': ..., 'options': {}, 'content': {'text': ''}, 'kind': 'file'},
 'edit': {'path': ..., 'options': {}, 'content': ...},
 'move': {'path': ..., 'options': {}, 'destination': ...},
 'copy': {'path': ..., 'options': {}, 'destination': ...},
 'rename': {'path': ..., 'options': {}, 'name': ...},
 'delete': {'path': ..., 'options': {}},
 'list': {'path': ..., 'options': {}},
 'info': {'path': ..., 'options': {}}}

temp = {'current': {}}

screen = {'screenshot': {'mode': {'capture': {'target': {}},
                         'save': {'target': {}},
                         'read': {'screenshot_id': ...}}},
 'marker': {'mode': {'add': {'screenshot_id': ..., 'data': ...},
                     'get': {'marker_id': ...},
                     'list': {'screenshot_id': ...},
                     'update': {'marker_id': ..., 'data': ...},
                     'delete': {'marker_id': ...}}},
 'capture_monitor': {'monitor': ...},
 'capture': {'mode': {'full': {'monitor': 1},
                      'window': {'window': ...},
                      'region': {'monitor': 1,
                                 'x': ...,
                                 'y': ...,
                                 'width': ...,
                                 'height': ...}}},
 'monitors': {'mode': {'all': {}, 'monitor': {'monitor': 1}, 'windows': {}}}}

verify = {'hash': {'target': {}},
 'diff': {'mode': {'current': {'before_id': ..., 'target': {}, 'tolerance': 0},
                   'saved': {'before_id': ..., 'after_id': ..., 'tolerance': 0}}},
 'wait_stable': {'target': {}, 'options': {}},
 'assert_changed': {'mode': {'current': {'before_id': ..., 'target': {}, 'tolerance': 0},
                             'saved': {'before_id': ..., 'after_id': ..., 'tolerance': 0}}},
 'assert_unchanged': {'mode': {'current': {'before_id': ..., 'target': {}, 'tolerance': 0},
                               'saved': {'before_id': ..., 'after_id': ..., 'tolerance': 0}}}}

watch = {'start': {'condition': 'screen_changed', 'target': {}, 'options': {}}, 'status': {'watch_id': ...}, 'stop': {'watch_id': ...}, 'list': {}}

interaction = {'ask_user': {'question': ..., 'options': []},
 'status': {'question_id': ...},
 'questions': {},
 'answer': {'question_id': ..., 'answer': ...}}

safety = {'kill_switch': {'reason': '사용자 중지'}}

input = {'mouse': {'mode': {'move': {'x': ..., 'y': ..., 'duration': 0},
                    'click': {'button': 'left', 'clicks': 1, 'interval': 0},
                    'drag': {'x': ..., 'y': ..., 'button': 'left', 'duration': 0.5},
                    'scroll': {'amount': ...},
                    'position': {},
                    'hover': {'x': ..., 'y': ..., 'duration': 0},
                    'double_click': {'x': ..., 'y': ...},
                    'right_click': {'x': ..., 'y': ...}}},
 'keyboard': {'mode': {'type': {'text': ..., 'interval': 0},
                       'key': {'key': ...},
                       'press': {'key': ...},
                       'hotkey': {'keys': ...},
                       'hold': {'key': ...},
                       'release': {'key': ...}}}}

_mcp_excluded = set()

recording = {'config': {'scope': 'query', 'screenshot': 'query'}, 'list': {'start': 'all', 'end': 'all', 'limit': 200}}
macro = {'create': {'title': ..., 'start': ..., 'end': ...}, 'list': {}, 'run': {'macro_id': ...}}
system['powershell'] = {'command': ..., 'privilege': 'normal', 'timeout': 60}
recording_descriptions = {'config': 'PC 조작 로그 저장 범위(none/program/all) 및 실행 후 스크린샷을 설정합니다. all은 PC에서 직접 누른 키보드와 마우스도 기록합니다.', 'list': 'PC 조작 기록을 시간 범위로 조회합니다. ID, 시간, 입력값, 성공 여부를 포함합니다.'}
macro_descriptions = {'create': '시작(start)~종료(end) 구간의 기록을 제목(title)이 있는 매크로로 저장합니다. 시간대 포함 ISO 시간을 사용하세요.', 'list': '저장된 매크로 ID, 제목, 기간, 단계 수를 조회합니다.', 'run': 'macro_id로 선택한 매크로를 실제 실행합니다. 긴급 중지로 중단할 수 있습니다.'}
system_descriptions = {'powershell': 'PowerShell 명령을 normal(일반) 또는 admin(관리자, PC의 UAC 승인 필요) 권한으로 실행합니다.'}

# Keep the original route for compatibility; expose two explicit MCP tools.
_mcp_excluded.add('system_powershell')
_mcp_only = {'system_powershell_normal', 'system_powershell_admin'}
system['powershell_normal'] = {'command': ..., 'timeout': 60}
system['powershell_admin'] = {'command': ..., 'timeout': 60}
system_descriptions.update({
    'powershell_normal': 'PowerShell 명령을 일반 사용자 권한으로 실행합니다. command와 timeout(초)을 받습니다.',
    'powershell_admin': 'PowerShell 명령을 관리자 권한으로 실행합니다. 일반 권한 서버에서는 PC 사용자가 Windows UAC를 승인해야 합니다. command와 timeout(초)을 받습니다.',
})

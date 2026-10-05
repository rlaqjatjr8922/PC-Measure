# PC Measure

Windows PC 기능을 `/{group}/{feature}` GET/POST로 호출합니다.
기능 구현은 각 기능 파일 안에 있으며 서버 시작 시 작업 선택은 없습니다.

## 실행

```powershell
python -m pip install -r requirements.txt
python server.py
```

기본 주소: http://127.0.0.1:8010 (`config.py`에서 변경).
코드 변경 후 실행 중인 서버는 재시작해야 합니다.
필수 인자는 `api_config.py`에서 None으로 표시됩니다. mode가 여러 개면 mode를 지정합니다.
객체와 배열은 POST JSON 사용을 권장합니다. PNG는 이미지 응답으로 반환합니다.

## 저장 및 중지

임시 파일은 `data/tmp`, 캡처는 `data/screenshots`, 마커와 질문 및 중단 사유는
`.private/feature-state.sqlite3`에 저장합니다. 예전 저장 파일은 자동으로 삭제하거나 가져오지 않습니다.
긴급 중지는 입력을 중단하고 유지한 키·버튼 해제를 시도하며 대기 질문을 취소합니다.
중지 사유를 저장하고 해제 오류를 반환합니다. 재시작하면 중지 상태가 해제됩니다.
질문은 응답 전까지 pending이며 자동 승인하지 않습니다. 사용자 질문 UI는 포함되지 않습니다.
호출 통계는 요청 수·오류 수·누적 처리시간이며 서버 재시작 시 초기화됩니다.

## Watch

제공된 명세에 따라 start는 `WATCH_CONDITION_UNDEFINED`(409)를 반환합니다.
감시 조건이 정의되지 않았으므로 실제 자동 감시는 수행하지 않습니다.
list/status/stop 경로는 유지됩니다.

## 테스트

```powershell
python -m unittest discover -s tests -v
```

파일 처리는 임시 폴더에서, 화면과 입력 장치는 모의 환경에서 검증합니다.

## 제공 경로 (60개)

### mouse

- `/mouse/click`
- `/mouse/double_click`
- `/mouse/right_click`
- `/mouse/hover`
- `/mouse/scroll`
- `/mouse/drag`
- `/mouse/position`

### keyboard

- `/keyboard/type`
- `/keyboard/hotkey`
- `/keyboard/press`
- `/keyboard/hold`
- `/keyboard/release`

### window

- `/window/list`
- `/window/find`
- `/window/focus`
- `/window/maximize`
- `/window/minimize`
- `/window/close`
- `/window/position` — mode: get, set
- `/window/state`
- `/window/window` — mode: list, find, activate, focus, maximize, minimize, close, move, resize, state

### system

- `/system/status`
- `/system/info`
- `/system/clipboard` — mode: read, write
- `/system/processes`
- `/system/start_app`
- `/system/telemetry`

### files

- `/files/open`
- `/files/save`
- `/files/read`
- `/files/create`
- `/files/edit`
- `/files/move`
- `/files/copy`
- `/files/rename`
- `/files/delete`
- `/files/list`
- `/files/info`

### temp

- `/temp/current`

### screen

- `/screen/screenshot` — mode: capture, save, read
- `/screen/marker` — mode: add, get, list, update, delete
- `/screen/capture_monitor`
- `/screen/capture` — mode: full, window, region
- `/screen/monitors` — mode: all, monitor, windows

### verify

- `/verify/hash`
- `/verify/diff` — mode: current, saved
- `/verify/wait_stable`
- `/verify/assert_changed` — mode: current, saved
- `/verify/assert_unchanged` — mode: current, saved

### watch

- `/watch/start`
- `/watch/status`
- `/watch/stop`
- `/watch/list`

### interaction

- `/interaction/ask_user`
- `/interaction/status`
- `/interaction/questions`
- `/interaction/answer`

### safety

- `/safety/kill_switch`

### input

- `/input/mouse` — mode: move, click, drag, scroll, position, hover, double_click, right_click
- `/input/keyboard` — mode: type, key, press, hotkey, hold, release


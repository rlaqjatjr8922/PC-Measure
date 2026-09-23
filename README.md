# PC-Control-Server

Windows PC 조작 기능을 `/{group}/{feature}` 형태로 제공하는 개인용 로컬 서버입니다.

## 설치 및 실행

프로젝트 폴더에서 실행합니다.

```powershell
python -m pip install -r requirements.txt
python server.py
```

`server.py`를 직접 실행하면 Uvicorn을 시작하기 전에 터미널에서 Mission을 선택합니다.

## Mission 선택

저장된 작업이 있을 때의 화면 예시입니다. 아래 이름의 작업을 자동으로 생성하지는 않습니다.

```text
========================================
 PC-Control-Server
========================================

작업을 선택하세요.

1. 그래픽카드 수리
2. Inventory 개발
3. PC-Control-Server 개발
0. 새 작업

선택 >
```

- 기존 작업 번호: 해당 Mission을 선택하고 저장된 계획서·진행상황·작업기록을 불러옵니다.
- `0`: 새 작업 이름을 입력받아 Mission을 생성하고 선택합니다.
- 저장된 작업이 없으면 `0. 새 작업`만 표시합니다.
- 잘못된 번호 또는 빈 입력은 다시 입력받습니다.
- 새 작업 이름은 앞뒤 공백을 제외하고 1~120자여야 합니다.
- 선택 중 `Ctrl+C` 또는 입력 종료(EOF)가 발생하면 서버를 시작하지 않고 종료합니다.

선택이 완료되면 작업 이름을 표시하고 Uvicorn을 시작합니다.

```text
선택한 작업: Inventory 개발
```

기본 서버 주소는 `http://127.0.0.1:8002`이며 `config.py`의 `HOST`, `PORT`를 사용합니다.

## 실행 순서

```text
python server.py
→ 저장된 Mission 목록 조회
→ 사용자 선택 또는 새 작업 생성
→ 현재 Mission 설정 및 데이터 불러오기
→ Uvicorn 시작
→ API 요청 대기
```

Mission 선택은 서버 시작 전에 사용자가 직접 합니다. GPT 실행·연결은 포함되어 있지 않으며, 계획의 자동 실행도 시작하지 않습니다.

터미널 선택 절차는 `python server.py`로 직접 실행할 때 적용됩니다. 모듈을 import하거나 `uvicorn server:app`으로 실행하면 이 절차를 거치지 않습니다.

## API 호출과 선택 상태

기존 `/{group}/{feature}` 호출 구조와 `api_config.py`의 등록·필수값·기본값 검사는 유지됩니다. PNG/JPEG bytes는 이미지로, 일반 결과는 JSON으로 반환합니다.

터미널에서 Mission을 선택해도 기존 API의 헤더 검사는 유지됩니다. 현재 구현에서 사용자 클라이언트는 서버 내부 `.private/user.key` 값을 `X-User-Key` 헤더에 사용하며, 실행 연결은 사용자 선택 API 응답의 `context_id`를 `X-Mission-Context` 헤더에 사용합니다. 터미널은 키나 연결값을 출력하지 않습니다. 인증정보를 GPT에게 전달하지 않습니다.

## 저장 및 검증

Mission 데이터는 `.private/state.sqlite3`에 저장됩니다. 서버를 다시 실행하면 사용자가 사용할 Mission을 다시 선택합니다.

기존 API 통합 테스트:

```powershell
python -m unittest discover -s tests -v
```

터미널 시작 흐름은 별도로 기존 작업 선택, 새 작업 생성, 잘못된 입력, EOF, `Ctrl+C`를 대체 입력으로 검증했습니다.

## 전체 기능 및 엔드포인트

아래는 실제 `api_config.py`에 등록된 **75개 경로 전체**입니다. GET/POST를 지원하며 객체·배열 인자는 POST JSON으로 전달합니다. `필수`는 기본값이 없어 반드시 입력해야 하는 값이고, 나머지는 미입력 시 기본값입니다. mode가 여러 개면 반드시 mode를 지정합니다.

### 마우스 (`mouse`)

좌표는 Windows 가상 데스크톱의 물리 픽셀입니다. options는 duration(초), interval(초), button(left/right/middle), clicks를 받으며 동작별로 적용됩니다. scroll의 amount는 양수 위 / 음수 아래입니다.

| 엔드포인트 | 기능 | mode | 호출값 / 기본값 |
|---|---|---|---|
| `/mouse/click` | 지정 좌표 클릭 | `—` | `x=필수, y=필수, options={}` |
| `/mouse/double_click` | 지정 좌표 더블클릭 | `—` | `x=필수, y=필수, options={}` |
| `/mouse/right_click` | 지정 좌표 우클릭 | `—` | `x=필수, y=필수, options={}` |
| `/mouse/hover` | 지정 좌표 이동 / 호버 | `—` | `x=필수, y=필수, options={}` |
| `/mouse/scroll` | 스크롤 | `—` | `amount=필수` |
| `/mouse/drag` | 시작 좌표에서 끝 좌표까지 드래그 | `—` | `start_x=필수, start_y=필수, end_x=필수, end_y=필수, options={}` |
| `/mouse/position` | 현재 마우스 좌표 조회 | `—` | `없음` |

### 키보드 (`keyboard`)

keys는 문자열 배열 또는 쉼표로 구분한 키 이름입니다. type의 interval은 글자 사이 대기시간(초)입니다. 중지 시 유지 중인 키를 해제합니다.

| 엔드포인트 | 기능 | mode | 호출값 / 기본값 |
|---|---|---|---|
| `/keyboard/type` | 한글·Unicode 텍스트 입력 | `—` | `text=필수, interval=0` |
| `/keyboard/hotkey` | 조합 단축키 입력 | `—` | `keys=필수` |
| `/keyboard/press` | 단일 키 입력 | `—` | `key=필수` |
| `/keyboard/hold` | 키를 누른 상태로 유지 | `—` | `key=필수` |
| `/keyboard/release` | 누른 키 해제 | `—` | `key=필수` |

### Window 관리 (`window`)

새 API는 hwnd를 사용합니다. find는 제목 부분 일치 결과 목록을 반환합니다. 기존 window/window는 제목이 정확히 일치하는 창 하나를 대상으로 합니다. close는 닫기 요청을 전달하며 저장 대화상자는 자동 처리하지 않습니다.

| 엔드포인트 | 기능 | mode | 호출값 / 기본값 |
|---|---|---|---|
| `/window/list` | 열린 창 목록 | `—` | `없음` |
| `/window/find` | 제목으로 창 검색 | `—` | `title=필수` |
| `/window/focus` | 특정 창 활성화 | `—` | `hwnd=필수` |
| `/window/maximize` | 창 최대화 | `—` | `hwnd=필수` |
| `/window/minimize` | 창 최소화 | `—` | `hwnd=필수` |
| `/window/close` | 창 닫기 요청 | `—` | `hwnd=필수` |
| `/window/position` | 창 위치·크기 조회 / 변경 | `get` | `hwnd=필수` |
| `/window/position` | 창 위치·크기 조회 / 변경 | `set` | `hwnd=필수, x=필수, y=필수, width=필수, height=필수` |
| `/window/state` | 창 존재·활성화·최소화·최대화 상태 | `—` | `hwnd=필수` |
| `/window/window` | 기존 title 기반 Window 호출 | `list` | `없음` |
| `/window/window` | 기존 title 기반 Window 호출 | `find` | `title=필수` |
| `/window/window` | 기존 title 기반 Window 호출 | `activate` | `title=필수` |
| `/window/window` | 기존 title 기반 Window 호출 | `focus` | `title=필수` |
| `/window/window` | 기존 title 기반 Window 호출 | `maximize` | `title=필수` |
| `/window/window` | 기존 title 기반 Window 호출 | `minimize` | `title=필수` |
| `/window/window` | 기존 title 기반 Window 호출 | `close` | `title=필수` |
| `/window/window` | 기존 title 기반 Window 호출 | `move` | `title=필수, x=필수, y=필수` |
| `/window/window` | 기존 title 기반 Window 호출 | `resize` | `title=필수, width=필수, height=필수` |
| `/window/window` | 기존 title 기반 Window 호출 | `state` | `title=필수` |

### 프로그램 / 시스템 (`system`)

start_app의 executable은 실행 파일 경로, args는 문자열 배열입니다. clipboard는 텍스트만 지원합니다. telemetry는 집계 통계이며 서버 로그 조회가 아닙니다.

| 엔드포인트 | 기능 | mode | 호출값 / 기본값 |
|---|---|---|---|
| `/system/status` | 서버·Mission 선택·중지 상태 | `—` | `없음` |
| `/system/info` | OS·Python·CPU 등 환경 정보 | `—` | `없음` |
| `/system/clipboard` | 텍스트 클립보드 읽기 / 쓰기 | `read` | `없음` |
| `/system/clipboard` | 텍스트 클립보드 읽기 / 쓰기 | `write` | `text=필수` |
| `/system/processes` | 실행 프로세스 목록 | `—` | `없음` |
| `/system/start_app` | 프로그램 실행 | `—` | `executable=필수, args=[]` |
| `/system/telemetry` | 호출 수·오류 수·누적 처리시간 | `—` | `없음` |

### 파일 관리 (`files`)

content는 {"text":"내용","encoding":"utf-8"} 또는 {"base64":"..."}입니다. 빈 파일은 {"text":""}로 저장합니다. options는 overwrite, recursive, encoding, offset, limit, expected_hash를 지원하며 해당 기능에서만 적용됩니다. overwrite/recursive는 기본 false입니다. read는 기본 1MB, 최대 32MB이며 저장도 한 번에 최대 32MB입니다. edit의 expected_hash는 선택적 내용 충돌 검사입니다. kind는 file/directory입니다.

| 엔드포인트 | 기능 | mode | 호출값 / 기본값 |
|---|---|---|---|
| `/files/open` | 연결 프로그램으로 파일 열기 | `—` | `path=필수, options={}` |
| `/files/save` | 파일 내용 저장 | `—` | `path=필수, options={}, content=필수` |
| `/files/read` | 파일 내용 읽기 | `—` | `path=필수, options={}` |
| `/files/create` | 파일 / 폴더 생성 | `—` | `path=필수, options={}, content={"text": ""}, kind="file"` |
| `/files/edit` | 기존 파일 내용 수정 | `—` | `path=필수, options={}, content=필수` |
| `/files/move` | 파일 / 폴더 이동 | `—` | `path=필수, options={}, destination=필수` |
| `/files/copy` | 파일 / 폴더 복사 | `—` | `path=필수, options={}, destination=필수` |
| `/files/rename` | 이름 변경 | `—` | `path=필수, options={}, name=필수` |
| `/files/delete` | 파일 / 폴더 삭제 | `—` | `path=필수, options={}` |
| `/files/list` | 폴더 내용 목록 | `—` | `path=필수, options={}` |
| `/files/info` | 파일 / 폴더 정보 | `—` | `path=필수, options={}` |

### GPT 임시폴더 (`temp`)

temp:/파일명 경로를 files API에 전달하면 현재 Mission의 tmp 폴더를 사용합니다. 파일 생성·읽기·수정·저장·이동·복사·이름 변경·삭제·목록은 일반 파일 API를 그대로 이용합니다. 별도 결과물 생성 API는 없습니다.

| 엔드포인트 | 기능 | mode | 호출값 / 기본값 |
|---|---|---|---|
| `/temp/current` | 현재 Mission 임시폴더 경로 조회 / 준비 | `—` | `없음` |

### 화면 / 마커 (`screen`)

screenshot target은 {}, {"monitor":0}(전체 화면), {"monitor":1}, {"hwnd":창번호}, {"region":{"x":0,"y":0,"width":640,"height":480}} 중 하나입니다. capture/read는 원본 PNG bytes, save는 screenshot ID·영역·hash·이미지 조회 URL을 반환합니다. marker data는 {"x":10,"y":20,"annotation":"메모"}이며 update는 일부 필드만 보낼 수 있습니다. 마커 좌표는 원본 이미지 내부 픽셀입니다. 원본 이미지와 마커를 분리 저장하며 이미지에 주석을 합성하지 않습니다. 주석창 열기/닫기는 이번 서버 구현에 포함되지 않은 UI 기능입니다. 기존 capture region의 x/y는 선택 모니터 기준 좌표입니다.

| 엔드포인트 | 기능 | mode | 호출값 / 기본값 |
|---|---|---|---|
| `/screen/screenshot` | 실제 이미지 캡처 / 저장 / 읽기 | `capture` | `target={}` |
| `/screen/screenshot` | 실제 이미지 캡처 / 저장 / 읽기 | `save` | `target={}` |
| `/screen/screenshot` | 실제 이미지 캡처 / 저장 / 읽기 | `read` | `screenshot_id=필수` |
| `/screen/marker` | 마커 추가 / 조회 / 수정 / 삭제 | `add` | `screenshot_id=필수, data=필수` |
| `/screen/marker` | 마커 추가 / 조회 / 수정 / 삭제 | `get` | `marker_id=필수` |
| `/screen/marker` | 마커 추가 / 조회 / 수정 / 삭제 | `list` | `screenshot_id=필수` |
| `/screen/marker` | 마커 추가 / 조회 / 수정 / 삭제 | `update` | `marker_id=필수, data=필수` |
| `/screen/marker` | 마커 추가 / 조회 / 수정 / 삭제 | `delete` | `marker_id=필수` |
| `/screen/capture_monitor` | 기본 캡처 모니터 변경 | `—` | `monitor=필수` |
| `/screen/capture` | 기존 모니터·창·영역 캡처 | `full` | `monitor=1` |
| `/screen/capture` | 기존 모니터·창·영역 캡처 | `window` | `window=필수` |
| `/screen/capture` | 기존 모니터·창·영역 캡처 | `region` | `monitor=1, x=필수, y=필수, width=필수, height=필수` |
| `/screen/monitors` | 모니터 또는 창 목록 조회 | `all` | `없음` |
| `/screen/monitors` | 모니터 또는 창 목록 조회 | `monitor` | `monitor=1` |
| `/screen/monitors` | 모니터 또는 창 목록 조회 | `windows` | `없음` |

### 화면 상태 검증 (`verify`)

tolerance는 픽셀 채널 차이 허용값(0~255, 기본 0)입니다. 캡처 영역이 다르면 비교를 거절합니다. wait_stable options는 interval(기본 .2초), stable_for(기본 1초), max_wait(기본 10초), tolerance(기본 0)입니다. 한도 초과는 stable=false, 검증 조건 불일치는 passed=false로 구분합니다. 자동 재시도·복구는 하지 않습니다.

| 엔드포인트 | 기능 | mode | 호출값 / 기본값 |
|---|---|---|---|
| `/verify/hash` | 현재 캡처의 픽셀 hash 생성 | `—` | `target={}` |
| `/verify/diff` | 저장된 화면 또는 현재 화면과 차이 비교 | `current` | `before_id=필수, target={}, tolerance=0` |
| `/verify/diff` | 저장된 화면 또는 현재 화면과 차이 비교 | `saved` | `before_id=필수, after_id=필수, tolerance=0` |
| `/verify/wait_stable` | 화면 변화가 안정될 때까지 확인 | `—` | `target={}, options={}` |
| `/verify/assert_changed` | 화면 변경 여부 검증 | `current` | `before_id=필수, target={}, tolerance=0` |
| `/verify/assert_changed` | 화면 변경 여부 검증 | `saved` | `before_id=필수, after_id=필수, tolerance=0` |
| `/verify/assert_unchanged` | 화면 유지 여부 검증 | `current` | `before_id=필수, target={}, tolerance=0` |
| `/verify/assert_unchanged` | 화면 유지 여부 검증 | `saved` | `before_id=필수, after_id=필수, tolerance=0` |

### Mission (`mission`)

현재 연결된 Mission만 사용하며 다른 Mission ID를 입력받지 않습니다. workflow write는 최신 version이 필요합니다. status data에는 current_step, completed_steps(배열), current_action, state(running/completed)를 저장합니다. work_log entry에는 수행한 작업·결과·성공/실패·검증·측정·오류·재시도·사용/생성 파일·최종 결과 등을 자유로운 JSON 객체로 기록합니다. status가 checkpoint 역할을 하며 별도 checkpoint API는 없습니다.

| 엔드포인트 | 기능 | mode | 호출값 / 기본값 |
|---|---|---|---|
| `/mission/plan` | 계획서 조회 / 최초 작성 | `get` | `없음` |
| `/mission/plan` | 계획서 조회 / 최초 작성 | `write` | `text=필수` |
| `/mission/workflow` | 기존 계획서 조회 / 버전 확인 후 수정 | `get` | `없음` |
| `/mission/workflow` | 기존 계획서 조회 / 버전 확인 후 수정 | `write` | `text=필수, version=필수` |
| `/mission/run` | 현재 Mission 실행 상태 시작; 행동 자동 생성 없음 | `—` | `없음` |
| `/mission/status` | 진행상황 조회 / 저장 | `get` | `없음` |
| `/mission/status` | 진행상황 조회 / 저장 | `set` | `data=필수` |
| `/mission/cancel` | Mission 중단 및 사유 기록 | `—` | `reason=필수` |
| `/mission/work_log` | 작업기록 추가 / 조회 | `list` | `없음` |
| `/mission/work_log` | 작업기록 추가 / 조회 | `add` | `entry=필수` |

### Mission 선택 / History (`history`)

모든 history API는 사용자 전용입니다. create/select는 Mission 데이터, 작업기록, context_id를 반환하며 GPT가 임의로 선택하지 않습니다. 실행 중인 Mission은 완료/중단 후 전환합니다. 데이터는 서버 재시작 후에도 유지됩니다.

| 엔드포인트 | 기능 | mode | 호출값 / 기본값 |
|---|---|---|---|
| `/history/create` | 사용자가 새 Mission 생성 및 선택 | `—` | `name=필수` |
| `/history/select` | 사용자가 기존 Mission 선택 | `—` | `mission_id=필수` |
| `/history/load` | 저장된 Mission과 작업기록 불러오기 | `—` | `mission_id=필수` |
| `/history/list` | 저장된 Mission 목록 | `—` | `없음` |

### Macro (`macro`)

source는 automation(기본), user, both입니다. record~stop 구간의 입력을 기록하며 재생 중에는 기록하지 않습니다. replay_with_verify의 verify는 {"target":{},"expect":"changed","tolerance":0} 형식입니다. expect는 changed/unchanged입니다. 저장된 입력을 그대로 재생하며 실패 후 자동으로 재시도하지 않습니다.

| 엔드포인트 | 기능 | mode | 호출값 / 기본값 |
|---|---|---|---|
| `/macro/record` | 사용자 / 자동화 입력 기록 시작 | `—` | `name=필수, source="automation"` |
| `/macro/stop` | 기록 중지 및 저장 | `—` | `없음` |
| `/macro/replay` | 기록된 매크로 재생 | `—` | `macro_id=필수` |
| `/macro/replay_with_verify` | 재생 후 화면 변화 검증 | `—` | `macro_id=필수, verify={}` |
| `/macro/list` | 현재 Mission 매크로 목록 | `—` | `없음` |

### Watch (`watch`)

수명주기용 경로만 등록한 상태입니다. 조건이 아직 정해지지 않아 start는 WATCH_CONDITION_UNDEFINED를 반환합니다. 실제 감시 기능이 동작한다고 표시하지 않으며 파일 변경·창 등장 등 조건을 임의로 추가하지 않았습니다.

| 엔드포인트 | 기능 | mode | 호출값 / 기본값 |
|---|---|---|---|
| `/watch/start` | 조건 미확정: 현재 409 오류 반환 | `—` | `없음` |
| `/watch/status` | 저장된 Watch 상태 조회; 현재 생성 가능한 Watch 없음 | `—` | `watch_id=필수` |
| `/watch/stop` | 저장된 Watch 중지; 현재 생성 가능한 Watch 없음 | `—` | `watch_id=필수` |
| `/watch/list` | 현재 Mission Watch 목록; 현재 빈 목록 | `—` | `없음` |

### 사용자 질문 / 답변 (`interaction`)

ask_user는 pending 질문을 생성합니다. 사용자 클라이언트가 questions로 조회하고 answer로 답변하면 status에서 답변을 조회합니다. 사용자 UI와 GPT에 답변을 전달하는 연결부는 별도 작업입니다. 무응답을 승인으로 처리하지 않으며 중지 시 대기 질문을 취소합니다. questions/answer는 사용자 전용입니다.

| 엔드포인트 | 기능 | mode | 호출값 / 기본값 |
|---|---|---|---|
| `/interaction/ask_user` | 사용자 질문 생성 | `—` | `question=필수, options=[]` |
| `/interaction/status` | 질문 상태 / 답변 조회 | `—` | `question_id=필수` |
| `/interaction/questions` | 사용자용 질문 목록 조회 | `—` | `없음` |
| `/interaction/answer` | 사용자 답변 저장 | `—` | `question_id=필수, answer=필수` |

### Safety (`safety`)

중지 상태를 먼저 설정하고 입력·드래그·매크로·검증 대기에서 이를 확인합니다. 대기 질문과 입력 기록도 종료합니다. 이미 OS에 전달된 단일 동작이나 진행 중인 파일 시스템 호출을 되돌리는 기능은 아닙니다. 키·버튼 정리 실패는 input_release_error에 표시합니다. BYPASS_HITL은 config.py 설정으로 유지하되 질문 자동 승인이나 중지 무시에 사용하지 않습니다.

| 엔드포인트 | 기능 | mode | 호출값 / 기본값 |
|---|---|---|---|
| `/safety/kill_switch` | 자동 작업 중지, 키·버튼 정리, 중단 사유 저장 | `—` | `reason="사용자 중지"` |

### 기존 입력 API 호환 (`input`)

기존 input/mouse의 click은 현재 위치 클릭, drag는 현재 위치부터 지정 좌표까지 드래그입니다. 지정 좌표 클릭과 시작/끝 드래그는 mouse 그룹을 사용합니다. input/keyboard의 key는 press 호환 이름입니다.

| 엔드포인트 | 기능 | mode | 호출값 / 기본값 |
|---|---|---|---|
| `/input/mouse` | 기존 mode 기반 마우스 조작 | `move` | `x=필수, y=필수, duration=0` |
| `/input/mouse` | 기존 mode 기반 마우스 조작 | `click` | `button="left", clicks=1, interval=0` |
| `/input/mouse` | 기존 mode 기반 마우스 조작 | `drag` | `x=필수, y=필수, button="left", duration=0.5` |
| `/input/mouse` | 기존 mode 기반 마우스 조작 | `scroll` | `amount=필수` |
| `/input/mouse` | 기존 mode 기반 마우스 조작 | `position` | `없음` |
| `/input/mouse` | 기존 mode 기반 마우스 조작 | `hover` | `x=필수, y=필수, duration=0` |
| `/input/mouse` | 기존 mode 기반 마우스 조작 | `double_click` | `x=필수, y=필수` |
| `/input/mouse` | 기존 mode 기반 마우스 조작 | `right_click` | `x=필수, y=필수` |
| `/input/keyboard` | 기존 mode 기반 키보드 조작 | `type` | `text=필수, interval=0` |
| `/input/keyboard` | 기존 mode 기반 키보드 조작 | `key` | `key=필수` |
| `/input/keyboard` | 기존 mode 기반 키보드 조작 | `press` | `key=필수` |
| `/input/keyboard` | 기존 mode 기반 키보드 조작 | `hotkey` | `keys=필수` |
| `/input/keyboard` | 기존 mode 기반 키보드 조작 | `hold` | `key=필수` |
| `/input/keyboard` | 기존 mode 기반 키보드 조작 | `release` | `key=필수` |

## 공통 응답 및 로그

일반 응답은 `{ "success": true, "group": "...", "feature": "...", "result": ... }`, 오류는 `{ "success": false, "error": ... }`입니다. 이미지 bytes는 실제 이미지 응답으로 반환합니다. 요청 식별자는 `X-Request-ID` 응답 헤더에 들어갑니다.

서버 요청 로그는 `.private/server.jsonl`에 저장하며 Mission work_log와 분리합니다. timestamp, request_id, HTTP method, path, parameters/body, response/result, HTTP status, duration, exception/error를 기록합니다. 큰 본문과 바이너리는 원문 대신 크기·생략 정보를 남기고, 인증 필드와 서버 사용자 키를 마스킹합니다. 서버 로그 조회·검색·다운로드·수정·삭제 API는 제공하지 않습니다.

파일 API는 서버 프로젝트·내부 저장소 접근을 차단하고 현재 Mission tmp만 허용합니다. 다만 같은 Windows 계정의 프로그램·터미널·화면 조작을 통한 로그/비밀 접근까지 절대 차단하는 OS 권한 격리는 아직 구현되지 않았습니다. 화면·클립보드·자유 텍스트·입력 기록에 섞인 임의 비밀번호를 자동 식별하는 기능도 없습니다.

## 포함하지 않은 기능 및 남은 연결

- 사용자 화면 UI, 마커 주석창, GPT 실행/연결은 포함하지 않았습니다. 시작 시 터미널 Mission 선택만 제공합니다.
- Watch 실제 감시는 조건 확정 전까지 구현하지 않습니다.
- 보류: UI 요소 직접 제어, 브라우저 전용 조작, 외부 앱/서비스 연동, notify, 이미지/파일 클립보드 및 클립보드 비우기 전용 기능.
- 제외: Dialog 전용 API, App Shortcut Actions, Desktop State Discovery, OCR, UI 요소 자동 인식·검색, 이미지 매칭, highlight, assert_template, assert_text, 서버 자동 오류 복구, Mission pause/resume/timeout, 별도 checkpoint, 결과물 생성 API.
- 실제 Windows 프로그램별 입력·캡처 동작 검증과 OS 권한 격리는 남아 있습니다.

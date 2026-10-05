# MCP 구현 결과

총 74개 도구. remote_call 등록과 plugins/remote/call.py 삭제. /remote/call은 404. History/Log/Mission 보존.

## 전체 도구 → API 매핑

| Tool | API | mode |
|---|---|---|
| history_list | /history/list |  |
| history_detail | /history/detail |  |
| history_select | /history/select |  |
| history_delete | /history/delete |  |
| history_create | /history/create |  |
| history_edit | /history/edit |  |
| log_config | /log/config |  |
| log_view | /log/view |  |
| mission_status | /mcp/mission/status |  |
| mission_step | /mcp/mission/step |  |
| mission_note | /mcp/mission/note |  |
| mission_complete | /mcp/mission/complete |  |
| mission_reject | /mcp/mission/reject |  |
| remote_status | /system/status |  |
| mouse_click | /mouse/click |  |
| mouse_double_click | /mouse/double_click |  |
| mouse_right_click | /mouse/right_click |  |
| mouse_hover | /mouse/hover |  |
| mouse_scroll | /mouse/scroll |  |
| mouse_drag | /mouse/drag |  |
| mouse_position | /mouse/position |  |
| keyboard_type | /keyboard/type |  |
| keyboard_hotkey | /keyboard/hotkey |  |
| keyboard_press | /keyboard/press |  |
| keyboard_hold | /keyboard/hold |  |
| keyboard_release | /keyboard/release |  |
| window_list | /window/list |  |
| window_find | /window/find |  |
| window_focus | /window/focus |  |
| window_maximize | /window/maximize |  |
| window_minimize | /window/minimize |  |
| window_close | /window/close |  |
| window_position | /window/position | get, set |
| window_state | /window/state |  |
| window_window | /window/window | list, find, activate, focus, maximize, minimize, close, move, resize, state |
| system_status | /system/status |  |
| system_info | /system/info |  |
| system_clipboard | /system/clipboard | read, write |
| system_processes | /system/processes |  |
| system_start_app | /system/start_app |  |
| system_telemetry | /system/telemetry |  |
| files_open | /files/open |  |
| files_save | /files/save |  |
| files_read | /files/read |  |
| files_create | /files/create |  |
| files_edit | /files/edit |  |
| files_move | /files/move |  |
| files_copy | /files/copy |  |
| files_rename | /files/rename |  |
| files_delete | /files/delete |  |
| files_list | /files/list |  |
| files_info | /files/info |  |
| temp_current | /temp/current |  |
| screen_screenshot | /screen/screenshot | capture, save, read |
| screen_marker | /screen/marker | add, get, list, update, delete |
| screen_capture_monitor | /screen/capture_monitor |  |
| screen_capture | /screen/capture | full, window, region |
| screen_monitors | /screen/monitors | all, monitor, windows |
| verify_hash | /verify/hash |  |
| verify_diff | /verify/diff | current, saved |
| verify_wait_stable | /verify/wait_stable |  |
| verify_assert_changed | /verify/assert_changed | current, saved |
| verify_assert_unchanged | /verify/assert_unchanged | current, saved |
| watch_start | /watch/start |  |
| watch_status | /watch/status |  |
| watch_stop | /watch/stop |  |
| watch_list | /watch/list |  |
| interaction_ask_user | /interaction/ask_user |  |
| interaction_status | /interaction/status |  |
| interaction_questions | /interaction/questions |  |
| interaction_answer | /interaction/answer |  |
| safety_kill_switch | /safety/kill_switch |  |
| input_mouse | /input/mouse | move, click, drag, scroll, position, hover, double_click, right_click |
| input_keyboard | /input/keyboard | type, key, press, hotkey, hold, release |

## 주소 갱신

개별 도구 → 30초 TTL resolver → Discord 최근 1000개 이내 최신 0001 URL → PC Measure. 정상 응답 주소는 data/remote/endpoint_cache.json에 저장. Discord 장애 시 마지막 주소 사용. 연결 실패 시 강제 조회 후 다른 주소로 한 번 재시도. 중복 실행을 막기 위해 응답 시간 초과와 HTTP 서버 오류는 재실행하지 않습니다.

## 환경변수

- DISCORD_BOT_TOKEN: 읽기용 봇 토큰
- DISCORD_CHANNEL_ID: 원격제어 채널 ID
- REMOTE_PC_CODE: 기본 0001

봇은 채널 보기/메시지 기록 보기 권한과 Message Content Intent가 필요합니다. 전송 웹훅과 별도입니다. [Discord 공식 문서](https://github.com/discord/discord-api-docs/blob/main/developers/resources/message.mdx)

## 재시작과 테스트

환경변수 설정 후 기존 서버를 Ctrl+C로 종료하고 새 터미널에서 실행:

```powershell
cd C:\tast\PC-Control-Server
python server.py
python -m unittest discover -s tests -v
```

MCP: http://127.0.0.1:8002/mcp. ChatGPT에는 이 서버의 공개 HTTPS /mcp 주소로 연결 후 도구 목록 새로고침.

## 결과

자동 테스트 14개 통과: 개별 도구 96개 mode 조합, REST GET/POST 120개 조합 포함. 실제 JSON-RPC tools/list는 74개. remote_status 실제 호출은 Discord 설정 필요 반환. 스크린샷의 최신 URL을 테스트에서만 지정한 system_status 실제 원격 호출은 server=running, stopped=false. 입력/파일 변경 기능은 모의 응답으로 검증.

## 추가·복구 파일

measure_tools.py, remote_client.py, remote_routes.py, remote/client.py, remote/resolver.py, remote/status.py, plugins/discord/client.py, reader.py, parser.py, cache.py, tests/test_discord.py, MCP_IMPLEMENTATION.md. 개별 mcp 파일은 기존 구조 유지.

삭제: plugins/remote/call.py 및 call 바이트코드 캐시.

## 전체 트리

```
api.py
api_config.py
config.py
data/
data/history/
data/history/current.json
data/history/d1acbefbe79c.json
data/log_config.json
data/logs/
data/logs/.gitkeep
data/logs/013641d258da44d5b1cc4d654c4494fc.json
data/logs/0155efd1dc0e4eb7be4858aff0b067a2.json
data/logs/07735b1a602f4009bde059640e91a40c.json
data/logs/091c21fcaeb54d7b8403c951afe9b8ee.json
data/logs/0a3bd48770ae4c44882c0298d0687f58.json
data/logs/0becaf9b0818436189f60504f4dfc65e.json
data/logs/0d21c9e204584a33a0b432d18fdc5243.json
data/logs/0d46ca86c2c94c85b7420cd9556d7e79.json
data/logs/0d69a3e9e1ee4e89ab56dfdf8d8d91c1.json
data/logs/0f57583eba6a4cbd8617b18ced423878.json
data/logs/10562ddb68a14245ab4074121fb82430.json
data/logs/1b06a7097fab43378ce5f6e3bc8e081c.json
data/logs/1e1e5ede6f374b0fb41fc410f88fc95b.json
data/logs/1eb77ee7283a4708abad4b499740bdd1.json
data/logs/1eed8b720a5e44a7ab5c95032ada6286.json
data/logs/21a3cc242bb2412180edb6a949d3cedb.json
data/logs/243eae07f61e43df8076d8d43c0d9e5f.json
data/logs/2495389ca8ac4061a0eef955c273878d.json
data/logs/29ea27271f18448baf2eaed57e5456da.json
data/logs/2d641a431e40459686d2b1157341aa82.json
data/logs/30de37170c5942798dc67e720c087a7b.json
data/logs/32d6c06b945743389f66cb85529f7308.json
data/logs/33ed0118483e4f6ba765d3b57955ccf9.json
data/logs/3990815f58ea4c9faff7ccbbba01d640.json
data/logs/39b1b1ce3bbd40a0859ee8839674159c.json
data/logs/3ef086c6655b454d9d61498c7f53fd4b.json
data/logs/42936b4deb3448fb9943f85b3d029875.json
data/logs/44b4b94e5740424d8116422fa3eda3a6.json
data/logs/46fcaf638549493e8b5ea902eb369a49.json
data/logs/4e2d91204a9f4601bd4a08e574939f04.json
data/logs/56fc79526ac44a5584f885c9ad4c983d.json
data/logs/58596caf369349c2944b2d0fbdb30508.json
data/logs/5cf0e7f23214454ab67a2aead270babb.json
data/logs/5ebe0db3025b4daba64bf82e3fda6593.json
data/logs/60df01351c794d7993d292bce5f29809.json
data/logs/63d19ab8b2b04bde8654412c1bb44973.json
data/logs/65b975e1566d48e3b3350bf8b0b38305.json
data/logs/65f5e03780834a30942e1ea0369dac3f.json
data/logs/661bc2042ed34cdcaeb6014042f798d5.json
data/logs/68092125784d4b28830dca173b698e1b.json
data/logs/6a3743510eb547e1b65fd8ed85eb4d1b.json
data/logs/6cb9ed930bd142efa85ed031d5cc822f.json
data/logs/6f36fb88e405411c80ae19686c16c96b.json
data/logs/6fe709b10c074127ac3528a6f3d54c24.json
data/logs/70aa7937d2fe4d3094b928a6a731a53c.json
data/logs/72db08f02ed04fe091475c83db99a2e5.json
data/logs/73c5ea156d724df18ea4f6d234b34f7f.json
data/logs/794a197b3852436ea9561beb62fdaf4c.json
data/logs/79a37a5eb24a4ad6aa956fbec127d786.json
data/logs/7c22395ef8bb4d8095d43d9703b2e258.json
data/logs/7d750fa62c86481aabf940eb50bd06a6.json
data/logs/7ef61f8f48b74660baedb6606bd00176.json
data/logs/838fd8e842744f8589a34cca123efb3f.json
data/logs/858f5c01e88c4d0bb3ee487699e8fdee.json
data/logs/87c509d60b574206b8950538f6ab100f.json
data/logs/88837b8cfb4748449ca8a5f3337351c1.json
data/logs/8961baaa890c4a34ba57ea796468a3a7.json
data/logs/89be11f11d7f44d185776a3845fdbff6.json
data/logs/8ee3e3fdcd564036b4f67c76be289ca5.json
data/logs/936ebe2d37e9451e98a6fb5fb1ae1b0c.json
data/logs/96b4bd888be047d38876ee1e198dda23.json
data/logs/9c44216fbfea4a31b84a50c79ecc8ede.json
data/logs/9d44e8ff57a2417889abd94ec3721627.json
data/logs/a1627194723e4cd7bf863a6dfa3268b7.json
data/logs/a18d71c8a52444d98816c83f2a72a238.json
data/logs/abb00e5662d5477f9bace635b7330a95.json
data/logs/ac20491053bc4879b739e42b48852f3a.json
data/logs/ac356d9ea01148acb8cff124c709eccb.json
data/logs/acb75b28b84d4eeca0a7896c8e8358ff.json
data/logs/b16e51215b4045d3929132e5219b80ab.json
data/logs/b58b2fabb3d04f25a5ded1cd3a918bee.json
data/logs/b76b4a79dc2d403faad902cf75a2b4f7.json
data/logs/b8eae35b5b584fe2b71b1daff4411074.json
data/logs/bc10d7e24ba945a7b5e615d8916d363e.json
data/logs/be84db18f88a46a59361fb824c081735.json
data/logs/be981b7a7cbc4716946af1ff7d0af563.json
data/logs/bf4756f9cb854fa08700c4619333598f.json
data/logs/c6e2be7c73344c6286466c72f00cef2f.json
data/logs/c887b0e50a6b42bf93151eb3d8d7f877.json
data/logs/ceef95d970524831b8ee476e6ba068d9.json
data/logs/d13e2438e8394f81b0379f1d0aa11a91.json
data/logs/d1e6750ee35247818ed86e3295613342.json
data/logs/d38bc59b36bc468d83a4a68356518a33.json
data/logs/d4cc83febe7143b8abefd16117e400d8.json
data/logs/d64cec1514e04e52a0b5c1ee9c9e7ba4.json
data/logs/d6bef2e867f042499d76fee3a2de0ef7.json
data/logs/dd77eb0efc374ad6a3f1597942fc5e99.json
data/logs/de7aa6b9b6144b6bb0cb77a709a2b35c.json
data/logs/e574d8a747b845a692615285356813b8.json
data/logs/e5ae8c88914e4f548772f9b2cff5bdad.json
data/logs/e6ea4823f706485485ce6aa092f9c64e.json
data/logs/e72940ae4e004f0a9882c74ad06349be.json
data/logs/e86a93d2780f43a381dfad1831e3956c.json
data/logs/ec8f20906c5f4e908eeb438c0cf904aa.json
data/logs/ed9c0b8d37eb40f58a383ba9cf4931c8.json
data/logs/f240b5f00950419e8cf96d81a1b24fde.json
data/logs/f702c03f2b064cb6a210586920913fc3.json
data/logs/f8f565e003c6476da8e5e7889986d56b.json
data/logs/f925c81e752e498aaf8e57a8d19434cb.json
data/logs/fc34a1580929406fa9ef8fb2ff57fb59.json
data/logs/fdb64f2fc6114cb4a6714a96313c9471.json
data/logs/fe652bdb8a0f4cc5aafcdad6c3ef6381.json
data/logs/ff05fd672969422793b772c91933b382.json
mcp/
mcp/files/
mcp/files/copy.py
mcp/files/create.py
mcp/files/delete.py
mcp/files/edit.py
mcp/files/info.py
mcp/files/list.py
mcp/files/move.py
mcp/files/open.py
mcp/files/read.py
mcp/files/rename.py
mcp/files/save.py
mcp/history/
mcp/history/create.py
mcp/history/delete.py
mcp/history/detail.py
mcp/history/edit.py
mcp/history/list.py
mcp/history/select.py
mcp/input/
mcp/input/keyboard.py
mcp/input/mouse.py
mcp/interaction/
mcp/interaction/answer.py
mcp/interaction/ask_user.py
mcp/interaction/questions.py
mcp/interaction/status.py
mcp/keyboard/
mcp/keyboard/hold.py
mcp/keyboard/hotkey.py
mcp/keyboard/press.py
mcp/keyboard/release.py
mcp/keyboard/type.py
mcp/log/
mcp/log/config.py
mcp/log/view.py
mcp/mission/
mcp/mission/complete.py
mcp/mission/note.py
mcp/mission/reject.py
mcp/mission/status.py
mcp/mission/step.py
mcp/mouse/
mcp/mouse/click.py
mcp/mouse/double_click.py
mcp/mouse/drag.py
mcp/mouse/hover.py
mcp/mouse/position.py
mcp/mouse/right_click.py
mcp/mouse/scroll.py
mcp/README.md
mcp/remote/
mcp/remote/status.py
mcp/safety/
mcp/safety/kill_switch.py
mcp/screen/
mcp/screen/capture.py
mcp/screen/capture_monitor.py
mcp/screen/marker.py
mcp/screen/monitors.py
mcp/screen/screenshot.py
mcp/system/
mcp/system/clipboard.py
mcp/system/info.py
mcp/system/processes.py
mcp/system/start_app.py
mcp/system/status.py
mcp/system/telemetry.py
mcp/temp/
mcp/temp/current.py
mcp/verify/
mcp/verify/assert_changed.py
mcp/verify/assert_unchanged.py
mcp/verify/diff.py
mcp/verify/hash.py
mcp/verify/wait_stable.py
mcp/watch/
mcp/watch/list.py
mcp/watch/start.py
mcp/watch/status.py
mcp/watch/stop.py
mcp/window/
mcp/window/close.py
mcp/window/find.py
mcp/window/focus.py
mcp/window/list.py
mcp/window/maximize.py
mcp/window/minimize.py
mcp/window/position.py
mcp/window/state.py
mcp/window/window.py
measure_tools.py
plugins/
plugins/discord/
plugins/discord/cache.py
plugins/discord/client.py
plugins/discord/parser.py
plugins/discord/reader.py
plugins/history/
plugins/history/create.py
plugins/history/delete.py
plugins/history/detail.py
plugins/history/edit.py
plugins/history/list.py
plugins/history/select.py
plugins/log/
plugins/log/config.py
plugins/log/view.py
plugins/mission/
plugins/mission/complete.py
plugins/mission/note.py
plugins/mission/reject.py
plugins/mission/status.py
plugins/mission/step.py
plugins/remote/
plugins/remote/status.py
remote/
remote/client.py
remote/resolver.py
remote/status.py
remote_client.py
remote_routes.py
server.py
tests/
tests/last-result.txt
tests/test_direct_routes.py
tests/test_discord.py
tests/test_remote_bridge.py
```
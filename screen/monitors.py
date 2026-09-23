import mss


def run(mode, monitor=None):
    # 연결된 모든 모니터 정보
    if mode == "all":
        monitors = []

        with mss.mss() as sct:
            for monitor_id, info in enumerate(
                sct.monitors[1:],
                start=1
            ):
                monitors.append({
                    "id": monitor_id,
                    "x": info["left"],
                    "y": info["top"],
                    "width": info["width"],
                    "height": info["height"]
                })

        return {
            "count": len(monitors),
            "monitors": monitors
        }

    # 특정 모니터 정보
    if mode == "monitor":
        if monitor is None:
            raise ValueError("monitor 값이 필요합니다.")

        monitor = int(monitor)

        with mss.mss() as sct:
            if monitor < 1 or monitor >= len(sct.monitors):
                raise ValueError("존재하지 않는 모니터입니다.")

            info = sct.monitors[monitor]

            return {
                "id": monitor,
                "x": info["left"],
                "y": info["top"],
                "width": info["width"],
                "height": info["height"]
            }

    # 떠 있는 창 목록
    if mode == "windows":
        import win32gui

        windows = []

        def callback(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return

            title = win32gui.GetWindowText(hwnd)

            if not title:
                return

            left, top, right, bottom = win32gui.GetWindowRect(hwnd)

            windows.append({
                "hwnd": hwnd,
                "title": title,
                "x": left,
                "y": top,
                "width": right - left,
                "height": bottom - top
            })

        win32gui.EnumWindows(callback, None)

        return {
            "count": len(windows),
            "windows": windows
        }

    raise ValueError(f"지원하지 않는 mode입니다: {mode}")
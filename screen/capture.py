import mss
import mss.tools
import win32gui


def run(
    mode,
    monitor=None,
    window=None,
    x=None,
    y=None,
    width=None,
    height=None
):

    # -----------------------------
    # 전체 모니터 캡처
    # -----------------------------

    if mode == "full":

        monitor = int(monitor)

        with mss.mss() as sct:

            monitor_count = len(sct.monitors) - 1

            if monitor < 1 or monitor > monitor_count:
                raise ValueError(
                    f"존재하지 않는 모니터입니다. 사용 가능: 1~{monitor_count}"
                )

            area = sct.monitors[monitor]

            image = sct.grab(area)

            return mss.tools.to_png(
                image.rgb,
                image.size
            )

    # -----------------------------
    # 특정 창 캡처
    # -----------------------------

    if mode == "window":

        hwnd = win32gui.FindWindow(
            None,
            str(window)
        )

        if not hwnd:
            raise ValueError(
                f"창을 찾을 수 없습니다: {window}"
            )

        left, top, right, bottom = (
            win32gui.GetWindowRect(hwnd)
        )

        width = right - left
        height = bottom - top

        if width <= 0 or height <= 0:
            raise ValueError(
                "창 크기가 올바르지 않습니다."
            )

        area = {
            "left": left,
            "top": top,
            "width": width,
            "height": height
        }

        with mss.mss() as sct:

            image = sct.grab(area)

            return mss.tools.to_png(
                image.rgb,
                image.size
            )

    # -----------------------------
    # 지정 영역 캡처
    # -----------------------------

    if mode == "region":

        monitor = int(monitor)
        x = int(x)
        y = int(y)
        width = int(width)
        height = int(height)

        if width <= 0 or height <= 0:
            raise ValueError(
                "width와 height는 1 이상이어야 합니다."
            )

        with mss.mss() as sct:

            monitor_count = len(sct.monitors) - 1

            if monitor < 1 or monitor > monitor_count:
                raise ValueError(
                    f"존재하지 않는 모니터입니다. 사용 가능: 1~{monitor_count}"
                )

            selected = sct.monitors[monitor]

            # x/y는 선택된 모니터 좌측 상단 기준
            area = {
                "left": selected["left"] + x,
                "top": selected["top"] + y,
                "width": width,
                "height": height
            }

            image = sct.grab(area)

            return mss.tools.to_png(
                image.rgb,
                image.size
            )

    raise ValueError(
        f"지원하지 않는 mode입니다: {mode}"
    )
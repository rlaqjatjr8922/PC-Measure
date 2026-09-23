import config
import mss


def run(monitor=None):

    # 값이 없으면 현재 선택된 모니터 반환
    if monitor is None:
        return {
            "selected_monitor": config.screen["selected_monitor"]
        }

    monitor = int(monitor)

    # 실제 존재하는 모니터인지 확인
    with mss.mss() as sct:
        monitor_count = len(sct.monitors) - 1

    if monitor < 1 or monitor > monitor_count:
        raise ValueError(
            f"존재하지 않는 모니터입니다. 사용 가능: 1~{monitor_count}"
        )

    # 기본 모니터 변경
    config.screen["selected_monitor"] = monitor
    import api_config
    api_config.screen["capture"]["mode"]["full"]["monitor"] = monitor
    api_config.screen["capture"]["mode"]["region"]["monitor"] = monitor
    api_config.screen["monitors"]["mode"]["monitor"]["monitor"] = monitor

    return {
        "selected_monitor": monitor
    }   

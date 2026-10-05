import config
import mss

def run(monitor=None):
    if monitor is None:
        return {'selected_monitor': config.screen['selected_monitor']}
    monitor = int(monitor)
    with mss.mss() as sct:
        monitor_count = len(sct.monitors) - 1
    if monitor < 1 or monitor > monitor_count:
        raise ValueError(f'존재하지 않는 모니터입니다. 사용 가능: 1~{monitor_count}')
    config.screen['selected_monitor'] = monitor
    import api_config
    api_config.screen['capture']['mode']['full']['monitor'] = monitor
    api_config.screen['capture']['mode']['region']['monitor'] = monitor
    api_config.screen['monitors']['mode']['monitor']['monitor'] = monitor
    return {'selected_monitor': monitor}

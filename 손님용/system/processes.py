def run(**kw):
    import psutil
    result = []
    for p in psutil.process_iter(['pid', 'name', 'status']):
        result.append(p.info)
    return result

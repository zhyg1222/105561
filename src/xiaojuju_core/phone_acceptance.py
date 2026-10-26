def evaluate_phone(*, connected: bool, screenshot_ok: bool, ocr_text_count: int, wechat_installed: bool, battery_level: int, powered: bool, ram_gb: float, android_sdk: int, storage_gb: float | None = None) -> dict:
    failures=[]; warnings=[]
    if not connected: failures.append("device_not_connected")
    if not screenshot_ok: failures.append("screenshot_failed")
    if int(ocr_text_count) < 2: failures.append("screen_not_readable")
    if not wechat_installed: failures.append("wechat_not_installed")
    if int(android_sdk) < 29: warnings.append("android_older_than_10")
    if float(ram_gb) < 4: warnings.append("ram_below_4gb")
    if int(battery_level) < 20 and not powered: warnings.append("low_battery_not_charging")
    if storage_gb is not None and float(storage_gb) < 2: warnings.append("storage_below_2gb")
    return {"passed": not failures, "failures": failures, "warnings": warnings}
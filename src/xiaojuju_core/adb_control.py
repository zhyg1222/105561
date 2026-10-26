def select_serial(devices_text: str, mode: str, usb_serial: str, wireless_serial: str, wireless_enabled: bool) -> str | None:
    text = devices_text or ""
    if mode == "usb_only":
        return usb_serial if usb_serial in text else None
    if mode == "wireless_only":
        return wireless_serial if wireless_serial in text else None
    if wireless_enabled and wireless_serial in text:
        return wireless_serial
    if usb_serial in text:
        return usb_serial
    return None
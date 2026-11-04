"""Map raw MQTT messages to liveness events."""
import json

STATUS_PREFIX = "doors/status/"
_STATUS_EVENTS = {"online": "seen", "offline": "offline", "rebooting": "rebooting"}


def classify(topic, payload, send_topic):
    """Return (event, device_name) with event in seen|offline|rebooting, or None."""
    if topic.startswith(STATUS_PREFIX):
        name = topic[len(STATUS_PREFIX):]
        event = _STATUS_EVENTS.get(payload.decode("utf-8", "replace").strip())
        return (event, name) if event and name else None
    if topic == send_topic:
        try:
            data = json.loads(payload)
        except ValueError:
            return None
        hostname = data.get("hostname") if isinstance(data, dict) else None
        return ("seen", hostname) if hostname else None
    return None

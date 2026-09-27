def _json_dict(response) -> dict:
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def message_of(response, label: str) -> str:
    body = _json_dict(response)
    error = body.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("status") or "")[:500]
    if isinstance(error, str):
        return str(body.get("error_description") or error)[:500]
    return f"{label} answered HTTP {response.status_code}"

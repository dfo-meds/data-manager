import datetime

def deep_update(d1, d2):
    for key in d2:
        if key in d1 and isinstance(d1[key], dict) and isinstance(d2[key], dict):
            deep_update(d1[key], d2[key])
        else:
            d1[key] = d2[key]

def safe_json(json):
    if isinstance(json, dict):
        for key in json:
            json[key] = safe_json(json[key])
        return json
    elif isinstance(json, list):
        new_list = [safe_json(x) for x in json]
        return new_list
    elif json is True or json is False or json is None:
        return json
    elif isinstance(json, str) or isinstance(json, int) or isinstance(json, float):
        return json
    # Fallback to ISO string encoding for easy parsing in Javascript
    elif isinstance(json, datetime.datetime):
        return json.isoformat()
    elif isinstance(json, datetime.date):
        return json.isoformat()
    elif isinstance(json, object):
        if hasattr(json, "__html__"):
            return str(json.__html__())
        if hasattr(json, "__str__"):
            return str(json)
    raise ValueError(f"cannot serialize: {json}")

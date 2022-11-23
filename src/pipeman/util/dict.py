
def deep_update(d1, d2):
    for key in d2:
        if key in d1 and isinstance(d1, dict) and isinstance(d2, dict):
            deep_update(d1[key], d2[key])
        else:
            d1[key] = d2[key]

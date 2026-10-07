def save(value):
    return {"saved": value}


def load(key):
    return {"key": key}


class Repository:
    def save(self, value):
        return value

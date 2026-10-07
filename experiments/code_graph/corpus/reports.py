from billing import discount, format_receipt
from storage import load


def render(key):
    return format_receipt(load(key))


def promotion(value):
    return discount(value)


def dynamic(handler, value):
    return handler(value)

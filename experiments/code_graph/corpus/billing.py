"""Synthetic billing module; never import or execute in the experiment."""


def total(items):
    return sum(items)


def discount(amount):
    return amount * 0.9


class Invoice:
    def amount(self, items):
        return discount(total(items))


def format_receipt(value):
    return str(value)

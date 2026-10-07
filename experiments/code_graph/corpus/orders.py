from billing import Invoice, total
from storage import save


def checkout(items):
    amount = total(items)
    return save(amount)


def quote(items):
    return total(items)


class ExpressInvoice(Invoice):
    pass

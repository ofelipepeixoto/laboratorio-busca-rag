"""Names in comments and strings deliberately distract lexical retrieval."""
# total total total; discount discount; checkout checkout; Invoice Invoice
# save save save save; load load; format_receipt format_receipt
# render render; promotion promotion; billing billing; storage storage


def total(items):
    return len(items)


def archived(items):
    return total(items)


def obsolete():
    return "ghost ghost"

from orders import checkout, quote
from reports import render


def run(items):
    return checkout(items), quote(items)


def preview(key):
    return render(key)


# Executing the corpus is always an error, even in this synthetic example.
raise RuntimeError("CORPUS_MUST_ONLY_BE_PARSED")

"""Processo descartável: apenas PDF local; saída JSON sem logs de documentos."""
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys
import time

from isolation import MAX_INPUT, MAX_PAGES, MAX_PAGE_TEXT, restrict_worker

VERSIONS = {"pypdf": "6.19.0", "mineru": "4.0.10", "docvortex": "0.5.11",
            "pypdfium2": "5.14.0"}


def verify_mineru_sources():
    spec = importlib.util.find_spec("mineru")
    root = Path(spec.origin).parent
    lines = Path(__file__).with_name("source-pin.sha256").read_text().splitlines()
    pin = {path: sha for sha, path in (line.split("  ", 1) for line in lines)}
    actual = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in root.rglob("*.py")}
    if actual != pin:
        raise ValueError("source_revision_mismatch")


def extract(engine, path):
    if engine not in {"pypdf", "mineru-flash"}:
        raise ValueError("engine_not_allowed")
    packages = ["pypdf"] if engine == "pypdf" else list(VERSIONS)
    for package in packages:
        if importlib.metadata.version(package) != VERSIONS[package]:
            raise ValueError("version_mismatch")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_INPUT:
        raise ValueError("invalid_input")
    data = path.read_bytes()
    if not data.startswith(b"%PDF-"):
        raise ValueError("pdf_required")
    from pypdf import PdfReader
    reader = PdfReader(path, strict=True)
    if reader.is_encrypted:
        raise ValueError("encrypted_pdf")
    total = len(reader.pages)
    if not 1 <= total <= MAX_PAGES:
        raise ValueError("page_limit")
    start = time.monotonic()
    if engine == "pypdf":
        texts = [page.extract_text() or "" for page in reader.pages]
    else:
        verify_mineru_sources()
        from mineru.parser.mineru_parser import MinerUParser
        from mineru.parser.base import ParseResult
        result = MinerUParser(tier="flash", parse_mode="txt", image_analysis=False).parse(path)
        if not result.middle_json.is_full_document or [p.page_idx for p in result.pages] != list(range(total)):
            raise ValueError("incomplete_pages")
        texts = []
        for page in result.pages:
            middle = result.middle_json.model_copy(deep=False)
            middle.pages = [page]
            # Imagens não são texto recuperado; não devolver base64 como evidência.
            texts.append(ParseResult(middle_json=middle).markdown(image_renderer=lambda block: ""))
    pages = []
    for number, text in enumerate(texts, 1):
        if len(text.encode()) > MAX_PAGE_TEXT:
            raise ValueError("page_text_limit")
        pages.append({"number": number, "text": text,
                      "text_sha256": hashlib.sha256(text.encode()).hexdigest()})
    return {"schema": 1, "engine": engine,
            "versions": {name: VERSIONS[name] for name in packages},
            "source_sha256": hashlib.sha256(data).hexdigest(),
            "review_state": "pending", "pages": pages,
            "parse_seconds": time.monotonic() - start}


def main():
    try:
        restrict_worker()
        # Imports de terceiros ocorrem só depois da instalação dos limites.
        result = extract(sys.argv[1], Path(sys.argv[2]))
    except Exception as error:
        allowed = {"engine_not_allowed", "version_mismatch", "invalid_input", "pdf_required",
                   "encrypted_pdf", "page_limit", "incomplete_pages", "page_text_limit",
                   "source_revision_mismatch"}
        reason = str(error) if str(error) in allowed else "worker_failed"
        print(json.dumps({"schema": 1, "error": reason}))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

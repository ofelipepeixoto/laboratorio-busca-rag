# Copyright (c) 2026 Carlos Felipe
# SPDX-License-Identifier: MIT
"""Original bounded offline comparison; lexical routing is NOT Jevbox's LLM."""

from dataclasses import dataclass

from busca import termos
from radar_evidence import Evidence, Scope, check_evidence
from experiments.jevbox.route_score import extend_score

MAX_PASSAGES = 2048


@dataclass(frozen=True, slots=True)
class Hit:
    evidence: Evidence
    score: float


def search(query, passages, scope, *, method="flat", top_k=3, beam_width=2,
           require_verified_review=True):
    """Filter eligibility before scoring; callers still own authentication.

    Both methods require all query terms in the final passage and use the
    existing lab's fixed equivalence dictionary. Hierarchical search first
    selects up to beam_width documents, then ranks their passages. Document
    scores are term coverage of the union of their eligible passages. Nothing
    is fetched, generated, published or executed from document text.
    """
    if type(query) is not str or not query.strip() or len(query) > 500:
        raise ValueError("query must contain 1–500 characters")
    query.encode("utf-8")
    if type(scope) is not Scope or type(require_verified_review) is not bool:
        raise TypeError("trusted Scope and explicit boolean policy required")
    if type(passages) not in (list, tuple) or len(passages) > MAX_PASSAGES:
        raise ValueError("provide at most 2048 bounded passages")
    if method not in ("flat", "hierarchical"):
        raise ValueError("unknown retrieval method")
    for value in (top_k, beam_width):
        if type(value) is not int or not 1 <= value <= 10:
            raise ValueError("top_k and beam_width must be integers from 1 to 10")
    query_terms = termos(query, expandir=True)
    if not query_terms:
        return []
    eligible = []
    seen = set()
    for evidence in passages:
        checked = check_evidence(evidence, scope, require_verified_review)
        if not checked.supported:
            continue
        if evidence.evidence_id in seen:
            raise ValueError("duplicate eligible passage")
        seen.add(evidence.evidence_id)
        # Only after scope, current revision and review have been checked.
        eligible.append((evidence, termos(evidence.quote, expandir=True)))
    documents = {}
    for evidence, tokens in eligible:
        documents.setdefault(evidence.document_id, set()).update(tokens)
    document_scores = {key: len(query_terms & tokens) / len(query_terms)
                       for key, tokens in documents.items()}
    selected = set(sorted(documents, key=lambda key: (-document_scores[key], key))[:beam_width])
    hits = []
    for evidence, tokens in eligible:
        if method == "hierarchical" and evidence.document_id not in selected:
            continue
        coverage = len(query_terms & tokens) / len(query_terms)
        if coverage != 1.0:
            continue
        score = coverage
        if method == "hierarchical":
            first = extend_score(0.0, 0, document_scores[evidence.document_id])
            score = extend_score(first[0], first[1], coverage)[2]
        hits.append(Hit(evidence, score))
    hits.sort(key=lambda hit: (-hit.score, hit.evidence.document_id,
                              hit.evidence.page, hit.evidence.start, hit.evidence.evidence_id))
    return hits[:top_k]

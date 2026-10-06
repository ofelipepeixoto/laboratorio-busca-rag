# Derived from extendRoute in extend-hq/jevbox server/beam-search.ts,
# commit aaa9381bcdca4dc7c383ab6778cb8aece72b9e3e.
# Copyright (c) 2026 CrowdView Inc, dba Extend
# Python adaptation and strict validation: Copyright (c) 2026 Carlos Felipe
# SPDX-License-Identifier: MIT. See third_party/JEVBOX-LICENSE.txt.
"""Only the geometric route score is extracted; no model or traversal engine."""

import math


def extend_score(log_probability, decisions, probability, decision=True):
    """Return accumulated log probability, decision count and geometric mean."""
    if (type(log_probability) not in (int, float) or not -1e12 <= log_probability <= 0
            or type(probability) not in (int, float) or not 0 < probability <= 1
            or type(decisions) is not int or not 0 <= decisions < 2048
            or type(decision) is not bool
            or (decisions == 0 and log_probability != 0)):
        raise ValueError("invalid route score state")
    log_probability += math.log(probability) if decision else 0
    decisions += int(decision)
    score = math.exp(log_probability / decisions) if decisions else 1.0
    return log_probability, decisions, score

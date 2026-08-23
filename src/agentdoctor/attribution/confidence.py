"""Bootstrap confidence intervals for a difference in failure proportions
(spec section 11.2: every causal claim needs a confidence interval, not
just a point estimate).
"""

from __future__ import annotations

import random
from typing import Sequence


def bootstrap_ci(
    baseline_outcomes: Sequence[int],
    intervention_outcomes: Sequence[int],
    n_bootstrap: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float]:
    """95% (by default) CI for P(fail|baseline) - P(fail|do(X)), via
    nonparametric bootstrap resampling of each arm independently.

    ``*_outcomes`` are 0/1 indicators, 1 == failure.
    """
    rng = random.Random(seed)
    n_b, n_i = len(baseline_outcomes), len(intervention_outcomes)
    if n_b == 0 or n_i == 0:
        return (0.0, 0.0)

    deltas = []
    for _ in range(n_bootstrap):
        b_sample = [baseline_outcomes[rng.randrange(n_b)] for _ in range(n_b)]
        i_sample = [intervention_outcomes[rng.randrange(n_i)] for _ in range(n_i)]
        deltas.append(sum(b_sample) / n_b - sum(i_sample) / n_i)

    deltas.sort()
    lo_idx = int((alpha / 2) * n_bootstrap)
    hi_idx = int((1 - alpha / 2) * n_bootstrap) - 1
    hi_idx = min(hi_idx, n_bootstrap - 1)
    return (deltas[lo_idx], deltas[hi_idx])

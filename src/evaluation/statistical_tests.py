"""Statistical tests for pipeline comparison.

Implements non-parametric tests (primary) and parametric tests (secondary)
for comparing retrieval and answer quality across pipelines.
"""

from __future__ import annotations

import numpy as np
from scipy import stats


def wilcoxon_signed_rank(
    scores_a: list[float],
    scores_b: list[float],
    alpha: float = 0.05,
) -> dict:
    """Wilcoxon signed-rank test for paired samples.

    Primary statistical test. Non-parametric, no normality assumption.

    Args:
        scores_a: Per-query scores from pipeline A.
        scores_b: Per-query scores from pipeline B.
        alpha: Significance level.

    Returns:
        Dict with statistic, p_value, significant, effect_size.
    """
    diffs = np.array(scores_a) - np.array(scores_b)

    # Remove zeros (ties)
    non_zero_diffs = diffs[diffs != 0]

    if len(non_zero_diffs) < 2:
        return {
            "test": "wilcoxon_signed_rank",
            "statistic": None,
            "p_value": 1.0,
            "significant": False,
            "note": "Insufficient non-zero differences for test.",
        }

    stat, p_value = stats.wilcoxon(non_zero_diffs)

    return {
        "test": "wilcoxon_signed_rank",
        "statistic": float(stat),
        "p_value": float(p_value),
        "significant": bool(p_value < alpha),
        "alpha": alpha,
    }


def cohens_d(scores_a: list[float], scores_b: list[float]) -> float:
    """Cohen's d effect size for paired samples.

    Measures standardized mean difference.
    Small: 0.2, Medium: 0.5, Large: 0.8
    """
    diffs = np.array(scores_a) - np.array(scores_b)
    if np.std(diffs) == 0:
        return 0.0
    return float(np.mean(diffs) / np.std(diffs, ddof=1))


def cliffs_delta(scores_a: list[float], scores_b: list[float]) -> dict:
    """Cliff's delta — non-parametric effect size.

    Negligible: |d| < 0.147
    Small: 0.147 ≤ |d| < 0.33
    Medium: 0.33 ≤ |d| < 0.474
    Large: |d| ≥ 0.474
    """
    a = np.array(scores_a)
    b = np.array(scores_b)
    n_a, n_b = len(a), len(b)

    # Count dominance
    more = sum(1 for ai in a for bi in b if ai > bi)
    less = sum(1 for ai in a for bi in b if ai < bi)

    delta = (more - less) / (n_a * n_b)

    # Interpret
    abs_delta = abs(delta)
    if abs_delta < 0.147:
        interpretation = "negligible"
    elif abs_delta < 0.33:
        interpretation = "small"
    elif abs_delta < 0.474:
        interpretation = "medium"
    else:
        interpretation = "large"

    return {
        "cliffs_delta": float(delta),
        "interpretation": interpretation,
    }


def paired_t_test(
    scores_a: list[float],
    scores_b: list[float],
    alpha: float = 0.05,
) -> dict:
    """Paired t-test (secondary, only if normality holds).

    Check normality with Shapiro-Wilk before using.
    """
    diffs = np.array(scores_a) - np.array(scores_b)

    # Normality check
    if len(diffs) >= 3:
        shapiro_stat, shapiro_p = stats.shapiro(diffs)
        normality_holds = bool(shapiro_p > alpha)
    else:
        shapiro_stat, shapiro_p = None, None
        normality_holds = False

    if not normality_holds:
        return {
            "test": "paired_t_test",
            "warning": "Normality assumption does not hold (Shapiro-Wilk p={:.4f}). Use Wilcoxon instead.".format(
                shapiro_p or 0.0
            ),
            "shapiro_p": float(shapiro_p) if shapiro_p else None,
        }

    stat, p_value = stats.ttest_rel(scores_a, scores_b)

    return {
        "test": "paired_t_test",
        "statistic": float(stat),
        "p_value": float(p_value),
        "significant": bool(p_value < alpha),
        "shapiro_p": float(shapiro_p),
        "normality_holds": True,
    }


def bootstrap_ci(
    scores_a: list[float],
    scores_b: list[float],
    n_bootstrap: int = 10000,
    ci_level: float = 0.95,
) -> dict:
    """Bootstrap confidence interval for the mean difference.

    Non-parametric CI via resampling.
    """
    rng = np.random.default_rng(42)
    diffs = np.array(scores_a) - np.array(scores_b)
    n = len(diffs)

    boot_means = []
    for _ in range(n_bootstrap):
        sample = rng.choice(diffs, size=n, replace=True)
        boot_means.append(np.mean(sample))

    boot_means = np.array(boot_means)
    lower_pct = (1 - ci_level) / 2 * 100
    upper_pct = (1 + ci_level) / 2 * 100

    return {
        "mean_diff": float(np.mean(diffs)),
        "ci_lower": float(np.percentile(boot_means, lower_pct)),
        "ci_upper": float(np.percentile(boot_means, upper_pct)),
        "ci_level": ci_level,
        "n_bootstrap": n_bootstrap,
    }


def full_comparison(
    scores_a: list[float],
    scores_b: list[float],
    label_a: str = "Pipeline A",
    label_b: str = "Pipeline B",
    alpha: float = 0.05,
) -> dict:
    """Run all statistical tests for comparing two pipelines.

    Returns a comprehensive comparison dict.
    """
    return {
        "comparison": f"{label_a} vs {label_b}",
        "n_queries": len(scores_a),
        "mean_a": float(np.mean(scores_a)),
        "mean_b": float(np.mean(scores_b)),
        "mean_diff": float(np.mean(scores_a) - np.mean(scores_b)),
        "wilcoxon": wilcoxon_signed_rank(scores_a, scores_b, alpha),
        "cohens_d": cohens_d(scores_a, scores_b),
        "cliffs_delta": cliffs_delta(scores_a, scores_b),
        "paired_t_test": paired_t_test(scores_a, scores_b, alpha),
        "bootstrap_ci": bootstrap_ci(scores_a, scores_b),
    }

"""intelligence.analytics — Data warehouse, aggregators, and benchmark computation.

Public API (import from submodules directly)::

    from intelligence.analytics.aggregators import compute_funnel_for_company
    from intelligence.analytics.materialized import get_platform_metrics_trend
    from intelligence.analytics.benchmarks import get_benchmarks_for_company
"""

__all__ = [
    'aggregators',
    'benchmarks',
    'materialized',
    'warehouse',
]
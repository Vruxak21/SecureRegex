"""
Optimizer package — public API.

Usage
-----
    from app.optimizer import minimize_dfa, MinimizationStats

    min_dfa, stats = minimize_dfa(dfa)
    print(stats.to_dict())
    print(min_dfa.to_dict())
"""

from app.optimizer.minimizer import minimize_dfa, MinimizationStats

__all__ = [
    "minimize_dfa",
    "MinimizationStats",
]

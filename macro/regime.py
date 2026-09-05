"""Shared regime vocabulary.

Which regime is in force decides whether a strong number is bought or sold.
Nothing else in the system is allowed to assume it.
"""

from __future__ import annotations

from enum import Enum


class MacroRegime(str, Enum):
    INFLATION_DOMINANT = "INFLATION-DOMINANT"
    # Rates are the binding constraint. Good growth news is sold (it delays
    # easing); bad growth news is bought until it threatens earnings.
    GROWTH_DOMINANT = "GROWTH-DOMINANT"
    # Earnings/recession risk is the binding constraint. Good growth news is
    # bought; bad news is bad news. Stock-bond correlation turns negative again.
    LIQUIDITY_DOMINANT = "LIQUIDITY-DOMINANT"
    # Funding/collateral stress dominates. Correlations converge to one and
    # the dollar bids regardless of the growth signal.
    UNKNOWN = "UNKNOWN"

    @property
    def explanation(self) -> str:
        return {
            MacroRegime.INFLATION_DOMINANT:
                "Policy path is the binding constraint. Equities and bonds are "
                "positively correlated; strong data tightens financial conditions.",
            MacroRegime.GROWTH_DOMINANT:
                "Earnings and recession risk are binding. Bonds hedge equities "
                "again; weak data is sold in equities and bought in duration.",
            MacroRegime.LIQUIDITY_DOMINANT:
                "Funding and collateral conditions are binding. Cross-asset "
                "correlations converge, the dollar bids, and macro signals are "
                "temporarily overridden by forced flow.",
            MacroRegime.UNKNOWN:
                "Regime not established. Directional mapping of any surprise is "
                "unreliable until it is.",
        }[self]


class RiskRegime(str, Enum):
    RISK_ON = "RISK-ON"
    RISK_OFF = "RISK-OFF"
    LIQUIDITY_STRESS = "LIQUIDITY STRESS"
    MIXED = "MIXED / TRANSITIONING"
    UNKNOWN = "UNKNOWN"


__all__ = ["MacroRegime", "RiskRegime"]

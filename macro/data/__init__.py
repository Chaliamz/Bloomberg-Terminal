"""Data adapters. Every one returns real data with provenance, or Unavailable."""

from .base import Series, Unavailable, http_get, http_json
from . import fred, store, treasury

__all__ = ["Series", "Unavailable", "fred", "http_get", "http_json", "store", "treasury"]

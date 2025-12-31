"""Addon package entrypoint.

Last updated: 2025-12-30
"""
from __future__ import annotations


from .core import (
    add,
    add_rule_data,
    add_spec_data,
    install_examples,
    list_installed,
    remove,
)

__all__ = [
    "add",
    "add_rule_data",
    "add_spec_data",
    "install_examples",
    "list_installed",
    "remove",
]

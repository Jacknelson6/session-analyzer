"""Core data types for the ledger."""

from dataclasses import dataclass


@dataclass
class Account:
    id: int
    name: str


@dataclass
class Transaction:
    id: int
    account_id: int
    amount: float
    category: str
    note: str = ""

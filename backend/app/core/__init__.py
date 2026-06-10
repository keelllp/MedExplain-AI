"""Core infrastructure: configuration, database, security, logging, exceptions.

This package holds app-wide infrastructure only — no business logic and no
imports from higher layers (services / crud / api). That keeps the dependency
direction clean (everything may import `core`; `core` imports nothing upward).
"""

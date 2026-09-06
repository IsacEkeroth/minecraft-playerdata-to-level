"""Migrate Java Edition Minecraft playerdata into level.dat."""

from .migrate import MigrationError, migrate

__all__ = ["MigrationError", "migrate"]

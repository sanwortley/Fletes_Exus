# backend/__init__.py
"""
Paquete principal del backend de Exus.
Expone el objeto `app` si se importa el paquete directamente.
"""

from .backend import app  # Permite que `from backend import app` funcione

__all__ = ["app"]

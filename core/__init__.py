"""
🤖 JARVIS — Core Modülü
LazyLoader ve sistem araçlarını içerir.
"""

__all__ = ["LazyLoader"]


def __getattr__(name):
    if name == "LazyLoader":
        from .loader import LazyLoader
        return LazyLoader
    raise AttributeError(name)

"""TurboKit: a HUD overlay for Turbo Sliders Unlimited."""

try:
    from turbokit._build import VERSION as __version__  # written by tools/build_app.py
except ImportError:
    __version__ = 'dev'

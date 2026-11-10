"""Browse nested mappings of Matplotlib figures in one window."""

from .browser import FigureBrowser
from .figures import save_figures, walk_figures

__all__ = ["FigureBrowser", "save_figures", "walk_figures"]

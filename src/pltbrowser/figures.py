"""Nested mappings of Matplotlib figures: traversal and file export."""

import re
from collections.abc import Mapping
from pathlib import Path

from matplotlib.figure import Figure


def walk_figures(figures, path=()):
    """Yield ``(path, figure)`` for every figure of a nested mapping.

    Parameters
    ----------
    figures : mapping
        Maps names to Matplotlib figures or to nested mappings of them.
    path : tuple of str, optional
        Names that lead to ``figures`` inside an enclosing mapping.

    Yields
    ------
    path : tuple of str
        Names that lead to the figure, outermost first.
    figure : matplotlib.figure.Figure
        Figure found at that path.
    """

    if not isinstance(figures, Mapping):
        raise TypeError(
            "Figures must be given as a mapping from names to figures or "
            "to nested mappings of figures."
        )
    for name, value in figures.items():
        branch = path + (str(name),)
        if isinstance(value, Figure):
            yield branch, value
        elif isinstance(value, Mapping):
            yield from walk_figures(value, branch)
        else:
            raise TypeError(
                f"{' / '.join(branch)} is a {type(value).__name__}, not "
                "a Matplotlib figure or a mapping of figures."
            )


def save_figures(figures, directory, formats=("png",), **options):
    """Save every figure of a nested mapping, one folder per group.

    The figure ``figures["a"]["b"]`` is written to ``directory/a/b.png``.

    Parameters
    ----------
    figures : mapping
        Maps names to Matplotlib figures or to nested mappings of them.
    directory : path-like
        Root output folder, created when missing.
    formats : str or sequence of str, optional
        File extensions that Matplotlib can write, such as ``"png"`` or
        ``"pdf"``.
    **options
        Passed to :meth:`matplotlib.figure.Figure.savefig`.
    """

    if isinstance(formats, str):
        formats = (formats,)
    for path, figure in walk_figures(figures):
        *folders, name = (_file_name(part) for part in path)
        folder = Path(directory).joinpath(*folders)
        folder.mkdir(parents=True, exist_ok=True)
        for extension in formats:
            figure.savefig(folder / f"{name}.{extension}", **options)


def _file_name(name):
    """Replace the characters that file systems reject."""

    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or "_"

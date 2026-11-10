"""Subplot grids that follow the shape of their canvas."""

import math

from matplotlib.gridspec import GridSpec


# margins and spacings that a rearranged grid inherits from the original
_MARGINS = ("left", "bottom", "right", "top", "wspace", "hspace")


def find_tiles(figure):
    """Return the subplots of a figure that a flow layout can rearrange.

    A grid can be rearranged when its subplots fill one uniform
    ``GridSpec`` row by row, each on one cell, and share no axis with
    another subplot.

    Returns
    -------
    list of list of Axes or None
        Axes of every subplot in reading order (twin axes belong to the
        same subplot), or ``None`` when the grid must stay as it is.
    """

    tiles = {}
    grids = set()
    for axis in figure.axes:
        spec = axis.get_subplotspec()
        # freely placed axes, subfigures, and subplots that span cells
        if (
            spec is None or axis.figure is not figure
            or spec.num1 != spec.num2
        ):
            return None
        grids.add(spec.get_gridspec())
        tiles.setdefault(spec.num1, []).append(axis)
    if len(tiles) < 2 or len(grids) != 1:
        return None

    # one plain grid of equal cells, filled row by row without gaps
    grid = grids.pop()
    if (
        not isinstance(grid, GridSpec)
        or len(set(grid.get_width_ratios() or [1])) != 1
        or len(set(grid.get_height_ratios() or [1])) != 1
        or sorted(tiles) != list(range(len(tiles)))
        or grid.nrows != math.ceil(len(tiles) / grid.ncols)
    ):
        return None

    # moving subplots that share an axis would misplace their tick labels
    tile_of = {axis: cell for cell in tiles for axis in tiles[cell]}
    for axis, cell in tile_of.items():
        shared = (
            *axis.get_shared_x_axes().get_siblings(axis),
            *axis.get_shared_y_axes().get_siblings(axis),
        )
        if any(tile_of.get(other, cell) != cell for other in shared):
            return None
    return [tiles[cell] for cell in sorted(tiles)]


class FlowLayout:
    """Rearrange the subplot grid of a figure when its canvas is resized.

    The subplots keep their order and move to the grid whose cells are
    closest in shape to the cells the figure was created with, like
    MATLAB's ``tiledlayout('flow')``. Only the grid changes: limits,
    aspect ratios, and artists are untouched.

    Parameters
    ----------
    figure : matplotlib.figure.Figure
        Figure whose subplots are rearranged.
    tiles : list of list of Axes
        Subplots of the figure, as returned by :func:`find_tiles`.
    """

    def __init__(self, figure, tiles):
        grid = tiles[0][0].get_gridspec()
        width, height = figure.get_size_inches()
        self.figure = figure
        self.tiles = tiles
        self.shape = (grid.nrows, grid.ncols)
        # width over height of one cell of the original grid
        self.cell_aspect = (width / grid.ncols) / (height / grid.nrows)
        self._margins = {name: getattr(grid, name) for name in _MARGINS}
        self._specs = [tile[0].get_subplotspec() for tile in tiles]
        self._connection = figure.canvas.mpl_connect(
            "resize_event", self.reflow
        )

    def reflow(self, event=None):
        """Move the subplots to the best grid for the figure size."""

        shape = self._best_shape()
        if shape == self.shape:
            return
        grid = GridSpec(*shape, figure=self.figure, **self._margins)
        self._place([grid[index] for index in range(len(self.tiles))])
        self.shape = shape

    def restore(self):
        """Stop following the canvas and return to the original grid."""

        self.figure.canvas.mpl_disconnect(self._connection)
        self._place(self._specs)
        self.shape = self._specs[0].get_gridspec().get_geometry()

    def _best_shape(self):
        """Return the ``(rows, columns)`` that cover most of the figure
        with cells of the original aspect."""

        width, height = self.figure.get_size_inches()
        if width <= 0.0 or height <= 0.0:
            return self.shape
        count = len(self.tiles)

        def covered(columns):
            rows = math.ceil(count / columns)
            aspect = (width / columns) / (height / rows)
            fit = min(aspect / self.cell_aspect, self.cell_aspect / aspect)
            return fit * count / (rows * columns)

        columns = max(range(1, count + 1), key=covered)
        return math.ceil(count / columns), columns

    def _place(self, specs):
        for tile, spec in zip(self.tiles, specs):
            for axis in tile:
                axis.set_subplotspec(spec)

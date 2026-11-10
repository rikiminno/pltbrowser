# pltbrowser

One window for all your Matplotlib figures.

A script that produces dozens of figures usually opens dozens of windows.
`pltbrowser` shows them in a single window instead: you organize the
figures in a nested dictionary, and a tree on the left lets you move
between them. Each figure keeps the usual Matplotlib toolbar (zoom, pan,
save).

## Installation

```bash
pip install pltbrowser
```

This installs Matplotlib and PySide6 (Qt 6) if they are missing.

## Usage

```python
import matplotlib.pyplot as plt
import numpy as np
from pltbrowser import FigureBrowser

t = np.linspace(0.0, 10.0, 200)


def plot(values, title):
    figure, axis = plt.subplots()
    axis.plot(t, values)
    axis.set_title(title)
    return figure


figures = {
    "signals": {
        "sine": plot(np.sin(t), "Sine"),
        "cosine": plot(np.cos(t), "Cosine"),
    },
    "envelope": plot(np.exp(-0.3 * t), "Envelope"),
}

FigureBrowser(figures).show()
```

The dictionary can be nested as deeply as you like: every level becomes a
group in the tree, and every figure a leaf. `show()` waits until the
window is closed, like `plt.show()`.

## Options

```python
FigureBrowser(
    figures,
    title="My results",       # window title and tree heading
    accent="tab:orange",      # any Matplotlib color
    label=str.title,          # text shown in the tree for each key
    size=(1380, 840),         # initial window size in pixels
    interactive=True,         # toolbar, mouse, and keyboard
    flow_layout=False,        # rearrange subplots to fit the window
)
```

With `flow_layout=True`, the subplots of a figure move to the grid that
best fits the window, like MATLAB's `tiledlayout('flow')`. Figures with
shared axes, spanning subplots, or freely placed axes keep their layout.

## Saving

`save_figures` writes the same dictionary to disk, one folder per group:

```python
from pltbrowser import save_figures

save_figures(figures, "plots", formats=("png", "pdf"), dpi=300)
```

This creates `plots/signals/sine.png`, `plots/signals/sine.pdf`, and so
on. Extra keyword arguments go to Matplotlib's `savefig`.

## Good to know

- The browser needs a desktop: it does not display inside Jupyter
  notebooks.
- Figures are resized to fit the window while they are displayed. They
  get their original size back when the window is closed, so saving
  them afterwards gives the same files as before.

## License

`pltbrowser` is released under the [MIT License](LICENSE).

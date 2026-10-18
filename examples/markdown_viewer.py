"""A live Markdown editor: code editor on the left, rendered preview on the right.

    python examples/markdown_viewer.py

Shows ``ui.editor`` with ``on_change``, ``ui.markdown`` and a draggable ``ui.split``.
Links in the preview open in your browser.
"""

import webbrowser

import pyzed as pz
from pyzed import ui

SAMPLE = """# Pyzed

Build **fast** desktop apps in *Python*, rendered by [Iced](https://iced.rs).

## Features

- Zed-style components in `pyzed.ui`
- Themes, including the ones from [Zed](https://zed.dev)
- `async def` everywhere

```python
import pyzed as pz

class Hello(pz.App):
    def view(self):
        return pz.text("Hello!")
```

> Tip: drag the divider to resize the panes.
"""


class MarkdownViewer(pz.App):
    title = "Markdown"
    size = (1100, 720)

    def __init__(self):
        self.source = SAMPLE
        self.ratio = 0.5
        self.wrap = True

    def view(self):
        t = self.resolved_theme()
        editor = pz.column([
            pz.container(
                pz.row([ui.label("Markdown", size="sm", color="text_muted"), pz.hspace(),
                        ui.checkbox(self.wrap, lambda v: setattr(self, "wrap", v), label="Wrap")], align="center"),
                padding=(6, 12), bg=t.tab_bar, width="fill",
            ),
            ui.editor("source", self.source, language="md", wrap=self.wrap,
                      on_change=lambda text: setattr(self, "source", text)),
        ])
        preview = pz.container(
            pz.scrollable(pz.container(ui.markdown(self.source, on_link=webbrowser.open), padding=24, max_width=760),
                          height="fill"),
            width="fill", height="fill", bg=t.background,
        )
        return ui.split(editor, preview, ratio=self.ratio, on_resize=lambda r: setattr(self, "ratio", r))


if __name__ == "__main__":
    pz.run(MarkdownViewer)

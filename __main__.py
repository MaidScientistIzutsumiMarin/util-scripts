import sys

from nicegui import app, ui

from compress import Compress
from discord import Discord
from meme import Meme


def main() -> None:
    tabs = ui.tabs().classes("w-full")
    with ui.tab_panels(tabs).classes("w-full"):
        Compress.load(tabs)
        Discord.load(tabs)
        Meme.load(tabs)

    with ui.row().classes("w-full"):
        ui.space()
        ui.button("Quit", on_click=app.shutdown)

    app.on_startup(lambda: app.native.main_window is not None and app.native.main_window.maximize())
    ui.run(dark=None, native=True, reload=False)


if __name__ == "__main__":
    sys.exit(main())

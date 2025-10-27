from nicegui import app, ui
from rich.pretty import install

from util_scripts.utils.compress import Compress
from util_scripts.utils.discord import Discord
from util_scripts.utils.meme import Meme


def root() -> None:
    tabs = ui.tabs().classes("w-full")
    with ui.tab_panels(tabs).classes("w-full"):
        Compress.load(tabs)
        Discord.load(tabs)
        Meme.load(tabs)

    with ui.row().classes("w-full"):
        ui.space()
        ui.button("Quit", on_click=app.shutdown)


def main() -> None:
    install()
    app.on_startup(lambda: app.native.main_window is not None and app.native.main_window.maximize())  # pyright: ignore[reportUnknownMemberType]
    ui.run(root, dark=None, native=True, reload=False)  # pyright: ignore[reportUnknownMemberType]

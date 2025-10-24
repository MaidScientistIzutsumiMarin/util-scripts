from nicegui import app
from nicegui.ui import button, row, run, space, tab_panels, tabs

from compress import Compress
from discord import Discord
from meme import Meme

tabs = tabs().classes("w-full")
with tab_panels(tabs).classes("w-full"):
    Compress.load(tabs)
    Discord.load(tabs)
    Meme.load(tabs)

with row().classes("w-full"):
    space()
    button("Quit", on_click=app.shutdown)

app.on_startup(lambda: app.native.main_window is not None and app.native.main_window.maximize())
run(dark=None, native=True, reload=False)

import logging
import sys
from asyncio import WindowsSelectorEventLoopPolicy, set_event_loop_policy
from logging import Handler, LogRecord, getLogger
from os import name

from nicegui import app, ui

from compress import Compress
from discord import Discord
from meme import Meme


class LogElementHandler(ui.log, Handler):
    def emit(self, record: LogRecord) -> None:
        match record.levelno:
            case logging.ERROR | logging.CRITICAL:
                color = "negative"
            case logging.WARNING:
                color = "warning"
            case logging.INFO:
                color = "info"
            case logging.DEBUG:
                color = "grey"
            case _:
                color = ""
        self.push(self.format(record), classes=f"text-{color}", props="clearable")


def main() -> None:
    if name == "nt":
        set_event_loop_policy(WindowsSelectorEventLoopPolicy())

    tabs = ui.tabs().classes("w-full")
    with ui.tab_panels(tabs).classes("w-full"):
        Compress.load(tabs)
        Discord.load(tabs)
        Meme.load(tabs)

    with ui.row().classes("w-full"):
        ui.space()
        ui.button("Quit", on_click=app.shutdown)

    getLogger().addHandler(LogElementHandler())

    ui.timer(0, lambda: app.native.main_window is not None and app.native.main_window.maximize(), once=True)
    ui.run(dark=None, native=True, reload=False)


if __name__ == "__main__":
    sys.exit(main())

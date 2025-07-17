import logging
import sys
from asyncio import WindowsSelectorEventLoopPolicy, set_event_loop_policy
from logging import Handler, LogRecord, getLogger
from os import name

from nicegui import app, ui

from compress import VideoCompressor
from discord import DiscordExpressionCreator
from meme import MemeTextCreator


class LogElementHandler(ui.log, Handler):
    def emit(self, record: LogRecord) -> None:
        match record.levelno:
            case logging.ERROR | logging.CRITICAL:
                color = "text-negative"
            case logging.WARNING:
                color = "text-warning"
            case logging.INFO:
                color = "text-info"
            case logging.DEBUG:
                color = "text-grey"
            case _:
                color = ""
        self.push(self.format(record), classes=color)


def main() -> None:
    tab_key = "tab"

    if name == "nt":
        set_event_loop_policy(WindowsSelectorEventLoopPolicy())

    with ui.tabs().classes("w-full") as tabs:
        one = ui.tab("Compress Videos")
        two = ui.tab("Create Discord Expressions")
        three = ui.tab("Create Meme Text")
    ui.separator()
    with ui.tab_panels(
        tabs,
        value=app.storage.general.get(tab_key, one),
        on_change=lambda handler: app.storage.general.update({tab_key: handler.value}),
    ).classes("w-full"):
        VideoCompressor.load(one)
        DiscordExpressionCreator.load(two)
        MemeTextCreator.load(three)

    with ui.row().classes("w-full"):
        ui.space()
        ui.button("Quit", on_click=app.shutdown)

    getLogger().addHandler(LogElementHandler().classes("w-full"))

    ui.timer(0, lambda: app.native.main_window is not None and app.native.main_window.maximize(), once=True)
    ui.run(
        dark=None,
        native=True,
        reload=False,
    )


if __name__ == "__main__":
    sys.exit(main())

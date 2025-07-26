import logging
import sys
from asyncio import WindowsSelectorEventLoopPolicy, set_event_loop_policy
from collections.abc import Awaitable, Callable
from logging import Handler, LogRecord, getLogger
from os import name

from anyio import EndOfStream
from nicegui import app, ui
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from compress import Compress
from discord import Discord
from meme import Meme


class IgnoreClientDisconnect(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        try:
            return await call_next(request)
        except RuntimeError as exc:
            if str(exc) == "No response returned.":
                return Response(status_code=499)
            raise
        except EndOfStream:
            return Response(status_code=499)


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
    app.add_middleware(IgnoreClientDisconnect)

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

    app.on_startup(lambda: app.native.main_window is not None and app.native.main_window.maximize())
    ui.run(dark=None, native=True, reload=False)


if __name__ == "__main__":
    sys.exit(main())

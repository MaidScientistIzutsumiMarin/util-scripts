from abc import abstractmethod
from asyncio import CancelledError
from datetime import timedelta
from functools import partial
from logging import getLogger
from math import inf
from mimetypes import guess_file_type
from os import fspath
from pathlib import Path
from subprocess import Popen
from time import perf_counter
from typing import ClassVar, Literal, Self, cast, override

from ffmpeg import probe_obj
from ffmpeg.dag.global_runnable.global_args import GlobalArgs
from ffmpeg.ffprobe.schema import ffprobeType
from nicegui import app, ui
from nicegui.run import io_bound
from nicegui.server import Server
from pydantic import BaseModel, ByteSize, ConfigDict, model_validator
from webview import FOLDER_DIALOG, OPEN_DIALOG

type StrPath = str | Path


class FullyValidatedModel(BaseModel):
    model_config = ConfigDict(
        validate_assignment=True,
        validate_default=True,
        validate_return=True,
        validate_by_name=True,
        ignored_types=(ui.refreshable_method,),
    )


class Common(FullyValidatedModel):
    hwaccel: ClassVar = "d3d12va"

    last_paths: dict[int, Path] = {}
    input_paths: list[Path] = []
    output_directory: Path = Path()

    @classmethod
    def load(cls, tabs: ui.tabs) -> None:
        with tabs:
            tab = ui.tab(cls.__name__)
        with ui.tab_panel(tab):
            cls.model_validate(app.storage.general[cls.__name__])
        tabs.set_value(tabs.value or tab)

    @model_validator(mode="after")
    def write(self) -> Self:
        app.storage.general[self.__class__.__name__] = self.model_dump(mode="json")
        return self

    @override
    def model_post_init(self, context: object) -> None:
        super().model_post_init(context)

        with ui.row():
            self._run_switch = ui.switch("Run", on_change=partial(io_bound, self.run))

        with ui.grid(columns=2).classes("w-full h-full"):
            ui.button("Select Input Paths", on_click=self.select_input)
            with ui.row(wrap=False, align_items="stretch"):
                ui.button("Select Output Directory", on_click=self.select_output).classes("w-full")
                ui.input("Output Extension").bind_value(self, "output_suffix")

            self._input_label = ui.label().classes("text-caption text-center text-grey")
            self._output_label = ui.label().classes("text-caption text-center text-grey")

            with ui.expansion("Input"):
                self._input_grid = ui.grid(columns=2).classes("w-full")
            with ui.expansion("Output"):
                self._results_grid = ui.grid(columns=2).classes("w-full")

        ui.separator()

        self._progress_expansion = ui.expansion("Encoding").classes("w-full")

        self.set_label_texts()

    def run(self) -> None:
        if self._run_switch.value:
            try:
                self._results_grid.clear()
                with self._results_grid:
                    self.main()
            finally:
                self._run_switch.value = False

    @abstractmethod
    def main(self) -> None: ...

    def set_label_texts(self) -> None:
        self._input_label.text = ", ".join(map(fspath, self.input_paths))
        self._output_label.text = fspath(self.output_directory)

    async def select_input(self) -> None:
        self.input_paths = await self.select_paths(self.input_paths, allow_multiple=True)
        self.set_label_texts()

        self._input_grid.clear()
        with self._input_grid:
            for input_path in self.input_paths:
                if input_path.exists():
                    media_element(input_path)

    async def select_output(self) -> None:
        (self.output_directory,) = await self.select_paths([self.output_directory], FOLDER_DIALOG)
        self.set_label_texts()

    async def select_paths[T](self, default: T, dialog_type: int = OPEN_DIALOG, *, allow_multiple: bool = False) -> T | list[Path]:
        # app.native.main_window.create_file_dialog can also return None, so we are casting it for maximum type safety.
        if files := app.native.main_window and cast(
            "tuple[str, ...] | None",
            await app.native.main_window.create_file_dialog(
                dialog_type,
                fspath(self.last_paths.get(dialog_type, "")),
                allow_multiple=allow_multiple,
            ),
        ):
            paths = list(map(Path, files))
            self.last_paths[dialog_type] = paths[0]
            return paths
        return default

    def encode_with_progress(self, stream: GlobalArgs, duration: float) -> None:
        stream = stream.global_args(
            loglevel="warning",
            y=True,
            progress="-",
        )

        duration_delta = timedelta(seconds=duration)
        ratio_format = "{} / {}"

        self._progress_expansion.clear()
        with self._progress_expansion:
            ui.code(stream.compile_line()).classes("w-full").markdown.style("scrollbar-color: gray black")
            with ui.row(wrap=False, align_items="center").classes("w-full"):
                ui.image("妖夢ちゃんに誕生日お祝いしてもらいました.webp").props("width=5%")
                progress = ui.linear_progress()

                with stream.run_async(quiet=True) as process:
                    self.handle_std(process, duration_delta, ratio_format, progress)
                    errors = "" if process.stderr is None else process.stderr.read().decode()

        if process.poll():
            progress.props("color=negative")
            raise RuntimeError(errors)

        progress.props("color=positive")
        progress.value = 1

        getLogger().warning(errors)

    def handle_std(self, process: Popen[bytes], duration_delta: timedelta, ratio_format: str, progress: ui.linear_progress) -> None:
        if process.stdout is None:
            return

        out_time_label = ui.label()
        time_elapsed_label = ui.label()
        total_size_label = ui.label()
        speed_label = ui.label()

        start_time = perf_counter()
        for line in process.stdout:
            if Server.instance.should_exit or not self._run_switch.value:
                process.terminate()
                progress.props("color=warning")
                raise CancelledError

            match line.split(b"="):
                case [b"total_size", total_size]:
                    total_size_label.text = ratio_format.format(
                        ByteSize(total_size).human_readable(),
                        ByteSize(int(total_size) / (progress.value or inf)).human_readable(),
                    )
                case [b"out_time_us", out_time_us] if out_time_us != b"N/A\n":
                    out_time_delta = timedelta(microseconds=int(out_time_us))
                    time_elapsed_delta = timedelta(seconds=perf_counter() - start_time)

                    progress.value = out_time_delta / duration_delta
                    out_time_label.text = ratio_format.format(
                        out_time_delta,
                        duration_delta,
                    )
                    time_elapsed_label.text = ratio_format.format(
                        time_elapsed_delta,
                        time_elapsed_delta / progress.value,
                    )
                case [b"speed", speed]:
                    speed_label.text = speed.decode()
                case _:
                    pass


def media_element(path: Path) -> ui.audio | ui.image | ui.video | None:
    if file_type := guess_file_type(path)[0]:
        if file_type.startswith("image"):
            element = ui.image(path)
            element.force_reload()
        else:
            element = ui.video(path)
        element.props(f"title='{path.as_posix()}'")
        return element
    return None


def get_duration(path: StrPath) -> float:
    info = get_ffprobe_info(path, "format", "duration", stream="")
    if info.format is None or info.format.duration is None:
        msg = f"The value of 'format' or 'duration' is None: {info}"
        raise ValueError(msg)
    return info.format.duration


def get_ffprobe_info(path: StrPath, entries_type: Literal["stream", "format"], *entries: str, stream: str) -> ffprobeType:
    if info := probe_obj(
        path,
        show_streams=False,
        show_format=False,
        select_streams=stream,
        show_entries=f"{entries_type}={','.join(entries)}",
    ):
        return info

    msg = "The value from ffprobe is None."
    raise ValueError(msg)

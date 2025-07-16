from abc import abstractmethod
from asyncio import CancelledError, run
from collections import defaultdict
from collections.abc import Generator
from datetime import timedelta
from logging import getLogger
from math import inf
from mimetypes import guess_file_type
from pathlib import Path
from subprocess import Popen
from time import perf_counter
from typing import ClassVar, Literal, Self, cast, override

from ffmpeg import probe_obj
from ffmpeg.dag.global_runnable.global_args import GlobalArgs
from ffmpeg.ffprobe.schema import ffprobeType, formatType, streamType
from nicegui import app, ui
from nicegui.run import io_bound
from nicegui.server import Server
from pydantic import BaseModel, ByteSize, ConfigDict, model_validator
from webview import FOLDER_DIALOG, OPEN_DIALOG

type StrOrPath = str | Path


class Common(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        validate_assignment=True,
        validate_default=True,
        validate_return=True,
        validate_by_name=True,
        ignored_types=(ui.refreshable_method,),
    )

    hwaccel: ClassVar = "d3d12va"

    last_folders: defaultdict[int, str] = defaultdict(str)
    input_files: tuple[str, ...] = ()
    output_folder: str = ""

    @classmethod
    def toml_path(cls) -> Path:
        return Path("config", f"{cls.__name__}.json")

    @classmethod
    def load(cls) -> Self:
        path = cls.toml_path()
        return cls.model_validate_json(path.read_bytes()) if path.exists() else cls()

    @model_validator(mode="after")
    def write(self) -> Self:
        path = self.toml_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(), encoding="utf_8")
        return self

    @override
    def model_post_init(self, *args: object) -> None:
        super().model_post_init(*args)

        with ui.row():
            self._run_switch = ui.switch("Run", on_change=self.run)

        with ui.grid(columns=2).classes("w-full"):
            ui.button("Select Input Files", on_click=self.select_input_files.refresh)
            ui.button("Select Output Folder", on_click=self.select_output_directory)

            self._input_files_label = ui.label().classes("text-caption text-center text-grey")
            ui.label().classes("text-caption text-center text-grey").bind_text(self, "output_folder")

            with ui.expansion("Input"), ui.grid(columns=2):
                run(self.select_input_files())

            with ui.expansion("Output"):
                self._results = ui.grid(columns=2)

            run(self.select_output_directory())

        ui.separator()

        with ui.expansion("Encoding", value=True).classes("w-full"):
            self._code_block = ui.code().classes("w-full")
            self._code_block.markdown.style("scrollbar-color: gray black")
            with ui.row(wrap=False, align_items="center").classes("w-full"):
                ui.image("妖夢ちゃんに誕生日お祝いしてもらいました.webp").props("width=5%")
                self._progress = ui.linear_progress()
                self._out_time_label = ui.label()
                self._time_elapsed_label = ui.label()
                self._total_size_label = ui.label()
                self._speed_label = ui.label()

    async def run(self) -> None:
        if self._run_switch.value:
            try:
                await io_bound(self.wrap_main)
            finally:
                self._run_switch.value = False

    def wrap_main(self) -> None:
        self._results.clear()
        for path in self.main():
            with self._results:
                media_element(path)

    @abstractmethod
    def main(self) -> Generator[Path]: ...

    @ui.refreshable_method
    async def select_input_files(self) -> None:
        self.input_files = await self.select_files(self.input_files, allow_multiple=True)
        self._input_files_label.text = ", ".join(self.input_files)
        for input_file in self.input_files:
            media_element(input_file)
        self.set_start_enabled()

    async def select_output_directory(self) -> None:
        (self.output_folder,) = await self.select_files([self.output_folder], FOLDER_DIALOG)
        Path(self.output_folder).mkdir(parents=True, exist_ok=True)
        self.set_start_enabled()

    async def select_files[T](self, default: T, dialog_type: int = OPEN_DIALOG, *, allow_multiple: bool = False) -> T | tuple[str, ...]:
        # app.native.main_window.create_file_dialog can also return None, so we are casting it for maximum type safety.
        if files := app.native.main_window and cast(
            "tuple[str, ...] | None",
            await app.native.main_window.create_file_dialog(
                dialog_type,
                self.last_folders[dialog_type],
                allow_multiple=allow_multiple,
            ),
        ):
            self.last_folders[dialog_type] = files[0]
            return files
        return default

    def set_start_enabled(self) -> None:
        return self._run_switch.set_enabled(bool(self.input_files and self.output_folder))

    def encode_with_progress(self, stream: GlobalArgs, duration: float) -> None:
        stream = stream.global_args(
            loglevel="warning",
            y=True,
            progress="-",
        )

        duration_delta = timedelta(seconds=duration)
        ratio_format = "{} / {}"

        self._code_block.content = stream.compile_line()
        self._progress.props(remove="color")

        with stream.run_async(quiet=True) as process:
            self.handle_std(process, duration_delta, ratio_format)
            errors = "" if process.stderr is None else process.stderr.read().decode()

        if process.poll():
            self._progress.props("color=negative")
            raise RuntimeError(errors)

        self._progress.props("color=positive")
        self._progress.value = 1

        getLogger().warning(errors)

    def handle_std(self, process: Popen[bytes], duration_delta: timedelta, ratio_format: str) -> None:
        if process.stdout is None:
            return

        start_time = perf_counter()

        for line in process.stdout:
            if Server.instance.should_exit or not self._run_switch.value:
                process.terminate()
                self._progress.props("color=warning")
                raise CancelledError

            match line.split(b"="):
                case [b"total_size", total_size]:
                    self._total_size_label.text = ratio_format.format(
                        ByteSize(total_size).human_readable(),
                        ByteSize(int(total_size) / (self._progress.value or inf)).human_readable(),
                    )
                case [b"out_time_us", out_time_us] if out_time_us != b"N/A\n":
                    out_time_delta = timedelta(microseconds=int(out_time_us))
                    time_elapsed_delta = timedelta(seconds=perf_counter() - start_time)

                    self._progress.value = out_time_delta / duration_delta
                    self._out_time_label.text = ratio_format.format(
                        out_time_delta,
                        duration_delta,
                    )
                    self._time_elapsed_label.text = ratio_format.format(
                        time_elapsed_delta,
                        time_elapsed_delta / self._progress.value,
                    )
                case [b"speed", speed]:
                    self._speed_label.text = speed.decode()
                case _:
                    pass


def media_element(file: StrOrPath) -> None:
    if file_type := guess_file_type(file)[0]:
        match file_type.split("/"):
            case "audio", _:
                element = ui.audio(file)
            case "image", _:
                element = ui.image(file)
                element.force_reload()
            case _:
                element = ui.video(file)

        element.props(f"title={file}")


def get_duration(path: StrOrPath) -> float:
    format_info = get_format_info(path, "duration")
    if format_info.duration is None:
        msg = f"The value of 'duration' is None: {format_info}"
        raise ValueError(msg)
    return format_info.duration


def get_stream_info(path: StrOrPath, *entries: str, stream: str) -> streamType:
    info = get_ffprobe_info(path, "stream", *entries, stream=stream)
    if info.streams is None or info.streams.stream is None:
        msg = f"The value of 'stream' is None: {info}"
        raise ValueError(msg)
    return info.streams.stream[0]


def get_format_info(path: StrOrPath, *entries: str) -> formatType:
    info = get_ffprobe_info(path, "format", *entries, stream="")
    if info.format is None:
        msg = f"The value of 'format' is None: {info}"
        raise ValueError(msg)
    return info.format


def get_ffprobe_info(path: StrOrPath, entries_type: Literal["stream", "format"], *entries: str, stream: str) -> ffprobeType:
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

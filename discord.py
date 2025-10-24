from datetime import timedelta
from functools import partial, total_ordering
from operator import itemgetter
from os import fspath
from typing import TYPE_CHECKING, Self, override
from uuid import UUID, uuid4

from ffmpeg import input as ffmpeg_input
from ffmpeg_normalize import FFmpegNormalize
from nicegui.ui import chip, column, expansion, grid, label, refreshable_method, row, select
from nicegui.ui import input as ui_input
from pytimeparse2 import parse  # pyright: ignore[reportMissingTypeStubs]

from common import Common, FullyValidatedModel, get_duration, media_element

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable
    from pathlib import Path

    from nicegui.events import ValueChangeEventArguments


@total_ordering
class Reaction(FullyValidatedModel):
    input_path: Path
    start_time: str = ""
    output_filename_base: str = ""

    def __lt__(self, other: Self) -> bool:
        return self.input_path < other.input_path


class Discord(Common):
    reactions: dict[UUID, Reaction] = {}  # noqa: RUF012
    output_suffix: str = ".opus"

    @staticmethod
    def serialize(paths: Iterable[Path]) -> list[str]:
        return list(map(fspath, paths))

    @staticmethod
    def parse_to_float(time: str) -> float | None:
        value = parse(time)
        return value.total_seconds() if isinstance(value, timedelta) else value

    def on_remove_edit(self, uuid: UUID) -> None:
        del self.reactions[uuid]
        self.write()  # pyright: ignore[reportCallIssue]

    @refreshable_method
    def on_selection(self, arguments: ValueChangeEventArguments | None) -> None:
        if arguments is not None:
            self.reactions[uuid4()] = Reaction(input_path=arguments.value)
            self.write()  # pyright: ignore[reportCallIssue]

        for uuid, reaction in sorted(self.reactions.items(), key=itemgetter(1)):
            with chip(removable=True, on_value_change=partial(self.on_remove_edit, uuid)).classes("h-full").props("outline"), ui.grid(columns=2):
                label(reaction.input_path.name).classes("col-span-full text-caption text-grey")
                media_element(reaction.input_path)
                with column():
                    ui_input("Start Time", on_change=self.write).classes("w-full").props("clearable").bind_value(reaction, "start_time")  # pyright: ignore[reportArgumentType]
                    ui_input("Output Filename Base", on_change=self.write).classes("w-full").bind_value(reaction, "output_filename_base")  # pyright: ignore[reportArgumentType]

    @override
    def model_post_init(self, context: object) -> None:
        with row(wrap=False).classes("w-full"):
            self._input_selector = select(
                self.serialize(self.input_paths),
                label="Select Input",
                on_change=lambda arguments: self.on_selection.refresh(arguments),
            ).classes("w-full")
            ui_input("Output Suffix").bind_value(self, "output_suffix")

        with expansion("Edits").classes("w-full"), grid(columns=3):
            self.on_selection(None)

        super().model_post_init(context)

    @override
    async def select_inputs(self) -> None:
        await super().select_inputs()
        self._input_selector.set_options(self.serialize(self.input_paths))

    @override
    def main(self) -> Generator[Path]:
        for reaction in self.reactions.values():
            output_path = (self.output_directory / reaction.output_filename_base).with_suffix(self.output_suffix)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            duration = 5
            stream = (
                ffmpeg_input(
                    reaction.input_path,
                    ss=self.parse_to_float(reaction.start_time),
                )
                .silenceremove(
                    start_periods=1,
                    stop_periods=1,
                )
                .output(
                    filename=output_path,
                    t=duration,
                    ac=2,
                )
            )

            seconds = self.parse_to_float(reaction.start_time) or 0
            self.encode_with_progress(stream, min(5, get_duration(reaction.input_path) - seconds))

            normalize = FFmpegNormalize(audio_codec="libopus", extension=self.output_suffix)
            normalize.add_media_file(fspath(output_path), fspath(output_path))
            normalize.run_normalization()

            yield output_path

from collections.abc import Generator, Iterable
from datetime import timedelta
from functools import partial, total_ordering
from operator import itemgetter
from os import fspath
from pathlib import Path
from typing import Self, override
from uuid import UUID, uuid4

import ffmpeg
from ffmpeg_normalize import FFmpegNormalize
from nicegui import ui
from nicegui.events import ValueChangeEventArguments
from pytimeparse2 import parse

from common import Common, FullyValidatedModel, get_duration, media_element


@total_ordering
class Reaction(FullyValidatedModel):
    path: Path
    start_time: str = ""
    output_filename_base: str = ""

    def __lt__(self, other: Self) -> bool:
        return self.path < other.path


class SoundReactionsCreator(Common):
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

    @ui.refreshable_method
    def on_selection(self, arguments: ValueChangeEventArguments | None) -> None:
        if arguments is not None:
            self.reactions[uuid4()] = Reaction(path=arguments.value)
            self.write()  # pyright: ignore[reportCallIssue]

        for uuid, reaction in sorted(self.reactions.items(), key=itemgetter(1)):
            with ui.chip(removable=True, on_value_change=partial(self.on_remove_edit, uuid)).classes("h-full").props("outline"), ui.grid(columns=2):
                media_element(reaction.path)
                with ui.column():
                    ui.input("Start Time").classes("w-full").bind_value(reaction, "start_time")
                    ui.input("Output Filename Base").classes("w-full").bind_value(reaction, "output_filename_base")

    @override
    def model_post_init(self, *args: object, input_button: bool = True) -> None:
        self._input_selector = ui.select(
            self.serialize(self.input_paths),
            label="Select Input",
            on_change=lambda arguments: self.on_selection.refresh(arguments),
        )
        with ui.expansion("Edits").classes("w-full"), ui.grid(columns=3):
            self.on_selection(None)

        super().model_post_init(*args)

    @override
    def on_input_paths_change(self) -> None:
        super().on_input_paths_change()
        self._input_selector.set_options(self.serialize(self.input_paths))

    # self.create_sound_reaction("A Ninja and an Assassin Under One Roof V1E1.mkv", "Ero manga!", "15:35")
    # self.create_sound_reaction("Ave Mujica V1E3.mkv", "つしやあ!", "9:08")
    # self.create_sound_reaction("Ave Mujica V1E6.mkv", "ふたりいる", "7:24")
    # self.create_sound_reaction("BanG Dream! V1E3.mkv", "Yay! Yay!", "13:38")
    # self.create_sound_reaction("Bocchi the Rock! V1E6.mkv", "じゃ~ん 私の「my」ベース", "10:33")
    # self.create_sound_reaction("Girls Band Cry V1E11.mkv", "Hey! Hey! Haaaa, Haaaaaa!", "16:47")
    # self.create_sound_reaction("mono V1E8.mkv", "ま「Nagano is big」だからね", "1:27")
    # self.create_sound_reaction("mono V1E10.mkv", "Nice idea", "20:16")
    # self.create_sound_reaction("mono V1E11.mkv", "Avocado cream cheese!", "18:37")
    # self.create_sound_reaction("MyGO!!!!! V1E4.mkv", "Hehehehe", "13:00")
    # self.create_sound_reaction("MyGO!!!!! V1E5.mkv", "おもしれー女", "3:46")
    # self.create_sound_reaction("MyGO!!!!! V1E10.mkv", "じー...", "6:39")
    # self.create_sound_reaction("MyGO!!!!! V1E11.mkv", "私のベッド...", "20:11")
    # self.create_sound_reaction("MyGO!!!!! V1E12.mkv", "「It's my go!」ねえ!", "4:08")
    # self.create_sound_reaction("MyGO!!!!! V1E12.mkv", "Yay!", "10:18")
    # self.create_sound_reaction("MyGO!!!!!xAve Mujica Joint Live Wakaremichi no, Sono Saki e Day 2.m4a", "It's MyGO!!!!!", "2:08:49")
    # self.create_sound_reaction("MyGO!!!!!メンバーの日常「かき氷」.webm", "あー!", 23)
    # self.create_sound_reaction("Nyamuchi Channel #2.webm", "こんばんにゃむにゃむ~~! にゃむちです~~!", 2)
    # self.create_sound_reaction("Po-Pi-Pa Pa-Pi-Po Pa!.mp4", "Po-Pi-Pa Pa-Pi-Po Pa!")
    # self.create_sound_reaction("Uma Musume Pretty Derby V1E4.mkv", "「Very exciting」でした!", "20:18")
    # self.create_sound_reaction("可憐なカミツレ.flac", "Princess Togawa Sakiko Arrives")

    @override
    def main(self) -> Generator[Path]:
        for reaction in self.reactions.values():
            output_path = self.output_directory / Path(reaction.output_filename_base).with_suffix(self.output_suffix)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            duration = 5
            stream = (
                ffmpeg.input(
                    reaction.path,
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

            seconds = self.parse_to_float(str(reaction.start_time)) or 0
            self.encode_with_progress(stream, min(5, get_duration(reaction.path)) - seconds)

            normalize = FFmpegNormalize(extension=self.output_suffix)
            normalize.add_media_file(fspath(output_path), fspath(output_path))
            normalize.run_normalization()

            yield output_path

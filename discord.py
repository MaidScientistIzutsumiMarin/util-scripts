from collections.abc import Callable, Generator
from datetime import timedelta
from enum import StrEnum
from os import fspath
from pathlib import Path
from typing import override

import ffmpeg
from ffmpeg import AVStream, VideoStream
from ffmpeg.codecs.encoders import libopus
from ffmpeg.dag.io.output_args import OutputArgs
from ffmpeg.types import String, Time
from ffmpeg_normalize import FFmpegNormalize
from nicegui import ui
from pytimeparse2 import parse

from common import Common, StrPath, get_duration


class Expression(StrEnum):
    ANIMATED_EMOJI = "Animated Emoji"
    SOUND_REACTIONS = "Sound Reactions"


class DiscordExpressionCreator(Common):
    expression: Expression = Expression.ANIMATED_EMOJI

    @staticmethod
    def get_seconds(value: object, default: float) -> float:
        seconds = parse(str(value))
        return seconds.total_seconds() if isinstance(seconds, timedelta) else seconds or default

    @override
    def model_post_init(self, *args: object, input_button: bool = True) -> None:
        self._input_button_enabled = False
        ui.toggle(list(Expression)).bind_value(self, "expression")
        super().model_post_init(*args)

    @override
    def main(self) -> Generator[Path]:
        if self.expression is Expression.ANIMATED_EMOJI:
            pito_crop = self.crop(85, 0.565, 0.335)

            yield self.create_animated_emoji("Monimorning!.gif", "Monimorning!")
            yield self.create_animated_emoji("OguuVibing.mp4", "OguuVibing", filters=lambda stream: stream.colorkey(color="White", similarity=0.15))
            yield self.create_animated_emoji("Sword Art Online Alternative Gun Gale Online V1E3.mkv", "LlennWaaa", "6:14.548", "6:14.923", self.crop(125, 0.465, 0.605))
            yield self.create_animated_emoji("Sword Art Online Alternative Gun Gale Online V2E2.mkv", "PitoBye", "14:59", "15:01.902", pito_crop)
            yield self.create_animated_emoji("Sword Art Online Alternative Gun Gale Online V2E2.mkv", "PitoHi", "15:06.698", "15:09.952", pito_crop)
        else:
            yield self.create_sound_reaction("A Ninja and an Assassin Under One Roof V1E1.mkv", "Ero manga!", "15:35")
            yield self.create_sound_reaction("Ave Mujica V1E3.mkv", "つしやあ!", "9:08")
            yield self.create_sound_reaction("Ave Mujica V1E6.mkv", "ふたりいる", "7:24")
            yield self.create_sound_reaction("BanG Dream! V1E3.mkv", "Yay! Yay!", "13:38")
            yield self.create_sound_reaction("Bocchi the Rock! V1E6.mkv", "じゃ~ん 私の「my」ベース", "10:33")
            yield self.create_sound_reaction("Girls Band Cry V1E11.mkv", "Hey! Hey! Haaaa, Haaaaaa!", "16:47")
            yield self.create_sound_reaction("mono V1E8.mkv", "ま「Nagano is big」だからね", "1:27")
            yield self.create_sound_reaction("mono V1E10.mkv", "Nice idea", "20:16")
            yield self.create_sound_reaction("mono V1E11.mkv", "Avocado cream cheese!", "18:37")
            yield self.create_sound_reaction("MyGO!!!!! V1E4.mkv", "Hehehehe", "13:00")
            yield self.create_sound_reaction("MyGO!!!!! V1E5.mkv", "おもしれー女", "3:46")
            yield self.create_sound_reaction("MyGO!!!!! V1E10.mkv", "じー...", "6:39")
            yield self.create_sound_reaction("MyGO!!!!! V1E11.mkv", "私のベッド...", "20:11")
            yield self.create_sound_reaction("MyGO!!!!! V1E12.mkv", "「It's my go!」ねえ!", "4:08")
            yield self.create_sound_reaction("MyGO!!!!! V1E12.mkv", "Yay!", "10:18")
            yield self.create_sound_reaction("MyGO!!!!!xAve Mujica Joint Live Wakaremichi no, Sono Saki e Day 2.m4a", "It's MyGO!!!!!", "2:08:49")
            yield self.create_sound_reaction("MyGO!!!!!メンバーの日常「かき氷」.webm", "あー!", 23)
            yield self.create_sound_reaction("Nyamuchi Channel #2.webm", "こんばんにゃむにゃむ~~! にゃむちです~~!", 2)
            yield self.create_sound_reaction("Po-Pi-Pa Pa-Pi-Po Pa!.mp4", "Po-Pi-Pa Pa-Pi-Po Pa!")
            yield self.create_sound_reaction("Uma Musume Pretty Derby V1E4.mkv", "「Very exciting」でした!", "20:18")
            yield self.create_sound_reaction("可憐なカミツレ.flac", "Princess Togawa Sakiko Arrives")

    def crop(self, dimensions: String, x_percentage: float, y_percentage: float) -> Callable[[AVStream], VideoStream]:
        return lambda stream: stream.crop(
            out_w=dimensions,
            out_h=dimensions,
            x=f"{x_percentage} * (in_w - out_w)",
            y=f"{y_percentage} * (in_h - out_h)",
        )

    def create_animated_emoji(
        self,
        input_filename: StrPath,
        output_filename_base: StrPath,
        start: Time = None,
        stop: Time = None,
        filters: Callable[[AVStream], OutputArgs] = AVStream.null,
    ) -> Path:
        return self.create_discord_expression(
            input_filename,
            f"{output_filename_base}.avif",
            start,
            stop,
            filters,
        )

    def create_sound_reaction(
        self,
        input_filename: StrPath,
        output_filename_base: StrPath,
        start: Time = None,
    ) -> Path:
        path = self.create_discord_expression(
            input_filename,
            f"{output_filename_base}.opus",
            start,
            None,
            lambda stream: stream.silenceremove(start_periods=1, stop_periods=1),
        )

        normalize = FFmpegNormalize(target_level=-30, audio_codec=libopus.__name__)
        normalize.add_media_file(fspath(path), fspath(path))
        normalize.run_normalization()

        return path

    def create_discord_expression(
        self,
        input_filename: StrPath,
        output_filename: StrPath,
        start: Time,
        stop: Time,
        filters: Callable[[AVStream], OutputArgs],
    ) -> Path:
        input_path = Path("data", self.expression, input_filename)
        output_path = self.output_directory / self.expression / output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        stream = filters(
            ffmpeg.input(
                input_path,
                to=stop,
                ss=start,
            ),
        ).output(
            filename=output_path,
            t=5,
            ac=2,
        )

        duration = self.get_seconds(stop, get_duration(input_path)) - self.get_seconds(start, 0)
        self.encode_with_progress(stream, duration)

        return output_path

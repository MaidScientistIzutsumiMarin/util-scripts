from collections.abc import Callable
from os import fspath
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import ffmpeg
from ffmpeg import AVStream, VideoStream
from ffmpeg.codecs.encoders import libopus, libsvtav1
from ffmpeg.dag.io.output_args import OutputArgs
from ffmpeg.types import String, Time
from ffmpeg_normalize import FFmpegNormalize

from common import Common

if TYPE_CHECKING:
    from _typeshed import StrPath


class DiscordExpressionCreator(Common):
    def create_discord_expression(
        self,
        expression_type: Literal["Animated Emoji", "Sound Reactions"],
        input_filename: "StrPath",
        output_filename_base: "StrPath",
        output_suffix: str,
        codec: String,
        start: Time,
        stop: Time,
        filters: Callable[[AVStream], OutputArgs],
    ) -> Path:
        output_path = create_output_path(expression_type, output_filename_base, suffix=output_suffix)

        stream = filters(
            ffmpeg.input(
                Path("data", expression_type, input_filename),
                to=stop,
                ss=start,
            ),
        ).output(
            filename=output_path,
            c=codec,
            t=5,
            ac=2,
        )
        encode_with_progress(stream, print_warnings=False)

        return output_path

    def create_animated_emoji(
        self,
        input_filename: "StrPath",
        output_filename_base: "StrPath",
        start: Time = None,
        stop: Time = None,
        filters: Callable[[AVStream], OutputArgs] = AVStream.null,
    ) -> None:
        create_discord_expression(
            "Animated Emoji",
            input_filename,
            output_filename_base,
            ".avif",
            libsvtav1.__name__,
            start,
            stop,
            filters,
        )

    def create_sound_reaction(
        self,
        input_filename: "StrPath",
        output_filename_base: "StrPath",
        start: Time = None,
    ) -> None:
        path = create_discord_expression(
            "Sound Reactions",
            input_filename,
            output_filename_base,
            ".opus",
            None,
            start,
            None,
            lambda stream: stream.silenceremove(start_periods=1, stop_periods=1),
        )

        normalize = FFmpegNormalize(target_level=-30, audio_codec=libopus.__name__)
        normalize.add_media_file(fspath(path), fspath(path))
        normalize.run_normalization()

    def crop(self, dimensions: String, x_percentage: float, y_percentage: float) -> Callable[[AVStream], VideoStream]:
        return lambda stream: stream.crop(
            out_w=dimensions,
            out_h=dimensions,
            x=f"{x_percentage} * (in_w - out_w)",
            y=f"{y_percentage} * (in_h - out_h)",
        )

    def main(self) -> None:
        pito_crop = crop(85, 0.565, 0.335)

        create_animated_emoji("Monimorning!.gif", "Monimorning!")
        create_animated_emoji("OguuVibing.mp4", "OguuVibing", filters=lambda stream: stream.colorkey(color="White", similarity=0.15))
        create_animated_emoji("Sword Art Online Alternative Gun Gale Online V1E3.mkv", "LlennWaaa", "6:14.548", "6:14.923", crop(125, 0.465, 0.605))
        create_animated_emoji("Sword Art Online Alternative Gun Gale Online V2E2.mkv", "PitoBye", "14:59", "15:01.902", pito_crop)
        create_animated_emoji("Sword Art Online Alternative Gun Gale Online V2E2.mkv", "PitoHi", "15:06.698", "15:09.952", pito_crop)

        create_sound_reaction("A Ninja and an Assassin Under One Roof V1E1.mkv", "Ero manga!", "15:35")
        create_sound_reaction("Ave Mujica V1E3.mkv", "つしやあ!", "9:08")
        create_sound_reaction("Ave Mujica V1E6.mkv", "ふたりいる", "7:24")
        create_sound_reaction("BanG Dream! V1E3.mkv", "Yay! Yay!", "13:38")
        create_sound_reaction("Bocchi the Rock! V1E6.mkv", "じゃ~ん 私の「my」ベース", "10:33")
        create_sound_reaction("Girls Band Cry V1E11.mkv", "Hey! Hey! Haaaa, Haaaaaa!", "16:47")
        create_sound_reaction("mono V1E8.mkv", "ま「Nagano is big」だからね", "1:27")
        create_sound_reaction("mono V1E10.mkv", "Nice idea", "20:16")
        create_sound_reaction("mono V1E11.mkv", "Avocado cream cheese!", "18:37")
        create_sound_reaction("MyGO!!!!! V1E4.mkv", "Hehehehe", "13:00")
        create_sound_reaction("MyGO!!!!! V1E5.mkv", "おもしれー女", "3:46")
        create_sound_reaction("MyGO!!!!! V1E10.mkv", "じー...", "6:39")
        create_sound_reaction("MyGO!!!!! V1E11.mkv", "私のベッド...", "20:11")
        create_sound_reaction("MyGO!!!!! V1E12.mkv", "「It's my go!」ねえ!", "4:08")
        create_sound_reaction("MyGO!!!!! V1E12.mkv", "Yay!", "10:18")
        create_sound_reaction("MyGO!!!!!xAve Mujica Joint Live Wakaremichi no, Sono Saki e Day 2.m4a", "It's MyGO!!!!!", "2:08:49")
        create_sound_reaction("MyGO!!!!!メンバーの日常「かき氷」.webm", "あー!", 23)
        create_sound_reaction("Nyamuchi Channel #2.webm", "こんばんにゃむにゃむ~~! にゃむちです~~!", 2)
        create_sound_reaction("Po-Pi-Pa Pa-Pi-Po Pa!.mp4", "Po-Pi-Pa Pa-Pi-Po Pa!")
        create_sound_reaction("Uma Musume Pretty Derby V1E4.mkv", "「Very exciting」でした!", "20:18")
        create_sound_reaction("可憐なカミツレ.flac", "Princess Togawa Sakiko Arrives")

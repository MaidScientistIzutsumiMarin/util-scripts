from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryFile
from typing import override

import ffmpeg
from nicegui import ui
from pydantic import ByteSize

from common import Common, get_duration


class Compress(Common):
    max_size: ByteSize = "500MiB"  # pyright: ignore[reportAssignmentType]
    output_suffix: str = ".mp4"

    @override
    def model_post_init(self, context: object) -> None:
        ui.number("Max Video Size", suffix="bytes").bind_value(self, "max_size")

        return super().model_post_init(context)

    @override
    def main(self) -> Generator[Path]:
        with TemporaryFile(suffix=self.output_suffix, delete_on_close=False) as audio_fp:
            audio_path = Path(audio_fp.name)
            audio_input = ffmpeg.input(audio_path)

            for input_path in self.input_paths:
                duration = get_duration(input_path)

                input_stream = ffmpeg.input(input_path, hwaccel=self.hwaccel)
                stream = input_stream.audio.output(filename=audio_path)
                self.encode_with_progress(stream, duration)

                output_path = self.get_output_path(input_path)
                video_max_rate = 8 * (self.max_size - audio_path.stat().st_size) / duration
                stream = input_stream.video_stream(0).output(
                    audio_input,
                    filename=output_path,
                    acodec="copy",
                    extra_options={
                        "bufsize": 2 * video_max_rate,
                        "maxrate": video_max_rate,
                    },
                )

                self.encode_with_progress(stream, duration)

                yield output_path

from pathlib import Path
from tempfile import TemporaryFile
from typing import override

import ffmpeg
from nicegui import ui
from pydantic import ByteSize, PositiveFloat

from common import Common, get_duration, render_video


class VideoCompressor(Common):
    max_size: ByteSize = "500MiB"  # pyright: ignore[reportAssignmentType]
    bitrate_percent: PositiveFloat = 95
    output_suffix: str = ".mp4"
    video_codec: str = "hevc_amf"

    @override
    def model_post_init(self, *args: object) -> None:
        with ui.grid(columns=2):
            ui.number("Max Video Size", suffix="bytes").bind_value(self, "max_size")
            ui.number("Target Bitrate Ratio", suffix="%").bind_value(self, "bitrate_percent")

            ui.input("Output Suffix").bind_value(self, "output_suffix")
            ui.input("Video Codec").bind_value(self, "video_codec")

        return super().model_post_init(*args)

    @override
    def main(self) -> None:
        self._results.clear()

        with TemporaryFile(suffix=self.output_suffix, delete_on_close=False) as audio_fp:
            audio_path = Path(audio_fp.name)
            audio_input = ffmpeg.input(audio_path)

            for input_file in self.input_files:
                duration = get_duration(input_file)

                input_stream = ffmpeg.input(input_file)
                stream = input_stream.audio.output(filename=audio_path)
                self.encode_with_progress(stream, duration)

                output_path = Path(self.output_folder) / Path(input_file).with_suffix(self.output_suffix).name
                video_max_rate = 8 * (self.max_size - audio_path.stat().st_size) / duration
                stream = input_stream.video_stream(0).output(
                    audio_input,
                    filename=output_path,
                    vcodec=self.video_codec,
                    acodec="copy",
                    extra_options={
                        "bufsize": 2 * video_max_rate,
                        "maxrate": video_max_rate,
                        "vb": self.bitrate_percent * video_max_rate / 100,
                    },
                )

                self.encode_with_progress(stream, duration)
                render_video(output_path)

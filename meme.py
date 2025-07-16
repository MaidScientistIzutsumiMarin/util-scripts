from collections.abc import Generator
from functools import partial
from pathlib import Path
from typing import ClassVar, TypeVar, override

import ffmpeg
from fontra import all_fonts, get_font, get_font_styles, has_font_style, init_fontdb
from nicegui import ui
from pydantic import PositiveFloat, PositiveInt

from common import Common, get_duration, get_stream_info

AnyElement = TypeVar("AnyElement", bound=ui.element)


class MemeTextCreator(Common):
    default_font_style: ClassVar = "Regular"

    text: str = ""
    font_family: str = "Impact"
    font_size: PositiveFloat = 100
    box_height: PositiveInt = 100

    @override
    def model_post_init(self, *args: object) -> None:
        init_fontdb()

        with ui.row(align_items="center"):
            self.set_font_family("")
            ui.splitter()
            ui.number("Font Size", min=1).bind_value(self, "font_size")
            ui.number("Box Height", min=1).bind_value(self, "box_height")

        self._text_area = ui.textarea("Overlay Text").classes("w-full").props("clearable").bind_value(self, "text")

        return super().model_post_init(*args)

    @ui.refreshable_method
    def set_font_family(self, font_family: str) -> None:
        if font_family:
            self.font_family = font_family

        with ui.dropdown_button(self.font_family, auto_close=True).style(f"font-family: {self.font_family}"), ui.column(align_items="stretch").classes("gap-0"):
            for family in sorted(all_fonts()):
                ui.item(
                    family,
                    on_click=partial(self.set_font_family.refresh, family),
                ).style(f"font-family: {family}").set_enabled(self.font_family != family)

    @override
    def main(self) -> Generator[Path]:
        font_style = get_font_styles(self.font_family)[0] if not has_font_style(self.font_family, self.default_font_style) else self.default_font_style
        font_file = str(get_font(self.font_family, font_style).path)

        for input_file in self.input_files:
            stream_info = get_stream_info(input_file, "width", "height", stream="v")
            if stream_info.width is None or stream_info.height is None:
                msg = f"The value of 'width' or 'height' is None: {stream_info}"
                raise ValueError(msg)

            output_path = Path(self.output_folder, self._text_area.value).with_suffix(".webp")
            stream = (
                ffmpeg.input(input_file, hwaccel=self.hwaccel)
                .drawtext(
                    fontfile=font_file,
                    text=self._text_area.value.replace("\n", "\r"),
                    box=True,
                    fontsize=self.font_size,
                    text_align="center+middle",
                    boxw=stream_info.width,
                    boxh=self.box_height,
                )
                .output(
                    filename=output_path,
                    extra_options={
                        "loop": 0,
                    },
                )
            )

            self.encode_with_progress(stream, get_duration(input_file))
            yield output_path

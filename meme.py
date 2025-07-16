from collections.abc import Generator
from pathlib import Path
from typing import ClassVar, TypeVar, override

import ffmpeg
from fontra import all_fonts, get_font, get_font_styles, has_font_style, init_fontdb
from nicegui import ui
from nicegui.elements.mixins.text_element import TextElement
from nicegui.events import UiEventArguments
from pydantic import PositiveFloat, PositiveInt

from common import Common, get_duration, get_stream_info

AnyElement = TypeVar("AnyElement", bound=ui.element)


class MemeTextCreator(Common):
    default_font_style: ClassVar = "Regular"

    text: str = ""
    font_family: str = "Impact"
    font_size: PositiveFloat = 10
    box_height: PositiveInt = 100
    output_suffix: str = ".webp"

    @override
    def model_post_init(self, *args: object) -> None:
        init_fontdb()

        self._text_area = ui.textarea("Overlay Text").classes("w-full").props("clearable").bind_value(self, "text")
        with ui.row(align_items="center"):
            self.set_font_style(None)
            ui.input("Output Suffix").bind_value(self, "output_suffix")

        return super().model_post_init(*args)

    @ui.refreshable_method
    def set_font_style(self, arguments: UiEventArguments | None) -> None:
        if arguments is not None and isinstance(arguments.sender, TextElement):
            self.font_family = arguments.sender.text

        with ui.dropdown_button(self.font_family, auto_close=True).style(f"font-family: {self.font_family}"), ui.column(align_items="stretch").classes("gap-0"):
            for family in sorted(all_fonts()):
                is_selected = self.font_family == family
                ui.button(
                    family,
                    on_click=lambda argument: self.set_font_style.refresh(argument),
                ).props("outline" if is_selected else "flat").style(f"font-family: {family}").set_enabled(not is_selected)

    @override
    def main(self) -> Generator[Path]:
        font_style = get_font_styles(self.font_family)[0] if not has_font_style(self.font_family, self.default_font_style) else self.default_font_style
        font_file = str(get_font(self.font_family, font_style).path)

        for input_file in self.input_files:
            stream_info = get_stream_info(input_file, "width", "height", stream="v")
            if stream_info.width is None or stream_info.height is None:
                msg = f"The value of 'width' or 'height' is None: {stream_info}"
                raise ValueError(msg)

            output_path = Path(self.output_folder, self._text_area.value).with_suffix(self.output_suffix)
            stream = (
                ffmpeg.input(input_file)
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

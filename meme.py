from pathlib import Path
from typing import TYPE_CHECKING, TypeVar, cast, override

import ffmpeg
from find_system_fonts_filename import get_system_fonts_filename
from fontTools.ttLib import TTFont
from nicegui import ui
from nicegui.elements.mixins.text_element import TextElement
from nicegui.events import ClickEventArguments
from pydantic import PositiveFloat, PositiveInt

from common import Common, get_duration, get_stream_info, render_video

if TYPE_CHECKING:
    from fontTools.ttLib.tables._n_a_m_e import table__n_a_m_e


AnyElement = TypeVar("AnyElement", bound=ui.element)


class MemeTextCreator(Common):
    text: str = ""
    font_family: str = "Impact"
    font_size: PositiveFloat = 10
    box_height: PositiveInt = 100
    output_suffix: str = ".webp"

    @staticmethod
    def style_font(element: AnyElement, family: str = font_family) -> AnyElement:
        return element.style(f"font-family: {family};")

    @override
    def model_post_init(self, *args: object) -> None:
        self._fonts: dict[str, str] = {}

        self._text_area = ui.textarea("Overlay Text").classes("w-full").props("clearable").bind_value(self, "text")

        with ui.row(align_items="center"):
            with ui.dropdown_button("Font"), ui.column(align_items="stretch").classes("gap-0"):
                for file in get_system_fonts_filename():
                    if family := cast("str | None", cast("table__n_a_m_e", TTFont(file, fontNumber=0)["name"]).getDebugName(1)):
                        self.style_font(ui.button(family, on_click=self.set_font_family).props("flat"), family).set_enabled(file != self.font_family)
                        self._fonts[family] = file

            self._font_label = ui.label().bind_text(self, "font_family")
            ui.input("Output Suffix").bind_value(self, "output_suffix")

        self.style_font(self._font_label)

        return super().model_post_init(*args)

    def set_font_family(self, arguments: ClickEventArguments) -> None:
        if isinstance(arguments.sender, TextElement):
            self.font_family = arguments.sender.text
            self.style_font(self._font_label)

    @override
    def main(self) -> None:
        self._results.clear()

        for input_file in self.input_files:
            stream_info = get_stream_info(input_file, "width", "height", stream="v")
            if stream_info.width is None or stream_info.height is None:
                msg = f"The value of 'width' or 'height' is None: {stream_info}"
                raise ValueError(msg)

            output_path = Path(self.output_folder, self._text_area.value).with_suffix(self.output_suffix)
            stream = (
                ffmpeg.input(input_file)
                .drawtext(
                    fontfile=self._fonts[self.font_family],
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
            render_video(output_path)

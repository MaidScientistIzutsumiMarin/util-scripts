from collections.abc import Generator
from functools import partial
from pathlib import Path
from typing import ClassVar, TypeVar, override

import ffmpeg
from fontra import all_fonts, get_font, get_font_styles, has_font_style, init_fontdb
from nicegui import ui
from pydantic import PositiveFloat, PositiveInt
from pydantic_extra_types.color import Color

from common import Common, get_duration, get_ffprobe_info

AnyElement = TypeVar("AnyElement", bound=ui.element)


class Meme(Common):
    default_font_style: ClassVar = "Regular"

    text: str = ""
    font_family: str = "Impact"
    font_size: PositiveFloat = 100
    box_height: PositiveInt = 100
    font_color: Color = Color("#000000")
    box_color: Color = Color("#ffffff")
    loop: bool = True

    output_suffix: str = ".webp"

    @override
    def model_post_init(self, context: object) -> None:
        init_fontdb()

        with ui.row(wrap=False, align_items="center"):
            self.set_font_family(self.font_family)
            self.color_picker_button("Font Color", "font_color")
            self.color_picker_button("Box Color", "box_color")
            ui.input("Output Suffix").bind_value(self, "output_suffix")
            ui.checkbox("Loop").bind_value(self, "loop")

        with ui.row(wrap=False, align_items="center").classes("w-full"):
            ui.label("Font Size").classes("text-caption text-grey")
            ui.slider(min=1, max=200).props("label-always").bind_value(self, "font_size")
            ui.separator().props("vertical")
            ui.label("Box Height").classes("text-caption text-grey")
            ui.slider(min=1, max=500).props("label-always").bind_value(self, "box_height")

        self._text_area = ui.textarea("Overlay Text").classes("w-full").props("clearable").bind_value(self, "text")

        return super().model_post_init(context)

    @ui.refreshable_method
    def set_font_family(self, font_family: str) -> None:
        self.font_family = font_family

        with ui.dropdown_button(self.font_family, auto_close=True).style(f"font-family: {self.font_family}"), ui.column(align_items="stretch").classes("gap-0"):
            for family in sorted(all_fonts()):
                ui.item(
                    family,
                    on_click=partial(self.set_font_family.refresh, family),
                ).style(f"font-family: {family}").set_enabled(self.font_family != family)

    def color_picker_button(self, text: str, attr: str) -> None:
        with ui.button(text, icon="palette") as button:
            ui.color_picker(on_pick=lambda e: self.on_pick_color(button, Color(e.color), attr))
        self.on_pick_color(button, getattr(self, attr), attr)

    def on_pick_color(self, button: ui.element, background_color: Color, attr: str) -> None:
        r, g, b = (255 - int(value) for value in background_color.as_rgb_tuple())
        text_color = Color((r, g, b))

        button.classes(f"!text-[{text_color.as_hex(format='long')}]")
        button.classes(f"!bg-[{background_color.as_hex(format='long')}]")
        setattr(self, attr, background_color)

    @override
    def main(self) -> Generator[Path]:
        font_style = get_font_styles(self.font_family)[0] if not has_font_style(self.font_family, self.default_font_style) else self.default_font_style
        font_file = str(get_font(self.font_family, font_style).path)

        for input_path in self.input_paths:
            info = get_ffprobe_info(input_path, "stream", "width", stream="v")
            if info.streams is None or info.streams.stream is None or info.streams.stream[0].width is None:
                msg = f"The value of 'stream' or 'width' is None: {info}"
                raise ValueError(msg)

            output_path = self.output_directory / input_path.with_suffix(self.output_suffix)
            stream = (
                ffmpeg.input(input_path, hwaccel=self.hwaccel)
                .drawtext(
                    fontfile=font_file,
                    text=self.text.replace("\n", "\r"),
                    box=True,
                    boxcolor=self.box_color.as_hex(format="long"),
                    fontcolor=self.font_color.as_hex(format="long"),
                    fontsize=self.font_size,
                    text_align="center+middle",
                    boxw=info.streams.stream[0].width,
                    boxh=self.box_height,
                )
                .output(
                    filename=output_path,
                    extra_options={
                        "loop": int(not self.loop),
                    },
                )
            )

            self.encode_with_progress(stream, get_duration(input_path))
            yield output_path

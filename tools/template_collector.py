from __future__ import annotations

import argparse
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from queshen_agent.config import load_region_config
from queshen_agent.paths import REGIONS_PATH, TEMPLATES_DIR
from queshen_agent.template_collection import (
    CANDIDATES_DIR,
    collect_template_candidates,
    find_latest_screenshot,
    save_template_crop,
    template_region_keys,
)
from queshen_agent.tile import ALL_TILES, tile_label


class TemplateCollectorApp:
    def __init__(self, image_path: Path) -> None:
        self.image_path = image_path
        self.source_image = Image.open(image_path).convert("RGB")
        self.root = tk.Tk()
        self.root.title("雀神模板采集")
        self.root.geometry("1120x760")
        self.root.minsize(820, 520)
        self.root.configure(bg="#111318")

        self.scale = 1.0
        self.display_image: Image.Image | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self.start_x = 0
        self.start_y = 0
        self.rect_id: int | None = None
        self.selected_region: tuple[int, int, int, int] | None = None

        self.tile_var = tk.StringVar(value=ALL_TILES[0])
        self.padding_var = tk.IntVar(value=2)
        self.status_var = tk.StringVar(value=f"已打开：{image_path.name}")

        self._build_ui()
        self._render_image()

    def _build_ui(self) -> None:
        root = ttk.Frame(self.root, padding=12)
        root.pack(fill="both", expand=True)
        self.root.option_add("*Font", ("Microsoft YaHei UI", 10))
        style = ttk.Style()
        style.configure("TFrame", background="#111318")
        style.configure("TLabel", background="#111318", foreground="#D8DEE9")
        style.configure("TButton", padding=(10, 6))

        toolbar = ttk.Frame(root)
        toolbar.pack(fill="x", pady=(0, 10))

        title = ttk.Label(toolbar, text="雀神模板采集", foreground="#F2C572", font=("Microsoft YaHei UI", 14, "bold"))
        title.pack(side="left")

        ttk.Button(toolbar, text="打开截图", command=self.open_image).pack(side="right", padx=(8, 0))
        ttk.Button(toolbar, text="导出候选", command=self.export_candidates).pack(side="right", padx=(8, 0))

        controls = ttk.Frame(root)
        controls.pack(fill="x", pady=(0, 10))

        ttk.Label(controls, text="牌名").pack(side="left")
        tile_combo = ttk.Combobox(
            controls,
            textvariable=self.tile_var,
            values=[f"{tile}  {tile_label(tile)}" for tile in ALL_TILES],
            state="readonly",
            width=12,
        )
        tile_combo.current(0)
        tile_combo.bind("<<ComboboxSelected>>", self._sync_tile_var)
        tile_combo.pack(side="left", padx=(6, 14))
        self.tile_combo = tile_combo

        ttk.Label(controls, text="边距").pack(side="left")
        padding = ttk.Spinbox(controls, from_=0, to=20, textvariable=self.padding_var, width=5)
        padding.pack(side="left", padx=(6, 14))

        ttk.Button(controls, text="保存选区到模板", command=self.save_selection).pack(side="left")
        ttk.Label(controls, text="拖拽框住单张牌，再保存到对应目录。").pack(side="left", padx=(14, 0))

        canvas_frame = ttk.Frame(root)
        canvas_frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg="#0C0E12", highlightthickness=0, cursor="crosshair")
        y_scroll = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        x_scroll = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        status = ttk.Label(root, textvariable=self.status_var, foreground="#8EA0B8")
        status.pack(fill="x", pady=(10, 0))

    def _sync_tile_var(self, event: tk.Event | None = None) -> None:
        value = self.tile_combo.get().split()[0]
        self.tile_var.set(value)

    def _render_image(self) -> None:
        max_width = 1600
        width, height = self.source_image.size
        self.scale = min(1.0, max_width / max(1, width))
        display_size = (int(width * self.scale), int(height * self.scale))
        self.display_image = self.source_image.resize(display_size)
        self.photo = ImageTk.PhotoImage(self.display_image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.canvas.configure(scrollregion=(0, 0, display_size[0], display_size[1]))
        self.selected_region = None
        self.rect_id = None

    def open_image(self) -> None:
        file_name = filedialog.askopenfilename(
            title="选择完整牌桌截图",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("All files", "*.*"),
            ],
        )
        if not file_name:
            return
        self.image_path = Path(file_name)
        self.source_image = Image.open(self.image_path).convert("RGB")
        self.status_var.set(f"已打开：{self.image_path.name}")
        self._render_image()

    def export_candidates(self) -> None:
        try:
            export = collect_template_candidates(
                self.image_path,
                load_region_config(),
                CANDIDATES_DIR,
                region_keys=template_region_keys(include_opponents=True),
            )
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))
            return
        self.status_var.set(
            f"已导出 {len(export.candidates)} 个候选：{export.output_dir}"
        )
        messagebox.showinfo(
            "候选已导出",
            f"候选图和预览已保存到：\n{export.output_dir}\n\n"
            "把确认好的单张牌图复制到 samples/templates/<牌名>/ 即可。",
        )

    def save_selection(self) -> None:
        if self.selected_region is None:
            messagebox.showwarning("还没有选区", "请先拖拽框住一张牌。")
            return
        x, y, width, height = self.selected_region
        try:
            tile = self.tile_var.get().split()[0]
            path = save_template_crop(
                self.image_path,
                bbox=_region_from_tuple(x, y, width, height),
                tile=tile,
                template_dir=TEMPLATES_DIR,
                padding=int(self.padding_var.get()),
            )
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))
            return
        self.status_var.set(f"已保存模板：{path}")

    def on_press(self, event: tk.Event) -> None:
        canvas_x = int(self.canvas.canvasx(event.x))
        canvas_y = int(self.canvas.canvasy(event.y))
        self.start_x = canvas_x
        self.start_y = canvas_y
        if self.rect_id is not None:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            canvas_x,
            canvas_y,
            canvas_x,
            canvas_y,
            outline="#F2C572",
            width=2,
        )

    def on_drag(self, event: tk.Event) -> None:
        if self.rect_id is None:
            return
        canvas_x = int(self.canvas.canvasx(event.x))
        canvas_y = int(self.canvas.canvasy(event.y))
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, canvas_x, canvas_y)

    def on_release(self, event: tk.Event) -> None:
        canvas_x = int(self.canvas.canvasx(event.x))
        canvas_y = int(self.canvas.canvasy(event.y))
        x1, x2 = sorted((self.start_x, canvas_x))
        y1, y2 = sorted((self.start_y, canvas_y))
        if x2 - x1 < 4 or y2 - y1 < 4:
            self.selected_region = None
            return
        self.selected_region = (
            int(x1 / self.scale),
            int(y1 / self.scale),
            int((x2 - x1) / self.scale),
            int((y2 - y1) / self.scale),
        )
        x, y, width, height = self.selected_region
        self.status_var.set(f"已选择：x={x}, y={y}, width={width}, height={height}")

    def run(self) -> None:
        self.root.mainloop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="采集雀神争霸牌面模板。")
    parser.add_argument(
        "image",
        nargs="?",
        type=Path,
        help="完整牌桌截图。省略时使用 watch/inbox 或 samples/screenshots 中最新图片。",
    )
    parser.add_argument(
        "--export-candidates",
        action="store_true",
        help="按当前 regions.json 批量导出候选牌图和区域预览，不打开 UI。",
    )
    parser.add_argument(
        "--include-opponents",
        action="store_true",
        help="导出候选时包含对手弃牌/碰杠和中部河牌区域。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=CANDIDATES_DIR,
        help="候选图输出目录。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    image_path = args.image
    if image_path is None:
        image_path = find_latest_screenshot(
            [
                ROOT / "watch" / "inbox",
                ROOT / "samples" / "screenshots",
            ]
        )
    if image_path is None or not image_path.exists():
        print("没有找到截图。请传入图片路径，或先用截图器保存一张图。")
        return 2

    if args.export_candidates:
        export = collect_template_candidates(
            image_path,
            load_region_config(REGIONS_PATH),
            args.output_dir,
            region_keys=template_region_keys(True),
        )
        print(f"source: {image_path}")
        print(f"output: {export.output_dir}")
        print(f"manifest: {export.manifest_path}")
        print(f"region crops: {len(export.region_crops)}")
        print(f"candidates: {len(export.candidates)}")
        return 0

    TemplateCollectorApp(image_path).run()
    return 0


def _region_from_tuple(x: int, y: int, width: int, height: int):
    from queshen_agent.models import Region

    return Region(x, y, width, height)


if __name__ == "__main__":
    raise SystemExit(main())

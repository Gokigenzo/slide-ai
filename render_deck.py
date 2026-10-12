"""render_deck.py: Kết xuất file PPTX thành danh sách ảnh PNG từng slide phục vụ Visual QA."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from pptx import Presentation
except ImportError:
    Presentation = None


class RenderError(Exception):
    """Lớp ngoại lệ cơ sở cho các lỗi kết xuất slide."""
    pass


class DeckRenderer:
    """Bộ điều phối kết xuất file trình chiếu PPTX sang ảnh PNG trên Ubuntu."""

    def __init__(self, default_dpi: int = 150, timeout: int = 120):
        self.default_dpi = default_dpi
        self.timeout = timeout

    def _get_slide_count(self, pptx_path: Path) -> Optional[int]:
        """Đếm số slide thực tế trong PPTX bằng python-pptx nếu có thư viện."""
        if Presentation is not None:
            try:
                prs = Presentation(str(pptx_path))
                return len(prs.slides)
            except Exception:
                return None
        return None

    # ------------------------------------------------------------------
    # 1. Tầng 1: Kết xuất bằng GenOffice Adapter
    # ------------------------------------------------------------------

    def _render_genoffice(self, pptx_path: Path, output_dir: Path) -> List[Path]:
        """Thử gọi kết xuất qua module GenOfficeAdapter nếu khả dụng."""
        try:
            from adapters.genoffice import GenOfficeAdapter, GenOfficeError
            adapter = GenOfficeAdapter(default_timeout=self.timeout)
            preflight = adapter.preflight()
            if not preflight.get("available"):
                raise GenOfficeError(f"GenOffice không sẵn sàng: {preflight.get('error')}")

            images = adapter.render_slides(pptx_path, output_dir, timeout=self.timeout)
            if not images:
                raise GenOfficeError("GenOffice không tạo ra file ảnh nào.")
            return images
        except Exception as e:
            raise RenderError(f"Không thể kết xuất qua GenOffice: {e}")

    # ------------------------------------------------------------------
    # 2. Tầng 2: Kết xuất dự phòng bằng LibreOffice + pdftoppm (Linux)
    # ------------------------------------------------------------------

    def _render_libreoffice_fallback(self, pptx_path: Path, output_dir: Path) -> List[Path]:
        """Chuyển PPTX sang PDF bằng LibreOffice headless, sau đó dùng pdftoppm trích xuất ảnh PNG."""
        soffice_bin = shutil.which("soffice") or shutil.which("libreoffice")
        pdftoppm_bin = shutil.which("pdftoppm")

        if not soffice_bin:
            raise RenderError("Không tìm thấy lệnh 'soffice' hoặc 'libreoffice' trên hệ điều hành.")
        if not pdftoppm_bin:
            raise RenderError("Không tìm thấy công cụ 'pdftoppm' (gói poppler-utils) trên hệ điều hành.")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Bước 2.1: Chuyển PPTX thành PDF qua LibreOffice headless
            cmd_pdf = [
                soffice_bin,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(tmp_path),
                str(pptx_path),
            ]

            res_pdf = subprocess.run(
                cmd_pdf,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                shell=False,
            )
            if res_pdf.returncode != 0:
                raise RenderError(f"LibreOffice chuyển đổi PDF thất bại: {res_pdf.stderr.strip()}")

            expected_pdf = tmp_path / f"{pptx_path.stem}.pdf"
            if not expected_pdf.exists():
                raise RenderError("Không tìm thấy file PDF trung gian sau khi chuyển đổi.")

            # Bước 2.2: Dùng pdftoppm kết xuất PDF thành các ảnh PNG
            output_prefix = output_dir / "slide"
            cmd_ppm = [
                pdftoppm_bin,
                "-png",
                "-r",
                str(self.default_dpi),
                str(expected_pdf),
                str(output_prefix),
            ]

            res_ppm = subprocess.run(
                cmd_ppm,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                shell=False,
            )
            if res_ppm.returncode != 0:
                raise RenderError(f"pdftoppm kết xuất ảnh thất bại: {res_ppm.stderr.strip()}")

            # Tìm và sắp xếp danh sách file ảnh sinh ra
            rendered_files = list(output_dir.glob("slide-*.png"))
            if not rendered_files:
                rendered_files = list(output_dir.glob("slide_*.png"))

            # Sắp xếp số tự nhiên theo số trang (tránh lỗi slide-10 đứng trước slide-2)
            def natural_sort_key(p: Path):
                numbers = re.findall(r"\d+", p.stem)
                return int(numbers[-1]) if numbers else 0

            return sorted(rendered_files, key=natural_sort_key)

    # ------------------------------------------------------------------
    # 3. Điều phối chính và kiểm định danh mục ảnh (Render Manifest)
    # ------------------------------------------------------------------

    def render_deck(
        self,
        pptx_path: str | Path,
        output_dir: str | Path,
        force_fallback: bool = False,
    ) -> Dict[str, Any]:
        """Thực thi kết xuất slide, kiểm tra số lượng ảnh khớp với số slide và trả về manifest."""
        in_pptx = Path(pptx_path).resolve()
        out_dir = Path(output_dir).resolve()

        if not in_pptx.exists():
            raise FileNotFoundError(f"Không tìm thấy file PPTX: {in_pptx}")

        out_dir.mkdir(parents=True, exist_ok=True)
        expected_slides = self._get_slide_count(in_pptx)

        renderer_used = None
        images: List[Path] = []
        errors: List[str] = []

        # Thử phương thức chính: GenOffice (trừ khi có cờ ép dùng fallback)
        if not force_fallback:
            try:
                images = self._render_genoffice(in_pptx, out_dir)
                renderer_used = "genoffice"
            except Exception as e:
                errors.append(f"GenOffice renderer không thành công: {str(e)}")

        # Nếu GenOffice không khả dụng, chuyển sang LibreOffice headless dự phòng
        if not images:
            try:
                images = self._render_libreoffice_fallback(in_pptx, out_dir)
                renderer_used = "libreoffice_pdftoppm"
            except Exception as e:
                errors.append(f"Fallback renderer (LibreOffice) không thành công: {str(e)}")

        # Nếu cả 2 phương thức đều thất bại: Ghi nhận trạng thái để Graceful Degradation
        if not images:
            return {
                "success": False,
                "deck_path": str(in_pptx),
                "renderer_used": None,
                "expected_slides": expected_slides,
                "rendered_count": 0,
                "image_paths": [],
                "errors": errors,
            }

        # Đổi tên file về chuẩn thống nhất slide_01.png, slide_02.png... để Agent dễ kiểm soát
        normalized_images: List[Path] = []
        for idx, img_p in enumerate(images, start=1):
            target_name = out_dir / f"slide_{idx:02d}.png"
            if img_p != target_name:
                shutil.move(str(img_p), str(target_name))
            normalized_images.append(target_name)

        # Chốt chặn kiểm định: Số ảnh kết xuất phải khớp tuyệt đối số slide trong PPTX
        count_mismatch = False
        if expected_slides is not None and len(normalized_images) != expected_slides:
            count_mismatch = True
            errors.append(
                f"Lệch số lượng kết xuất: File PPTX có {expected_slides} slide "
                f"nhưng chỉ tạo được {len(normalized_images)} file ảnh."
            )

        success = (len(normalized_images) > 0) and not count_mismatch

        return {
            "success": success,
            "deck_path": str(in_pptx),
            "renderer_used": renderer_used,
            "expected_slides": expected_slides,
            "rendered_count": len(normalized_images),
            "image_paths": [str(p) for p in normalized_images],
            "errors": errors,
        }


def run_render(
    pptx_path: str,
    output_dir: str = "renders",
    output_manifest: Optional[str] = None,
    force_fallback: bool = False,
) -> Dict[str, Any]:
    """Hàm interface chuẩn dùng để import vào pipeline.py hoặc chạy trực tiếp từ dòng lệnh."""
    renderer = DeckRenderer()
    result = renderer.render_deck(
        pptx_path=pptx_path,
        output_dir=output_dir,
        force_fallback=force_fallback,
    )

    if output_manifest:
        out_p = Path(output_manifest).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Kết xuất file PowerPoint thành ảnh PNG từng slide phục vụ Visual QA[cite: 1]."
    )
    parser.add_argument("pptx_file", help="Đường dẫn đến file PPTX cần render")
    parser.add_argument(
        "--output-dir",
        "-o",
        default="renders",
        help="Thư mục lưu các ảnh PNG (mặc định: renders)",
    )
    parser.add_argument(
        "--manifest",
        "-m",
        default=None,
        help="Đường dẫn file JSON để ghi kết quả kết xuất (render_manifest.json)",
    )
    parser.add_argument(
        "--force-fallback",
        action="store_true",
        help="Bỏ qua GenOffice và ép dùng LibreOffice/pdftoppm",
    )

    args = parser.parse_args()

    res = run_render(
        pptx_path=args.pptx_file,
        output_dir=args.output_dir,
        output_manifest=args.manifest,
        force_fallback=args.force_fallback,
    )

    print(f"\n===== KẾT QUẢ RENDER SLIDE: {args.pptx_file} =====")
    print(f"Trạng thái: {'THÀNH CÔNG' if res['success'] else 'THẤT BẠI / CẢNH BÁO'}")
    print(f"Renderer đã sử dụng: {res['renderer_used'] or 'Không có'}")
    print(f"Số lượng ảnh đã tạo: {res['rendered_count']} / {res['expected_slides'] or '?'}")

    if res["errors"]:
        print("\n[CHI TIẾT LỖI]:")
        for err in res["errors"]:
            print(f"  - {err}")

    if not res["success"]:
        sys.exit(1)

    print(f"\nToàn bộ ảnh đã được lưu tại: {args.output_dir}")
    sys.exit(0)
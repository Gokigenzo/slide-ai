"""adapters/genoffice.py: Adapter kết nối và điều phối công cụ GenOffice trên Ubuntu."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


class GenOfficeError(Exception):
    """Lớp ngoại lệ cơ sở cho các lỗi liên quan đến GenOffice."""
    pass


class GenOfficeNotAvailableError(GenOfficeError):
    """Ngoại lệ khi chưa cài đặt GenOffice hoặc môi trường chưa sẵn sàng."""
    pass


class GenOfficeExecutionError(GenOfficeError):
    """Ngoại lệ khi lệnh thực thi GenOffice trả về mã lỗi."""
    pass


class GenOfficeTimeoutError(GenOfficeError):
    """Ngoại lệ khi tác vụ GenOffice bị quá thời gian chờ (timeout)."""
    pass


class GenOfficeAdapter:
    """Bộ bọc giao diện tương tác với GenOffice qua CLI/subprocess an toàn."""

    def __init__(
        self,
        binary_path: Optional[str] = None,
        default_timeout: int = 120,
    ):
        # Ưu tiên lấy đường dẫn từ biến môi trường, tham số truyền vào hoặc tìm trong PATH
        self.binary_path = (
            binary_path
            or os.environ.get("GENOFFICE_BIN")
            or shutil.which("genoffice")
            or "genoffice"
        )
        self.default_timeout = default_timeout

    # ------------------------------------------------------------------
    # 1. Preflight: Kiểm tra năng lực môi trường (Graceful Degradation)
    # ------------------------------------------------------------------

    def preflight(self) -> Dict[str, Any]:
        """Kiểm tra sự tồn tại của GenOffice trong hệ điều hành trước khi sản xuất slide."""
        bin_resolved = shutil.which(self.binary_path)
        if not bin_resolved:
            return {
                "available": False,
                "binary_path": self.binary_path,
                "version": None,
                "error": f"Không tìm thấy file thực thi '{self.binary_path}' trong PATH.",
            }

        try:
            # Chạy kiểm tra phiên bản với danh sách đối số, không dùng shell=True
            result = subprocess.run(
                [bin_resolved, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                shell=False,
            )
            if result.returncode == 0:
                version_str = result.stdout.strip()
                return {
                    "available": True,
                    "binary_path": bin_resolved,
                    "version": version_str,
                    "error": None,
                }
            return {
                "available": False,
                "binary_path": bin_resolved,
                "version": None,
                "error": f"Lệnh kiểm tra trả về mã lỗi {result.returncode}: {result.stderr.strip()}",
            }
        except subprocess.TimeoutExpired:
            return {
                "available": False,
                "binary_path": bin_resolved,
                "version": None,
                "error": "Timeout khi kiểm tra phiên bản GenOffice.",
            }
        except Exception as e:
            return {
                "available": False,
                "binary_path": bin_resolved,
                "version": None,
                "error": f"Lỗi không xác định khi gọi GenOffice: {str(e)}",
            }

    # ------------------------------------------------------------------
    # 2. Build Deck: Tạo bài trình chiếu từ DeckSpec
    # ------------------------------------------------------------------

    def build_deck(
        self,
        deck_spec_path: Path | str,
        output_pptx_path: Path | str,
        template_name: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Gọi GenOffice để sản xuất file PPTX từ file đặc tả deck_spec.json."""
        spec_p = Path(deck_spec_path).resolve()
        out_p = Path(output_pptx_path).resolve()
        timeout_sec = timeout or self.default_timeout

        # Kiểm tra trước: Tránh chạy nếu spec không tồn tại
        if not spec_p.exists():
            raise FileNotFoundError(f"Không tìm thấy file đặc tả: {spec_p}")

        # Kiểm tra preflight: Nếu backend chưa sẵn sàng, kích hoạt dừng an toàn
        status = self.preflight()
        if not status["available"]:
            raise GenOfficeNotAvailableError(
                f"GenOffice chưa sẵn sàng: {status['error']}. "
                "Hệ thống sẽ giữ nguyên dàn ý và dừng trước bước sản xuất."
            )

        # Đảm bảo thư mục đích tồn tại
        out_p.parent.mkdir(parents=True, exist_ok=True)

        # Xây dựng danh sách tham số an toàn (không nối chuỗi shell để chống command injection)
        cmd: List[str] = [
            str(status["binary_path"]),
            "build",
            "--spec",
            str(spec_p),
            "--output",
            str(out_p),
        ]

        if template_name:
            cmd.extend(["--template", str(template_name)])

        try:
            # Thực thi tác vụ nặng có giới hạn thời gian
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                shell=False,
            )

            if process.returncode != 0:
                raise GenOfficeExecutionError(
                    f"GenOffice hoàn tất với mã lỗi {process.returncode}:\n{process.stderr.strip()}"
                )

            # Kiểm tra tính toàn vẹn: File đầu ra phải thực sự tồn tại và có dung lượng > 0
            if not out_p.exists() or out_p.stat().st_size == 0:
                raise GenOfficeExecutionError(
                    "Lệnh thành công nhưng không tìm thấy file PPTX đầu ra hoặc file rỗng."
                )

            return {
                "success": True,
                "output_path": str(out_p),
                "stdout": process.stdout.strip(),
            }

        except subprocess.TimeoutExpired as e:
            raise GenOfficeTimeoutError(
                f"Tác vụ tạo slide bằng GenOffice bị quá thời gian ({timeout_sec}s)."
            ) from e

    # ------------------------------------------------------------------
    # 3. Render Slides: Kết xuất slide thành ảnh để Visual QA
    # ------------------------------------------------------------------

    def render_slides(
        self,
        pptx_path: Path | str,
        output_dir: Path | str,
        timeout: Optional[int] = None,
    ) -> List[Path]:
        """Kết xuất từng slide trong file PPTX thành danh sách ảnh PNG phục vụ kiểm tra thị giác."""
        in_pptx = Path(pptx_path).resolve()
        out_d = Path(output_dir).resolve()
        timeout_sec = timeout or self.default_timeout

        if not in_pptx.exists():
            raise FileNotFoundError(f"Không tìm thấy file PPTX: {in_pptx}")

        out_d.mkdir(parents=True, exist_ok=True)

        cmd: List[str] = [
            str(self.binary_path),
            "render",
            "--input",
            str(in_pptx),
            "--output-dir",
            str(out_d),
            "--format",
            "png",
        ]

        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                shell=False,
            )

            if process.returncode != 0:
                raise GenOfficeExecutionError(
                    f"Render slide thất bại (Mã lỗi {process.returncode}):\n{process.stderr.strip()}"
                )

            # Lấy danh sách ảnh PNG đã sinh ra và sắp xếp theo tên
            rendered_images = sorted(list(out_d.glob("slide_*.png")))
            if not rendered_images:
                # Tìm kiếm bất kỳ ảnh png nào nếu định dạng tên khác
                rendered_images = sorted(list(out_d.glob("*.png")))

            return rendered_images

        except subprocess.TimeoutExpired as e:
            raise GenOfficeTimeoutError(
                f"Tác vụ render slide bị quá thời gian ({timeout_sec}s)."
            ) from e
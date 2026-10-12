"""extract_sources.py: Trích xuất cấu trúc, mục lục, bảng biểu và vị trí tham chiếu từ tài liệu nguồn."""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from schema import SourceFile, SourceManifest, SourceSection


def get_utc_now() -> str:
    """Lấy thời gian hiện tại theo chuẩn ISO 8601 UTC."""
    return datetime.now(timezone.utc).isoformat()


def compute_sha256(filepath: Path) -> str:
    """Tính mã băm SHA-256 để kiểm soát tính toàn vẹn của tệp nguồn."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class SourceExtractor:
    """Bộ xử lý trích xuất tài liệu nguồn đa định dạng."""

    def __init__(self, project_dir: Optional[Path] = None):
        self.project_dir = project_dir or Path.cwd()
        self.section_counter = 1

    def _resolve_path(self, file_path_str: str) -> Path:
        p = Path(file_path_str)
        if not p.is_absolute():
            p = self.project_dir / p
        if not p.exists():
            raise FileNotFoundError(f"Không tìm thấy file nguồn: {p}")
        return p

    # ------------------------------------------------------------------
    # 1. Trình bóc tách Markdown & TXT
    # ------------------------------------------------------------------

    def _parse_markdown(self, path: Path) -> List[SourceSection]:
        sections: List[SourceSection] = []
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        current_heading = "Mở đầu"
        current_points: List[str] = []
        line_start = 1

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Bắt các tiêu đề Markdown (#, ##, ###)
            header_match = re.match(r"^(#{1,4})\s+(.+)$", stripped)
            if header_match:
                if current_points:
                    sections.append(
                        SourceSection(
                            section_id=f"SEC-{self.section_counter:02d}",
                            heading=current_heading,
                            order=self.section_counter,
                            locator=f"Dòng {line_start}–{idx - 1}",
                            key_points=current_points,
                            example_refs=[],
                        )
                    )
                    self.section_counter += 1
                    current_points = []
                current_heading = header_match.group(2).strip()
                line_start = idx
            elif stripped:
                if stripped.startswith(("-", "*", "•")):
                    pt = stripped.lstrip("-*• ").strip()
                    if pt:
                        current_points.append(pt)
                elif len(stripped) > 5:
                    current_points.append(stripped)

        if current_points:
            sections.append(
                SourceSection(
                    section_id=f"SEC-{self.section_counter:02d}",
                    heading=current_heading,
                    order=self.section_counter,
                    locator=f"Dòng {line_start}–{len(lines)}",
                    key_points=current_points,
                    example_refs=[],
                )
            )
            self.section_counter += 1

        return sections

    # ------------------------------------------------------------------
    # 2. Trình bóc tách DOCX
    # ------------------------------------------------------------------

    def _parse_docx(self, path: Path) -> List[SourceSection]:
        try:
            import docx
        except ImportError:
            raise ImportError(
                "Thiếu thư viện 'python-docx' để đọc file DOCX. Hãy cài: pip install python-docx"
            )

        doc = docx.Document(str(path))
        sections: List[SourceSection] = []
        current_heading = "Phần mở đầu"
        current_points: List[str] = []
        para_start = 1

        for idx, p in enumerate(doc.paragraphs, start=1):
            text = p.text.strip()
            if not text:
                continue

            # Nhận diện tiêu đề qua Paragraph Style hoặc định dạng Heading
            is_heading = p.style.name.startswith("Heading") or (
                len(text) < 80 and p.runs and p.runs[0].bold
            )

            if is_heading:
                if current_points:
                    sections.append(
                        SourceSection(
                            section_id=f"SEC-{self.section_counter:02d}",
                            heading=current_heading,
                            order=self.section_counter,
                            locator=f"Đoạn {para_start}–{idx - 1}",
                            key_points=current_points,
                            example_refs=[],
                        )
                    )
                    self.section_counter += 1
                    current_points = []
                current_heading = text
                para_start = idx
            else:
                current_points.append(text)

        if current_points:
            sections.append(
                SourceSection(
                    section_id=f"SEC-{self.section_counter:02d}",
                    heading=current_heading,
                    order=self.section_counter,
                    locator=f"Đoạn {para_start}–{len(doc.paragraphs)}",
                    key_points=current_points,
                    example_refs=[],
                )
            )
            self.section_counter += 1

        return sections

    # ------------------------------------------------------------------
    # 3. Trình bóc tách PDF
    # ------------------------------------------------------------------

    def _parse_pdf(self, path: Path) -> List[SourceSection]:
        try:
            import pdfplumber
        except ImportError:
            raise ImportError(
                "Thiếu thư viện 'pdfplumber' để trích xuất file PDF. Hãy cài: pip install pdfplumber"
            )

        sections: List[SourceSection] = []
        with pdfplumber.open(str(path)) as pdf:
            if len(pdf.pages) == 0:
                raise ValueError(f"Tệp PDF '{path.name}' rỗng, không chứa trang nào.")

            for page_idx, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                lines = [l.strip() for l in text.split("\n") if l.strip()]

                if not lines:
                    # Cảnh báo trang quét hoặc trang ảnh cần OCR
                    continue

                # Lấy dòng đầu tiên làm tiêu đề mục tạm thời nếu chưa có heading rõ
                heading = lines[0] if len(lines[0]) < 100 else f"Nội dung trang {page_idx}"
                body_points = lines[1:] if len(lines) > 1 else [lines[0]]

                sections.append(
                    SourceSection(
                        section_id=f"SEC-{self.section_counter:02d}",
                        heading=heading,
                        order=self.section_counter,
                        locator=f"Trang {page_idx}",
                        key_points=body_points,
                        example_refs=[],
                    )
                )
                self.section_counter += 1

        if not sections:
            raise ValueError(
                f"Tệp PDF '{path.name}' không trích xuất được chữ (nghi ngờ là tài liệu scan hoặc ảnh phẳng)."
            )

        return sections

    # ------------------------------------------------------------------
    # 4. Trình bóc tách PPTX nguồn
    # ------------------------------------------------------------------

    def _parse_pptx(self, path: Path) -> List[SourceSection]:
        try:
            from pptx import Presentation
        except ImportError:
            raise ImportError(
                "Thiếu thư viện 'python-pptx'. Hãy cài: pip install python-pptx"
            )

        prs = Presentation(str(path))
        sections: List[SourceSection] = []

        for idx, slide in enumerate(prs.slides, start=1):
            slide_title = f"Slide {idx}"
            points: List[str] = []

            for shape in slide.shapes:
                if shape.has_text_frame:
                    t = shape.text_frame.text.strip()
                    if not t:
                        continue
                    if shape == slide.shapes[0] and len(t) < 100:
                        slide_title = t
                    else:
                        points.extend([line.strip() for line in t.split("\n") if line.strip()])

            if not points:
                points = [f"Nội dung trích xuất từ slide gốc số {idx}"]

            sections.append(
                SourceSection(
                    section_id=f"SEC-{self.section_counter:02d}",
                    heading=slide_title,
                    order=self.section_counter,
                    locator=f"Slide {idx}",
                    key_points=points,
                    example_refs=[],
                )
            )
            self.section_counter += 1

        return sections

    # ------------------------------------------------------------------
    # 5. Điều phối chính (Main Execution)
    # ------------------------------------------------------------------

    def extract_manifest(self, source_files: List[SourceFile]) -> SourceManifest:
        """Đọc và tạo toàn bộ SourceManifest từ danh sách các file nguồn[cite: 1]."""
        all_sections: List[SourceSection] = []
        file_hashes: Dict[str, str] = {}
        self.section_counter = 1

        for src in source_files:
            file_p = self._resolve_path(src.path)
            file_hashes[src.path] = compute_sha256(file_p)

            # Bỏ qua bóc tách chữ đối với tài liệu chỉ đóng vai trò visual_reference[cite: 1]
            if src.role == "visual_reference":
                continue

            # Điều phối theo media_type
            if src.media_type in ("md", "txt"):
                extracted = self._parse_markdown(file_p)
            elif src.media_type == "docx":
                extracted = self._parse_docx(file_p)
            elif src.media_type == "pdf":
                extracted = self._parse_pdf(file_p)
            elif src.media_type == "pptx":
                extracted = self._parse_pptx(file_p)
            else:
                continue

            all_sections.extend(extracted)

        if not all_sections:
            raise ValueError(
                "Không trích xuất được bất kỳ mục kiến thức nào từ các nguồn có vai trò 'content'[cite: 1]."
            )

        return SourceManifest(
            sources=source_files,
            sections=all_sections,
            file_hashes=file_hashes,
            extracted_at=get_utc_now(),
        )


def run_extraction(
    request_json_path: str | Path, output_manifest_path: Optional[str | Path] = None
) -> SourceManifest:
    """Đọc từ file request.json, chạy trích xuất và xuất ra file source_manifest.json[cite: 1]."""
    req_path = Path(request_json_path).resolve()
    with open(req_path, "r", encoding="utf-8") as f:
        req_data = json.load(f)

    sources = [SourceFile.model_validate(s) for s in req_data.get("source_files", [])]
    project_dir = req_path.parent

    extractor = SourceExtractor(project_dir=project_dir)
    manifest = extractor.extract_manifest(sources)

    out_p = (
        Path(output_manifest_path).resolve()
        if output_manifest_path
        else project_dir / "source_manifest.json"
    )
    with open(out_p, "w", encoding="utf-8") as f:
        f.write(manifest.model_dump_json(indent=2))

    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Trích xuất cấu trúc mục nguồn và vị trí tham chiếu vào source_manifest.json[cite: 1]."
    )
    parser.add_argument("request_json", help="Đường dẫn tới tệp request.json")
    parser.add_argument(
        "--output", "-o", default=None, help="Đường dẫn lưu source_manifest.json"
    )

    args = parser.parse_args()
    try:
        manifest_res = run_extraction(args.request_json, args.output)
        print(f"Trích xuất thành công {len(manifest_res.sections)} mục nội dung[cite: 1].")
        print(f"Đã lưu manifest vào: {args.output or 'source_manifest.json'}")
        sys.exit(0)
    except Exception as err:
        print(f"Lỗi khi trích xuất tài liệu nguồn: {err}", file=sys.stderr)
        sys.exit(1)
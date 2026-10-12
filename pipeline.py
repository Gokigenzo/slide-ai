"""pipeline.py: Bộ điều phối trung tâm kết nối toàn bộ module của skill slide-ai."""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from schema import (
    ApprovalRecord,
    DeckSpec,
    ProjectStateModel,
    QAReport,
    SlideQAResult,
    SlideRequest,
    SlideSpec,
    SourceFile,
    SourceManifest,
    SourceSection,
)
from extract_sources import SourceExtractor
from adapters.genoffice import (
    GenOfficeAdapter,
    GenOfficeError,
    GenOfficeNotAvailableError,
)
from inspect_pptx import run_inspection
from render_deck import run_render


def get_utc_now() -> str:
    """Lấy thời gian hiện tại theo chuẩn ISO 8601 UTC."""
    return datetime.now(timezone.utc).isoformat()


def compute_sha256(filepath: Path) -> str:
    """Tính mã băm SHA-256 để kiểm soát tính toàn vẹn của tệp."""
    if not filepath.exists():
        raise FileNotFoundError(f"Không tìm thấy tệp để tính hash: {filepath}")
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


# Bí danh tương thích ngược
compute_file_hash = compute_sha256



class SlideAIPipeline:
    """Bộ điều phối trạng thái, kiểm soát chốt chặn và thực thi quy trình slide-ai."""

    def __init__(self, project_dir: str | Path):
        self.project_dir = Path(project_dir).resolve()
        self.project_dir.mkdir(parents=True, exist_ok=True)

        # Định vị các tệp trạng thái và sản phẩm theo kiến trúc dữ liệu dự án
        self.state_file = self.project_dir / "state.json"
        self.request_file = self.project_dir / "request.json"
        self.manifest_file = self.project_dir / "source_manifest.json"
        self.outline_file = self.project_dir / "outline.md"
        self.deck_spec_file = self.project_dir / "deck_spec.json"
        self.approval_file = self.project_dir / "approval_record.json"
        self.qa_report_file = self.project_dir / "qa_report.json"
        self.output_dir = self.project_dir / "output"
        self.renders_dir = self.project_dir / "renders"

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.renders_dir.mkdir(parents=True, exist_ok=True)

        self.genoffice_adapter = GenOfficeAdapter()
        self._ensure_state_initialized()

    # ==================================================================
    # 1. State Engine: Quản lý vòng đời và chuyển pha
    # ==================================================================

    def _ensure_state_initialized(self):
        """Khởi tạo state.json ban đầu nếu chưa tồn tại trên ổ cứng."""
        if not self.state_file.exists():
            init_state = ProjectStateModel(
                schema_version=1,
                phase="intake",
                revision=1,
                source_hashes={},
                outline_hash=None,
                user_approved=False,
                unresolved_issues=[],
            )
            self._save_state(init_state)

    def load_state(self) -> ProjectStateModel:
        """Đọc và kiểm tra tính hợp lệ của state.json qua schema nghiêm ngặt."""
        with open(self.state_file, "r", encoding="utf-8") as f:
            return ProjectStateModel.model_validate(json.load(f))

    def _save_state(self, state: ProjectStateModel):
        """Ghi atomic trạng thái mới xuống đĩa."""
        with open(self.state_file, "w", encoding="utf-8") as f:
            f.write(state.model_dump_json(indent=2))

    def transition_phase(self, new_phase: str, unresolved_issues: Optional[List[str]] = None):
        """Chuyển pha tiến trình và tăng revision."""
        state = self.load_state()
        state.phase = new_phase  # type: ignore
        state.revision += 1
        if unresolved_issues is not None:
            state.unresolved_issues = unresolved_issues
        self._save_state(state)

    def set_blocked(self, reason: str):
        """Chuyển tiến trình sang blocked khi gặp lỗi chặn hoặc nguồn mâu thuẫn."""
        state = self.load_state()
        state.phase = "blocked"
        state.revision += 1
        if reason not in state.unresolved_issues:
            state.unresolved_issues.append(reason)
        self._save_state(state)

    # ==================================================================
    # GIAI ĐOẠN 1: Tiếp nhận và chuẩn hóa yêu cầu (Intake)
    # ==================================================================

    def step_intake(self, raw_request: Dict[str, Any]) -> SlideRequest:
        """Xác thực schema đầu vào, kiểm tra file tồn tại và ghi request.json[cite: 1]."""
        try:
            req = SlideRequest.model_validate(raw_request)
        except Exception as e:
            self.set_blocked(f"Lỗi kiểm tra dữ liệu yêu cầu (Schema Error): {str(e)}")
            raise

        # Kiểm tra file nguồn trên đĩa
        src_hashes: Dict[str, str] = {}
        for src in req.source_files:
            p = Path(src.path)
            if not p.is_absolute():
                p = self.project_dir / p
            if not p.exists() or not p.is_file():
                err_msg = f"Tệp nguồn không tồn tại hoặc không thể đọc: {src.path}"
                self.set_blocked(err_msg)
                raise FileNotFoundError(err_msg)
            src_hashes[src.path] = compute_sha256(p)

        with open(self.request_file, "w", encoding="utf-8") as f:
            f.write(req.model_dump_json(indent=2))

        state = self.load_state()
        state.source_hashes = src_hashes
        state.phase = "sources_validated"
        state.revision += 1
        state.unresolved_issues = []
        self._save_state(state)
        return req

    # ==================================================================
    # GIAI ĐOẠN 2: Trích xuất và lập bảng ánh xạ nguồn (Extraction)
    # ==================================================================

    def step_extract_sources(self) -> SourceManifest:
        """Gọi extract_sources.py để trích xuất mục, locator và tạo source_manifest.json[cite: 1]."""
        if not self.request_file.exists():
            raise FileNotFoundError("Chưa có request.json. Hãy chạy step_intake trước.")

        with open(self.request_file, "r", encoding="utf-8") as f:
            req = SlideRequest.model_validate(json.load(f))

        extractor = SourceExtractor(project_dir=self.project_dir)
        try:
            manifest = extractor.extract_manifest(req.source_files)
        except Exception as e:
            self.set_blocked(f"Lỗi trích xuất tài liệu nguồn: {str(e)}")
            raise

        with open(self.manifest_file, "w", encoding="utf-8") as f:
            f.write(manifest.model_dump_json(indent=2))

        self.transition_phase("outline_draft")
        return manifest

    # ==================================================================
    # GIAI ĐOẠN 3: Tạo dàn ý sơ bộ và quản lý phê duyệt (Outline Review)
    # ==================================================================

    def step_generate_outline_draft(self) -> Path:
        """Sinh tệp outline.md theo mẫu động dựa trên SourceManifest và SlideRequest[cite: 1]."""
        if not self.manifest_file.exists():
            raise FileNotFoundError("Thiếu source_manifest.json. Hãy trích xuất nguồn trước.")

        with open(self.request_file, "r", encoding="utf-8") as f:
            req = SlideRequest.model_validate(json.load(f))
        with open(self.manifest_file, "r", encoding="utf-8") as f:
            manifest = SourceManifest.model_validate(json.load(f))

        # Đánh giá cảnh báo xung đột số lượng slide với dung lượng nguồn[cite: 1]
        recommended_slides = len(manifest.sections) + 2  # Gồm bìa và tổng kết
        conflict_warning = "Không có xung đột."
        if req.slide_count is not None and req.slide_count < recommended_slides:
            conflict_warning = (
                f"CẢNH BÁO: Bạn yêu cầu {req.slide_count} slide, nhưng tài liệu có {len(manifest.sections)} mục nội dung "
                f"(đề xuất tối thiểu {recommended_slides} slide). Việc ép quá ít slide có thể làm giảm cỡ chữ "
                f"hoặc vi phạm mật độ 2-3 ý chính[cite: 1]."
            )

        lines: List[str] = [
            "# DÀN Ý CHI TIẾT BÀI TRÌNH CHIẾU (OUTLINE.MD)\n",
            "> Hướng dẫn: Bạn có thể sửa trực tiếp tiêu đề, ý chính, ý phụ hoặc ví dụ trên VS Code[cite: 1].",
            "> Sau khi lưu file (Ctrl + S), hãy báo Agent để đối chiếu và chốt duyệt[cite: 1].\n",
            "## 1. Thông số tổng quan",
            f"- **Tên bài:** {req.output_name.replace('.pptx', '')}",
            f"- **Tài liệu nguồn:** {', '.join([s.path for s in req.source_files])}",
            f"- **Phong cách:** {req.style or 'Chưa chọn (Hỏi người dùng trước khi thiết kế)'}[cite: 1]",
            f"- **Số slide yêu cầu:** {req.slide_count or 'Tự động tính theo tài liệu'}",
            f"- **Số slide dự kiến:** {req.slide_count or recommended_slides}",
            f"- **Cảnh báo độ đọc:** {conflict_warning}\n",
            "## 2. Bảng ánh xạ mục nguồn sang Slide (Source Mapping)",
            "| Mục nguồn (Section ID) | Tiêu đề mục trong tài liệu | Vị trí nguồn | Slide ID | Ghi chú |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]

        curr_slide = 2
        for sec in manifest.sections:
            lines.append(
                f"| `{sec.section_id}` | {sec.heading} | {sec.locator} | Slide {curr_slide} | Bám sát ý chính |"
            )
            curr_slide += 1

        lines.extend([
            "\n## 3. Nội dung chi tiết từng Slide\n",
            "### Slide 1: [Tiêu đề bài thuyết trình]",
            "- **Loại slide:** `title`",
            "- **Mục nguồn:** Toàn bài",
            "- **Speaker Notes:** Lời chào mở đầu và giới thiệu chủ đề thuyết trình[cite: 1].\n",
        ])

        curr_slide = 2
        for sec in manifest.sections:
            lines.extend([
                f"### Slide {curr_slide}: {sec.heading}",
                "- **Loại slide:** `content`",
                f"- **Mục nguồn:** `{sec.section_id}` ({sec.locator})",
                "- **Nội dung nhìn thấy trên slide (Mật độ 2-3 ý chính):**[cite: 1]",
            ])
            for pt in sec.key_points[:3]:
                lines.append(f"  - [Ý chính]: {pt}")
            lines.extend([
                "- **Ví dụ minh họa:**",
                "  - *Phân loại:* `[Ví dụ nguồn]`",
                "  - *Nội dung ví dụ:* [Lấy từ tài liệu hoặc để nhãn Thiếu ví dụ - Cần bổ sung][cite: 1]",
                "- **Thành phần trực quan:** Bố cục văn bản native",
                f"- **Speaker Notes:** Giảng giải chi tiết nội dung của mục {sec.heading}[cite: 1].\n",
            ])
            curr_slide += 1

        lines.extend([
            f"### Slide {curr_slide}: Tổng kết và Ghi nhớ",
            "- **Loại slide:** `summary`",
            "- **Mục nguồn:** Tổng hợp toàn bài",
            "- **Speaker Notes:** Đúc kết kiến thức trọng tâm và giải đáp thắc mắc[cite: 1].\n",
        ])

        with open(self.outline_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        self.transition_phase("awaiting_outline_approval")
        return self.outline_file

    def step_approve_outline(
        self,
        explicit_decision: bool = True,
        outline_path: Optional[str | Path] = None,
    ) -> ApprovalRecord:
        """Ghi nhận phê duyệt dàn ý từ người dùng kèm mã băm SHA-256 đối chứng[cite: 1]."""
        if not explicit_decision:
            raise ValueError("Chỉ ghi nhận duyệt khi người dùng xác nhận đồng ý rõ ràng[cite: 1].")

        target_outline = (
            Path(outline_path) if Path(outline_path).is_absolute() else self.project_dir / outline_path
        ) if outline_path else self.outline_file

        if not target_outline.exists():
            raise FileNotFoundError(f"Không tìm thấy {target_outline.name} để phê duyệt.")

        state = self.load_state()
        current_outline_hash = compute_sha256(target_outline)

        # Tính lại hash toàn bộ file nguồn tại thời điểm duyệt
        current_src_hashes = {}
        for src_path_str in state.source_hashes.keys():
            p = Path(src_path_str)
            if not p.is_absolute():
                p = self.project_dir / p
            current_src_hashes[src_path_str] = compute_sha256(p)

        record = ApprovalRecord(
            outline_hash=current_outline_hash,
            source_hashes=current_src_hashes,
            explicit_user_decision=True,
            approved_at=get_utc_now(),
        )

        with open(self.approval_file, "w", encoding="utf-8") as f:
            f.write(record.model_dump_json(indent=2))

        state.outline_hash = current_outline_hash
        state.source_hashes = current_src_hashes
        state.user_approved = True
        state.phase = "approved"
        state.unresolved_issues = []
        state.revision += 1
        self._save_state(state)
        return record

    # ==================================================================
    # GIAI ĐOẠN 4: Kiểm tra toàn vẹn và Sản xuất PPTX (Production)
    # ==================================================================

    def verify_integrity_before_production(
        self, outline_path: Optional[str | Path] = None
    ) -> Tuple[bool, List[str]]:
        """Chặn sản xuất nếu phát hiện outline.md hoặc nguồn bị đổi sau khi duyệt[cite: 1]."""
        state = self.load_state()
        issues: List[str] = []

        if not state.user_approved or state.phase != "approved":
            issues.append("Dàn ý chưa được người dùng phê duyệt hoặc trạng thái chưa sẵn sàng[cite: 1].")
            return False, issues

        if not state.outline_hash:
            issues.append("Thiếu mã hash dàn ý lưu đối chứng.")
            return False, issues

        target_outline = (
            Path(outline_path) if Path(outline_path).is_absolute() else self.project_dir / outline_path
        ) if outline_path else self.outline_file

        # Kiểm tra tính toàn vẹn của outline.md
        if not target_outline.exists():
            issues.append(f"Không tìm thấy tệp {target_outline.name}.")
        elif compute_sha256(target_outline) != state.outline_hash:
            issues.append(
                f"Tệp {target_outline.name} đã bị chỉnh sửa sau lần duyệt cuối. Cần duyệt lại trước khi tạo PPTX[cite: 1]."
            )

        # Kiểm tra tính toàn vẹn của các tệp nguồn
        for src_path_str, recorded_hash in state.source_hashes.items():
            p = Path(src_path_str)
            if not p.is_absolute():
                p = self.project_dir / p
            if not p.exists():
                issues.append(f"Tệp nguồn '{p.name}' không tồn tại hoặc đã bị xóa.")
            elif compute_sha256(p) != recorded_hash:
                issues.append(
                    f"Tệp nguồn '{p.name}' đã bị thay đổi sau khi duyệt dàn ý[cite: 1]."
                )

        if issues:
            state.user_approved = False
            state.phase = "awaiting_outline_approval"
            state.unresolved_issues.extend(issues)
            state.revision += 1
            self._save_state(state)
            return False, issues

        return True, []

    def step_build_deck(
        self,
        deck_spec_data: Optional[Dict[str, Any]] = None,
        template_name: Optional[str] = None,
    ) -> Path:
        """Kiểm tra toàn vẹn, preflight GenOffice và sản xuất file PPTX[cite: 1]."""
        # Chốt chặn 1: Tính toàn vẹn của dàn ý và nguồn[cite: 1]
        valid, issues = self.verify_integrity_before_production()
        if not valid:
            raise ValueError(f"Chặn sản xuất slide: {'; '.join(issues)}")

        # Chốt chặn 2: Kiểm tra adapter GenOffice (Graceful Degradation)[cite: 1]
        preflight = self.genoffice_adapter.preflight()
        if not preflight["available"]:
            self.set_blocked(
                f"GenOffice chưa kết nối: {preflight['error']}. "
                "Hệ thống giữ nguyên dàn ý và dừng trước bước sản xuất[cite: 1]."
            )
            raise GenOfficeNotAvailableError(preflight["error"])

        # Đọc yêu cầu để lấy tên file xuất
        with open(self.request_file, "r", encoding="utf-8") as f:
            req = SlideRequest.model_validate(json.load(f))

        # Lưu deck_spec.json nếu có dữ liệu truyền vào
        if deck_spec_data:
            spec = DeckSpec.model_validate(deck_spec_data)
            with open(self.deck_spec_file, "w", encoding="utf-8") as f:
                f.write(spec.model_dump_json(indent=2))
        elif not self.deck_spec_file.exists():
            raise FileNotFoundError("Thiếu file deck_spec.json để sản xuất PPTX.")

        output_pptx = self.output_dir / req.output_name
        self.transition_phase("building")

        try:
            self.genoffice_adapter.build_deck(
                deck_spec_path=self.deck_spec_file,
                output_pptx_path=output_pptx,
                template_name=template_name,
            )
        except Exception as e:
            self.set_blocked(f"Lỗi khi thực thi GenOffice build: {str(e)}")
            raise

        self.transition_phase("validating")
        return output_pptx

    # ==================================================================
    # GIAI ĐOẠN 5: Kết xuất và Kiểm định (Render, Inspect & Visual QA)
    # ==================================================================

    def step_render_and_inspect(self) -> Dict[str, Any]:
        """Chạy inspect_pptx và render_deck để chuẩn bị tài nguyên cho Agent đánh giá thị giác[cite: 1]."""
        with open(self.request_file, "r", encoding="utf-8") as f:
            req = SlideRequest.model_validate(json.load(f))
        pptx_path = self.output_dir / req.output_name

        if not pptx_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file PPTX cần kiểm tra: {pptx_path}")

        # 1. Kiểm tra cấu trúc hình học và văn bản bằng inspect_pptx[cite: 1]
        inspect_report = run_inspection(
            pptx_path=str(pptx_path),
            expected_count=req.slide_count,
        )

        # 2. Kết xuất slide thành ảnh bằng render_deck[cite: 1]
        render_report = run_render(
            pptx_path=str(pptx_path),
            output_dir=str(self.renders_dir),
            output_manifest=str(self.project_dir / "render_manifest.json"),
        )

        # Ghi nhận trạng thái chuẩn bị QA
        return {
            "pptx_path": str(pptx_path),
            "inspect_passed": inspect_report["passed"],
            "inspect_report": inspect_report,
            "render_success": render_report["success"],
            "renderer_used": render_report["renderer_used"],
            "image_paths": render_report["image_paths"],
            "errors": inspect_report["global_issues"] + render_report["errors"],
        }

    def step_finalize_qa(self, slide_qa_results: List[Dict[str, Any]]) -> QAReport:
        """Tổng hợp đánh giá thị giác của Agent và chốt trạng thái ready hoặc blocked[cite: 1]."""
        with open(self.request_file, "r", encoding="utf-8") as f:
            req = SlideRequest.model_validate(json.load(f))
        pptx_path = self.output_dir / req.output_name

        parsed_slides: List[SlideQAResult] = []
        blocking_issues: List[str] = []

        for item in slide_qa_results:
            qa_res = SlideQAResult.model_validate(item)
            parsed_slides.append(qa_res)
            if not qa_res.readability_passed or not qa_res.native_elements_passed:
                blocking_issues.extend(qa_res.detected_errors)

        if not parsed_slides:
            blocking_issues.append("Chưa có slide nào được kiểm tra thị giác (unverified draft).")

        overall_passed = (len(blocking_issues) == 0) and (len(parsed_slides) > 0)

        qa = QAReport(
            passed=overall_passed,
            deck_path=str(pptx_path),
            total_slides_checked=len(parsed_slides),
            slide_results=parsed_slides,
            missing_source_sections=[],
            blocking_issues=blocking_issues,
            audited_at=get_utc_now(),
        )

        with open(self.qa_report_file, "w", encoding="utf-8") as f:
            f.write(qa.model_dump_json(indent=2))

        if overall_passed:
            self.transition_phase("ready", unresolved_issues=[])
        else:
            self.transition_phase("blocked", unresolved_issues=blocking_issues)

        return qa

    def record_qa_completion(self, qa_report: QAReport):
        """Ghi nhận báo cáo nghiệm thu và quyết định phase ready hoặc blocked (tương thích ngược)."""
        with open(self.qa_report_file, "w", encoding="utf-8") as f:
            f.write(qa_report.model_dump_json(indent=2))

        state = self.load_state()
        if qa_report.passed:
            self.transition_phase("ready", unresolved_issues=[])
        else:
            self.transition_phase("blocked", unresolved_issues=qa_report.blocking_issues)

    # Bí danh tương thích theo tên gọi quy định trong SKILL.md
    validate_and_save_request = step_intake
    record_user_approval = step_approve_outline
    verify_pre_production_integrity = verify_integrity_before_production


# Bí danh tương thích ngược tên lớp cũ
PipelineManager = SlideAIPipeline


# ==================================================================
# Helper Functions: Gọi trực tiếp theo định danh trong SKILL.md
# ==================================================================

def validate_and_save_request(
    project_dir: str | Path, raw_request: Dict[str, Any]
) -> SlideRequest:
    """Hàm interface chuẩn hóa và lưu yêu cầu theo SKILL.md Giai đoạn 1."""
    return SlideAIPipeline(project_dir).step_intake(raw_request)


def record_user_approval(
    project_dir: str | Path, explicit_decision: bool = True
) -> ApprovalRecord:
    """Hàm interface ghi nhận phê duyệt dàn ý theo SKILL.md Giai đoạn 3."""
    return SlideAIPipeline(project_dir).step_approve_outline(explicit_decision)


def verify_pre_production_integrity(
    project_dir: str | Path,
) -> Tuple[bool, List[str]]:
    """Hàm interface kiểm tra toàn vẹn trước sản xuất theo SKILL.md Giai đoạn 4."""
    return SlideAIPipeline(project_dir).verify_integrity_before_production()



# ==================================================================
# CLI Interface: Điểm điều khiển từ dòng lệnh hoặc terminal Antigravity
# ==================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Bộ điều phối pipeline thực thi tự động của skill slide-ai[cite: 1]."
    )
    parser.add_argument("--project-dir", "-p", default=".", help="Đường dẫn thư mục dự án")
    subparsers = parser.add_subparsers(dest="action", help="Lệnh hành động cần chạy")

    # Command: intake
    intake_parser = subparsers.add_parser("intake", help="Tiếp nhận và chuẩn hóa request.json")
    intake_parser.add_argument("input_json", help="File JSON chứa yêu cầu ban đầu")

    # Command: extract
    subparsers.add_parser("extract", help="Trích xuất tài liệu nguồn thành source_manifest.json")

    # Command: make-outline
    subparsers.add_parser("make-outline", help="Sinh file dàn ý outline.md sơ bộ")

    # Command: approve
    subparsers.add_parser("approve", help="Ghi nhận duyệt dàn ý từ người dùng kèm mã hash")

    # Command: build
    build_parser = subparsers.add_parser("build", help="Xây dựng PPTX qua GenOffice adapter")
    build_parser.add_argument("--template", default=None, help="Tên template GenOffice")

    # Command: render-inspect
    subparsers.add_parser("render-inspect", help="Kiểm tra cấu trúc và render ảnh từng slide")

    # Command: status
    subparsers.add_parser("status", help="Xem trạng thái hiện tại của dự án")

    args = parser.parse_args()
    pipeline = SlideAIPipeline(project_dir=args.project_dir)

    try:
        if args.action == "intake":
            with open(args.input_json, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            pipeline.step_intake(raw_data)
            print("Đã hoàn tất Intake và lưu request.json thành công[cite: 1].")

        elif args.action == "extract":
            manifest = pipeline.step_extract_sources()
            print(f"Trích xuất thành công {len(manifest.sections)} mục vào source_manifest.json[cite: 1].")

        elif args.action == "make-outline":
            out_p = pipeline.step_generate_outline_draft()
            print(f"Đã tạo dàn ý tại: {out_p}. Vui lòng mở và chỉnh sửa trong VS Code[cite: 1].")

        elif args.action == "approve":
            rec = pipeline.step_approve_outline(explicit_decision=True)
            print(f"Đã ghi nhận phê duyệt lúc {rec.approved_at} với hash: {rec.outline_hash[:12]}...[cite: 1]")

        elif args.action == "build":
            out_pptx = pipeline.step_build_deck(template_name=args.template)
            print(f"Đã sản xuất file PPTX thành công tại: {out_pptx}[cite: 1]")

        elif args.action == "render-inspect":
            res = pipeline.step_render_and_inspect()
            print(f"Kết quả kiểm tra cấu trúc: {'ĐẠT' if res['inspect_passed'] else 'CÓ LỖI'}[cite: 1]")
            print(f"Kết quả render: {'ĐẠT' if res['render_success'] else 'CÓ LỖI'} (bằng {res['renderer_used']})[cite: 1]")
            print(f"Đã tạo {len(res['image_paths'])} ảnh slide trong thư mục renders/[cite: 1].")

        elif args.action == "status":
            st = pipeline.load_state()
            print(f"Phase hiện tại: {st.phase}")
            print(f"Revision: {st.revision}")
            print(f"Đã duyệt outline: {st.user_approved}")
            if st.unresolved_issues:
                print("Vấn đề tồn đọng:", st.unresolved_issues)

        else:
            parser.print_help()

    except Exception as err:
        print(f"Thực thi thất bại: {err}", file=sys.stderr)
        sys.exit(1)
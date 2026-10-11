"""pipeline.py: Bộ điều phối trạng thái, kiểm tra tính toàn vẹn và thực thi luồng slide-ai."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from schema import (
    ApprovalRecord,
    ProjectStateModel,
    QAReport,
    SlideRequest,
    SourceFile,
    SourceManifest,
    SourceSection,
)


def get_utc_now() -> str:
    """Trả về thời gian UTC theo chuẩn ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def compute_file_hash(filepath: Path) -> str:
    """Tính toán mã băm SHA-256 của tệp để kiểm soát phiên bản."""
    if not filepath.exists():
        raise FileNotFoundError(f"Không tìm thấy tệp để tính hash: {filepath}")
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class PipelineManager:
    """Quản lý trạng thái dự án, lưu trữ file và kiểm soát các cổng chuyển bước."""

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir).resolve()
        self.project_dir.mkdir(parents=True, exist_ok=True)
        
        self.state_file = self.project_dir / "state.json"
        self.request_file = self.project_dir / "request.json"
        self.manifest_file = self.project_dir / "source_manifest.json"
        self.deck_spec_file = self.project_dir / "deck_spec.json"
        self.qa_report_file = self.project_dir / "qa_report.json"
        self.approval_file = self.project_dir / "approval_record.json"
        
        self._init_state()

    # ------------------------------------------------------------------
    # 1. Quản lý trạng thái (State Engine)
    # ------------------------------------------------------------------

    def _init_state(self):
        """Khởi tạo state.json nếu chưa tồn tại."""
        if not self.state_file.exists():
            initial_state = ProjectStateModel(
                schema_version=1,
                phase="intake",
                revision=1,
                source_hashes={},
                outline_hash=None,
                user_approved=False,
                unresolved_issues=[],
            )
            self._save_state(initial_state)

    def load_state(self) -> ProjectStateModel:
        """Đọc và xác thực trạng thái từ file state.json."""
        with open(self.state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ProjectStateModel.model_validate(data)

    def _save_state(self, state: ProjectStateModel):
        """Ghi atomic trạng thái mới vào đĩa."""
        with open(self.state_file, "w", encoding="utf-8") as f:
            f.write(state.model_dump_json(indent=2))

    def transition_phase(
        self,
        new_phase: str,
        unresolved_issues: Optional[List[str]] = None,
    ):
        """Chuyển đổi phase và tăng chỉ số revision."""
        state = self.load_state()
        state.phase = new_phase  # type: ignore
        state.revision += 1
        if unresolved_issues is not None:
            state.unresolved_issues = unresolved_issues
        self._save_state(state)

    def set_blocked(self, reason: str):
        """Đưa dự án vào trạng thái nghẽn kèm nguyên nhân chi tiết."""
        state = self.load_state()
        state.phase = "blocked"
        state.revision += 1
        if reason not in state.unresolved_issues:
            state.unresolved_issues.append(reason)
        self._save_state(state)

    # ------------------------------------------------------------------
    # 2. Gate 1: Tiếp nhận và kiểm tra sơ bộ (Intake & Preflight)
    # ------------------------------------------------------------------

    def validate_and_save_request(self, raw_input: Dict[str, Any]) -> SlideRequest:
        """Validate input bằng SlideRequest schema nghiêm ngặt và lưu vào request.json."""
        try:
            req = SlideRequest.model_validate(raw_input)
        except Exception as e:
            self.set_blocked(f"Lỗi xác thực yêu cầu đầu vào (Schema Validation): {str(e)}")
            raise

        # Kiểm tra sự tồn tại của các file nguồn trên hệ thống file
        for src in req.source_files:
            p = Path(src.path)
            if not p.is_absolute():
                p = self.project_dir / p
            if not p.exists() or not p.is_file():
                err_msg = f"Tệp nguồn không tồn tại hoặc không thể đọc: {src.path}"
                self.set_blocked(err_msg)
                raise FileNotFoundError(err_msg)

        # Lưu bản chuẩn hóa
        with open(self.request_file, "w", encoding="utf-8") as f:
            f.write(req.model_dump_json(indent=2))

        # Lưu hash ban đầu của các file nguồn
        state = self.load_state()
        state.source_hashes = {
            src.path: compute_file_hash(
                Path(src.path) if Path(src.path).is_absolute() else self.project_dir / src.path
            )
            for src in req.source_files
        }
        state.phase = "sources_validated"
        state.revision += 1
        self._save_state(state)
        return req

    # ------------------------------------------------------------------
    # 3. Gate 2 & 3: Phê duyệt Dàn ý và Kiểm soát toàn vẹn
    # ------------------------------------------------------------------

    def record_user_approval(self, outline_path_str: str, explicit_decision: bool) -> ApprovalRecord:
        """Ghi nhận quyết định phê duyệt kèm hash đối chứng tại thời điểm chốt."""
        if not explicit_decision:
            raise ValueError("Chỉ ghi nhận duyệt khi có quyết định chấp thuận rõ ràng từ người dùng.")

        outline_p = Path(outline_path_str)
        if not outline_p.is_absolute():
            outline_p = self.project_dir / outline_p

        if not outline_p.exists():
            raise FileNotFoundError(f"Không tìm thấy file dàn ý: {outline_path_str}")

        state = self.load_state()
        current_outline_hash = compute_file_hash(outline_p)

        # Tính toán lại hash nguồn hiện tại
        current_src_hashes = {}
        for src_path_str in state.source_hashes.keys():
            p = Path(src_path_str)
            if not p.is_absolute():
                p = self.project_dir / p
            current_src_hashes[src_path_str] = compute_file_hash(p)

        approval = ApprovalRecord(
            outline_hash=current_outline_hash,
            source_hashes=current_src_hashes,
            explicit_user_decision=True,
            approved_at=get_utc_now(),
        )

        with open(self.approval_file, "w", encoding="utf-8") as f:
            f.write(approval.model_dump_json(indent=2))

        state.outline_hash = current_outline_hash
        state.source_hashes = current_src_hashes
        state.user_approved = True
        state.phase = "approved"
        state.unresolved_issues = []
        state.revision += 1
        self._save_state(state)
        return approval

    def verify_pre_production_integrity(self, outline_path_str: str) -> Tuple[bool, List[str]]:
        """Chặn sản xuất nếu file nguồn hoặc outline bị sửa sau khi người dùng đã duyệt."""
        state = self.load_state()
        issues: List[str] = []

        if not state.user_approved or state.phase != "approved":
            issues.append("Dàn ý chưa được người dùng phê duyệt hoặc trạng thái chưa sẵn sàng.")
            return False, issues

        if not state.outline_hash:
            issues.append("Thiếu mã hash dàn ý đã duyệt để đối chiếu.")
            return False, issues

        # Kiểm tra tính toàn vẹn của dàn ý outline.md
        outline_p = Path(outline_path_str)
        if not outline_p.is_absolute():
            outline_p = self.project_dir / outline_p

        if compute_file_hash(outline_p) != state.outline_hash:
            issues.append(
                "Tệp dàn ý (outline.md) đã bị sửa đổi sau lần duyệt cuối. Cần duyệt lại."
            )

        # Kiểm tra tính toàn vẹn của các tệp nguồn
        for src_path_str, recorded_hash in state.source_hashes.items():
            p = Path(src_path_str)
            if not p.is_absolute():
                p = self.project_dir / p
            if compute_file_hash(p) != recorded_hash:
                issues.append(
                    f"Tệp nguồn '{p.name}' đã bị thay đổi sau lần duyệt cuối. Cần đọc lại nguồn."
                )

        if issues:
            # Tự động hủy trạng thái duyệt và đưa về awaiting_outline_approval
            state.user_approved = False
            state.phase = "awaiting_outline_approval"
            state.unresolved_issues.extend(issues)
            state.revision += 1
            self._save_state(state)
            return False, issues

        return True, []

    # ------------------------------------------------------------------
    # 4. Gate 4: Nghiệm thu bàn giao (Delivery Inspection)
    # ------------------------------------------------------------------

    def record_qa_completion(self, qa_report: QAReport):
        """Ghi nhận báo cáo nghiệm thu và quyết định phase ready hoặc blocked."""
        with open(self.qa_report_file, "w", encoding="utf-8") as f:
            f.write(qa_report.model_dump_json(indent=2))

        state = self.load_state()
        if qa_report.passed:
            state.phase = "ready"
            state.unresolved_issues = []
        else:
            state.phase = "blocked"
            state.unresolved_issues = qa_report.blocking_issues
        state.revision += 1
        self._save_state(state)
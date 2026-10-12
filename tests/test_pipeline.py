"""tests/test_pipeline.py: Unit tests cho pipeline.py và bộ điều phối SlideAIPipeline."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from adapters.genoffice import GenOfficeNotAvailableError
from pipeline import (
    SlideAIPipeline,
    record_user_approval,
    validate_and_save_request,
    verify_pre_production_integrity,
)
from schema import SlideRequest


class TestSlideAIPipeline:
    def setup_project(self, tmp_path):
        src_file = tmp_path / "source.md"
        src_file.write_text("# Chương 1: Kiến trúc\n- Ý 1\n- Ý 2\n# Chương 2: Thiết kế\n- Ý A\n- Ý B\n", encoding="utf-8")

        raw_req = {
            "schema_version": 1,
            "operation": "create",
            "project_dir": str(tmp_path),
            "source_files": [
                {"path": "source.md", "role": "content", "media_type": "md"}
            ],
            "target_deck": None,
            "audience": "Kỹ sư phần mềm",
            "language": "vi",
            "usage": "presentation_and_self_study",
            "slide_count": 4,
            "duration_minutes": 20,
            "style": "technical_report",
            "output_name": "architecture.pptx",
            "research_enabled": True,
            "outline_path": "outline.md",
        }
        return tmp_path, src_file, raw_req

    def test_init_creates_state_and_dirs(self, tmp_path):
        pipe = SlideAIPipeline(project_dir=tmp_path)
        assert pipe.state_file.exists()
        assert pipe.output_dir.exists()
        assert pipe.renders_dir.exists()

        state = pipe.load_state()
        assert state.phase == "intake"
        assert state.revision == 1
        assert state.user_approved is False

    def test_step_intake_success_and_blocked_on_error(self, tmp_path):
        tmp_dir, src_file, raw_req = self.setup_project(tmp_path)
        pipe = SlideAIPipeline(project_dir=tmp_dir)

        req = pipe.step_intake(raw_req)
        assert req.operation == "create"
        assert pipe.request_file.exists()

        state = pipe.load_state()
        assert state.phase == "sources_validated"
        assert "source.md" in state.source_hashes

        # Test thất bại khi tệp nguồn không tồn tại
        raw_req_bad = dict(raw_req, source_files=[{"path": "non_exist.md", "role": "content", "media_type": "md"}])
        with pytest.raises(FileNotFoundError):
            pipe.step_intake(raw_req_bad)

        bad_state = pipe.load_state()
        assert bad_state.phase == "blocked"
        assert len(bad_state.unresolved_issues) > 0

    def test_step_extract_and_generate_outline(self, tmp_path):
        tmp_dir, src_file, raw_req = self.setup_project(tmp_path)
        pipe = SlideAIPipeline(project_dir=tmp_dir)
        pipe.step_intake(raw_req)

        # Trích xuất nguồn
        manifest = pipe.step_extract_sources()
        assert pipe.manifest_file.exists()
        assert len(manifest.sections) == 2
        assert pipe.load_state().phase == "outline_draft"

        # Sinh dàn ý sơ bộ
        outline_path = pipe.step_generate_outline_draft()
        assert outline_path.exists()
        assert pipe.load_state().phase == "awaiting_outline_approval"

        content = outline_path.read_text(encoding="utf-8")
        assert "DÀN Ý CHI TIẾT BÀI TRÌNH CHIẾU" in content
        assert "SEC-01" in content
        assert "SEC-02" in content

    def test_step_approve_outline_and_integrity_guard(self, tmp_path):
        tmp_dir, src_file, raw_req = self.setup_project(tmp_path)
        pipe = SlideAIPipeline(project_dir=tmp_dir)
        pipe.step_intake(raw_req)
        pipe.step_extract_sources()
        pipe.step_generate_outline_draft()

        # Không cho phép duyệt nếu explicit_decision = False
        with pytest.raises(ValueError):
            pipe.step_approve_outline(explicit_decision=False)

        # Phê duyệt hợp lệ
        rec = pipe.step_approve_outline(explicit_decision=True)
        assert rec.explicit_user_decision is True
        assert pipe.approval_file.exists()

        state = pipe.load_state()
        assert state.phase == "approved"
        assert state.user_approved is True
        assert state.outline_hash is not None

        # Kiểm tra toàn vẹn thành công ngay sau khi duyệt
        valid, issues = pipe.verify_integrity_before_production()
        assert valid is True
        assert len(issues) == 0

        # Case 1: Chỉnh sửa outline.md sau khi duyệt -> HỦY DUYỆT
        with open(pipe.outline_file, "a", encoding="utf-8") as f:
            f.write("\n<!-- Thêm nội dung sau duyệt -->\n")

        valid_after_edit, issues_edit = pipe.verify_integrity_before_production()
        assert valid_after_edit is False
        assert any("đã bị chỉnh sửa sau lần duyệt cuối" in iss for iss in issues_edit)

        state_after_edit = pipe.load_state()
        assert state_after_edit.user_approved is False
        assert state_after_edit.phase == "awaiting_outline_approval"

        # Duyệt lại
        pipe.step_approve_outline(explicit_decision=True)
        assert pipe.verify_integrity_before_production()[0] is True

        # Case 2: Chỉnh sửa tệp nguồn sau khi duyệt -> HỦY DUYỆT
        with open(src_file, "a", encoding="utf-8") as f:
            f.write("\nThay đổi tài liệu gốc")

        valid_src, issues_src = pipe.verify_integrity_before_production()
        assert valid_src is False
        assert any("đã bị thay đổi sau khi duyệt" in iss for iss in issues_src)
        assert pipe.load_state().user_approved is False

    def test_step_build_deck_graceful_degradation_when_genoffice_missing(self, tmp_path):
        tmp_dir, src_file, raw_req = self.setup_project(tmp_path)
        pipe = SlideAIPipeline(project_dir=tmp_dir)
        pipe.step_intake(raw_req)
        pipe.step_extract_sources()
        pipe.step_generate_outline_draft()
        pipe.step_approve_outline(explicit_decision=True)

        # Giả lập genoffice không khả dụng trên máy
        pipe.genoffice_adapter.binary_path = "non_existent_genoffice_bin"

        with pytest.raises(GenOfficeNotAvailableError):
            pipe.step_build_deck()

        # Hệ thống phải chuyển sang blocked và ghi rõ lý do, không tạo file rỗng
        state = pipe.load_state()
        assert state.phase == "blocked"
        assert any("GenOffice chưa kết nối" in iss for iss in state.unresolved_issues)

    def test_step_finalize_qa_ready_and_blocked(self, tmp_path):
        tmp_dir, src_file, raw_req = self.setup_project(tmp_path)
        pipe = SlideAIPipeline(project_dir=tmp_dir)
        pipe.step_intake(raw_req)

        # Case 1: Thẩm định QA thành công (toàn bộ slide đạt)
        qa_results_pass = [
            {
                "slide_id": 1,
                "readability_passed": True,
                "native_elements_passed": True,
                "rendered_image_path": "renders/slide_01.png",
                "visual_feedback": "Đạt chuẩn",
                "detected_errors": [],
            },
            {
                "slide_id": 2,
                "readability_passed": True,
                "native_elements_passed": True,
                "rendered_image_path": "renders/slide_02.png",
                "visual_feedback": "Bố cục thoáng, chữ rõ",
                "detected_errors": [],
            },
        ]

        report_pass = pipe.step_finalize_qa(qa_results_pass)
        assert report_pass.passed is True
        assert pipe.load_state().phase == "ready"

        # Case 2: Thẩm định QA có lỗi chặn (chữ bị mờ hoặc rasterized)
        qa_results_fail = [
            {
                "slide_id": 1,
                "readability_passed": False,
                "native_elements_passed": True,
                "rendered_image_path": "renders/slide_01.png",
                "visual_feedback": "Chữ quá nhỏ, khó đọc",
                "detected_errors": ["Font size < 18pt"],
            }
        ]

        report_fail = pipe.step_finalize_qa(qa_results_fail)
        assert report_fail.passed is False
        assert pipe.load_state().phase == "blocked"
        assert "Font size < 18pt" in pipe.load_state().unresolved_issues

        # Case 3: Danh sách kết quả rỗng (unverified draft) -> Phải đánh dấu blocked
        report_empty = pipe.step_finalize_qa([])
        assert report_empty.passed is False
        assert pipe.load_state().phase == "blocked"

    def test_skill_md_helper_functions_and_aliases(self, tmp_path):
        tmp_dir, src_file, raw_req = self.setup_project(tmp_path)

        # 1. validate_and_save_request
        req = validate_and_save_request(tmp_dir, raw_req)
        assert req.operation == "create"

        pipe = SlideAIPipeline(project_dir=tmp_dir)
        pipe.step_extract_sources()
        pipe.step_generate_outline_draft()

        # 2. record_user_approval
        rec = record_user_approval(tmp_dir, explicit_decision=True)
        assert rec.explicit_user_decision is True

        # 3. verify_pre_production_integrity
        valid, issues = verify_pre_production_integrity(tmp_dir)
        assert valid is True
        assert len(issues) == 0


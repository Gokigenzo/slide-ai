"""tests/test_schema.py: Unit tests cho schema.py của skill slide-ai."""

import pytest
from pydantic import ValidationError

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


class TestSourceFileSchema:
    def test_valid_source_file(self):
        sf = SourceFile(
            path="docs/lesson1.md",
            role="content",
            media_type="md",
        )
        assert sf.path == "docs/lesson1.md"
        assert sf.role == "content"
        assert sf.media_type == "md"

    def test_empty_path_raises(self):
        with pytest.raises(ValidationError):
            SourceFile(path="   ", role="content", media_type="md")

    def test_invalid_role_raises(self):
        with pytest.raises(ValidationError):
            SourceFile(path="test.md", role="invalid_role", media_type="md")  # type: ignore

    def test_invalid_media_type_raises(self):
        with pytest.raises(ValidationError):
            SourceFile(path="test.xyz", role="content", media_type="xyz")  # type: ignore


class TestSlideRequestSchema:
    def get_valid_payload(self):
        return {
            "schema_version": 1,
            "operation": "create",
            "project_dir": "/tmp/test_project",
            "source_files": [
                {"path": "source.md", "role": "content", "media_type": "md"}
            ],
            "target_deck": None,
            "audience": "Sinh viên CNTT",
            "language": "vi",
            "usage": "presentation_and_self_study",
            "slide_count": 5,
            "duration_minutes": 30,
            "style": "academic_minimal",
            "output_name": "deck.pptx",
            "research_enabled": True,
            "outline_path": "outline.md",
        }

    def test_valid_request(self):
        payload = self.get_valid_payload()
        req = SlideRequest.model_validate(payload)
        assert req.operation == "create"
        assert req.slide_count == 5
        assert req.output_name == "deck.pptx"

    def test_forbid_extra_fields(self):
        payload = self.get_valid_payload()
        payload["unknown_extra_field"] = "hacked"
        with pytest.raises(ValidationError) as exc:
            SlideRequest.model_validate(payload)
        assert "extra_forbidden" in str(exc.value)

    def test_strict_types_rejected(self):
        payload = self.get_valid_payload()
        # Chuỗi số '5' thay vì int 5
        payload["slide_count"] = "5"
        with pytest.raises(ValidationError):
            SlideRequest.model_validate(payload)

        # bool thay vì int
        payload["slide_count"] = True
        with pytest.raises(ValidationError):
            SlideRequest.model_validate(payload)

    def test_negative_slide_count_rejected(self):
        payload = self.get_valid_payload()
        payload["slide_count"] = -1
        with pytest.raises(ValidationError):
            SlideRequest.model_validate(payload)

    def test_zero_slide_count_rejected(self):
        payload = self.get_valid_payload()
        payload["slide_count"] = 0
        with pytest.raises(ValidationError):
            SlideRequest.model_validate(payload)

    def test_output_name_must_end_with_pptx(self):
        payload = self.get_valid_payload()
        payload["output_name"] = "presentation.pdf"
        with pytest.raises(ValidationError):
            SlideRequest.model_validate(payload)

    def test_output_name_cannot_contain_path_separator(self):
        payload = self.get_valid_payload()
        payload["output_name"] = "subfolder/deck.pptx"
        with pytest.raises(ValidationError):
            SlideRequest.model_validate(payload)

    def test_create_operation_requires_content_source(self):
        payload = self.get_valid_payload()
        # Chỉ có visual_reference mà không có content
        payload["source_files"] = [
            {"path": "image.png", "role": "visual_reference", "media_type": "png"}
        ]
        with pytest.raises(ValidationError):
            SlideRequest.model_validate(payload)

    def test_revise_requires_target_deck(self):
        payload = self.get_valid_payload()
        payload["operation"] = "revise"
        payload["target_deck"] = None
        with pytest.raises(ValidationError):
            SlideRequest.model_validate(payload)

    def test_audit_requires_target_deck(self):
        payload = self.get_valid_payload()
        payload["operation"] = "audit"
        payload["source_files"] = []
        payload["target_deck"] = None
        with pytest.raises(ValidationError):
            SlideRequest.model_validate(payload)


class TestSourceSectionAndManifest:
    def test_valid_source_section(self):
        sec = SourceSection(
            section_id="SEC-01",
            heading="Giới thiệu",
            order=1,
            locator="Dòng 1–10",
            key_points=["Ý 1", "Ý 2"],
            example_refs=[],
        )
        assert sec.section_id == "SEC-01"
        assert len(sec.key_points) == 2

    def test_empty_key_points_rejected(self):
        with pytest.raises(ValidationError):
            SourceSection(
                section_id="SEC-01",
                heading="Giới thiệu",
                order=1,
                locator="Dòng 1–10",
                key_points=[],  # min_length=1
                example_refs=[],
            )

    def test_manifest_validation(self):
        manifest = SourceManifest(
            sources=[
                SourceFile(path="source.md", role="content", media_type="md")
            ],
            sections=[
                SourceSection(
                    section_id="SEC-01",
                    heading="Giới thiệu",
                    order=1,
                    locator="Dòng 1–10",
                    key_points=["Ý 1"],
                    example_refs=[],
                )
            ],
            file_hashes={"source.md": "abc123hash"},
            extracted_at="2026-10-12T00:00:00Z",
        )
        assert len(manifest.sections) == 1
        assert manifest.file_hashes["source.md"] == "abc123hash"


class TestDeckSpecSchema:
    def test_valid_deck_spec(self):
        spec = DeckSpec(
            schema_version=1,
            title="Bài giảng Kiến trúc phần mềm",
            style="academic_minimal",
            total_slides=2,
            slides=[
                SlideSpec(
                    slide_id=1,
                    section_ids=["SEC-01"],
                    title="Slide mở đầu",
                    slide_type="title",
                    main_points=["Giới thiệu môn học"],
                    supporting_points=[],
                    example_refs=[],
                    visual_refs=[],
                    speaker_notes="Chào các bạn sinh viên",
                ),
                SlideSpec(
                    slide_id=2,
                    section_ids=["SEC-01"],
                    title="Khái niệm kiến trúc",
                    slide_type="content",
                    main_points=["Định nghĩa 1", "Định nghĩa 2"],
                    supporting_points=["Chi tiết"],
                    example_refs=[],
                    visual_refs=[],
                    speaker_notes="Phân tích khái niệm",
                ),
            ],
        )
        assert spec.total_slides == 2

    def test_slide_count_mismatch_rejected(self):
        with pytest.raises(ValidationError):
            DeckSpec(
                schema_version=1,
                title="Mismatch Deck",
                style="technical_report",
                total_slides=3,  # Khai báo 3 nhưng chỉ có 1 slide
                slides=[
                    SlideSpec(
                        slide_id=1,
                        section_ids=["SEC-01"],
                        title="Slide 1",
                        slide_type="title",
                        main_points=["Ý chính"],
                        supporting_points=[],
                        example_refs=[],
                        visual_refs=[],
                        speaker_notes="Notes",
                    )
                ],
            )

    def test_non_sequential_slide_id_rejected(self):
        with pytest.raises(ValidationError):
            DeckSpec(
                schema_version=1,
                title="Non-sequential Deck",
                style="creative",
                total_slides=2,
                slides=[
                    SlideSpec(
                        slide_id=1,
                        section_ids=["SEC-01"],
                        title="Slide 1",
                        slide_type="title",
                        main_points=["Ý chính"],
                        supporting_points=[],
                        example_refs=[],
                        visual_refs=[],
                        speaker_notes="Notes",
                    ),
                    SlideSpec(
                        slide_id=3,  # Nhảy cóc từ 1 lên 3
                        section_ids=["SEC-02"],
                        title="Slide 3",
                        slide_type="content",
                        main_points=["Ý 1", "Ý 2"],
                        supporting_points=[],
                        example_refs=[],
                        visual_refs=[],
                        speaker_notes="Notes",
                    ),
                ],
            )

    def test_content_slide_density_too_many_points_rejected(self):
        with pytest.raises(ValidationError):
            SlideSpec(
                slide_id=2,
                section_ids=["SEC-01"],
                title="Quá nhiều ý",
                slide_type="content",
                main_points=["Ý 1", "Ý 2", "Ý 3", "Ý 4", "Ý 5", "Ý 6"],  # Vượt quá 5 ý chính
                supporting_points=[],
                example_refs=[],
                visual_refs=[],
                speaker_notes="Notes",
            )


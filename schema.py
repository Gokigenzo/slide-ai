"""schema.py: Khai báo dữ liệu và bộ kiểm tra strict typing cho skill slide-ai."""

from pathlib import Path
from typing import Dict, List, Literal, Optional
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)


class StrictBase(BaseModel):
    """Lớp cơ sở cấm ép kiểu ngầm và cấm các trường không khai báo."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )


def _validate_non_empty_str(value: Optional[str], field_name: str) -> Optional[str]:
    """Kiểm tra chuỗi không được để trống hoặc chỉ chứa khoảng trắng."""
    if value is not None and not value.strip():
        raise ValueError(f"Trường '{field_name}' không được là chuỗi rỗng.")
    return value


# ----------------------------------------------------------------------
# 1. Input Request Schema
# ----------------------------------------------------------------------

class SourceFile(StrictBase):
    """Khai báo file nguồn đầu vào."""

    path: StrictStr
    role: Literal["content", "visual_reference"]
    media_type: Literal["pdf", "docx", "pptx", "png", "jpg", "jpeg", "txt", "md"]

    @field_validator("path")
    @classmethod
    def check_path_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Đường dẫn file nguồn 'path' không được để trống.")
        return v.strip()


class SlideRequest(StrictBase):
    """Hợp đồng dữ liệu đầu vào cho mỗi phiên chạy của skill slide-ai."""

    schema_version: Literal[1] = 1
    operation: Literal["create", "revise", "audit"]
    project_dir: StrictStr
    source_files: List[SourceFile]
    target_deck: Optional[StrictStr] = None
    audience: Optional[StrictStr] = None
    language: StrictStr = "vi"
    usage: Literal["presentation_and_self_study"] = "presentation_and_self_study"
    slide_count: Optional[StrictInt] = Field(default=None, gt=0)
    duration_minutes: Optional[StrictInt] = Field(default=None, gt=0)
    style: Optional[Literal["academic_minimal", "technical_report", "creative"]] = None
    output_name: StrictStr
    research_enabled: StrictBool = True
    outline_path: StrictStr = "outline.md"

    @field_validator("project_dir", "language", "outline_path")
    @classmethod
    def check_non_empty_strings(cls, v: str, info) -> str:
        _validate_non_empty_str(v, info.field_name)
        return v.strip()

    @field_validator("target_deck", "audience")
    @classmethod
    def check_optional_non_empty_strings(cls, v: Optional[str], info) -> Optional[str]:
        return _validate_non_empty_str(v, info.field_name)

    @field_validator("output_name")
    @classmethod
    def validate_output_name(cls, v: str) -> str:
        clean_name = v.strip()
        if not clean_name:
            raise ValueError("output_name không được để trống.")
        if "/" in clean_name or "\\" in clean_name:
            raise ValueError("output_name chỉ là tên file, không được chứa ký tự đường dẫn '/' hoặc '\\'.")
        if not clean_name.lower().endswith(".pptx"):
            raise ValueError("output_name bắt buộc phải có đuôi mở rộng '.pptx'.")
        return clean_name

    @model_validator(mode="after")
    def validate_operation_constraints(self) -> "SlideRequest":
        # Ràng buộc nguồn nội dung
        if self.operation in ("create", "revise"):
            if not self.source_files:
                raise ValueError(f"Thao tác '{self.operation}' yêu cầu ít nhất một file nguồn.")
            has_content = any(src.role == "content" for src in self.source_files)
            if not has_content:
                raise ValueError(
                    f"Thao tác '{self.operation}' cần ít nhất một file nguồn mang vai trò 'content'."
                )

        # Ràng buộc target_deck
        if self.operation in ("revise", "audit") and not self.target_deck:
            raise ValueError(f"Thao tác '{self.operation}' bắt buộc phải cung cấp 'target_deck'.")

        return self


# ----------------------------------------------------------------------
# 2. Source Extraction & Outline Mapping
# ----------------------------------------------------------------------

class SourceSection(StrictBase):
    """Mục nội dung được trích xuất từ tài liệu nguồn."""

    section_id: StrictStr
    heading: StrictStr
    order: StrictInt = Field(ge=0)
    locator: StrictStr
    key_points: List[StrictStr] = Field(min_length=1)
    example_refs: List[StrictStr] = []

    @field_validator("section_id", "heading", "locator")
    @classmethod
    def check_section_strings(cls, v: str, info) -> str:
        _validate_non_empty_str(v, info.field_name)
        return v.strip()


class SourceManifest(StrictBase):
    """Toàn bộ danh mục nguồn và các mục trích xuất kèm hash phục vụ đối chiếu."""

    sources: List[SourceFile]
    sections: List[SourceSection]
    file_hashes: Dict[StrictStr, StrictStr]
    extracted_at: StrictStr


# ----------------------------------------------------------------------
# 3. Production Specification (Deck Spec)
# ----------------------------------------------------------------------

class SlideSpec(StrictBase):
    """Đặc tả chi tiết nội dung của từng slide trước khi đưa vào sản xuất."""

    slide_id: StrictInt = Field(gt=0)
    section_ids: List[StrictStr]
    title: StrictStr
    slide_type: Literal["title", "content", "diagram", "example", "summary"] = "content"
    main_points: List[StrictStr]
    supporting_points: List[StrictStr] = []
    example_refs: List[StrictStr] = []
    visual_refs: List[StrictStr] = []
    speaker_notes: StrictStr

    @field_validator("title", "speaker_notes")
    @classmethod
    def check_slide_strings(cls, v: str, info) -> str:
        _validate_non_empty_str(v, info.field_name)
        return v.strip()

    @model_validator(mode="after")
    def validate_slide_density(self) -> "SlideSpec":
        # Slide nội dung bình thường phải tuân thủ mật độ 2-3 ý chính (ngoại lệ cho bìa hoặc sơ đồ)
        if self.slide_type == "content":
            if len(self.main_points) < 1 or len(self.main_points) > 5:
                raise ValueError(
                    f"Slide {self.slide_id} ({self.title}): Số ý chính phải từ 1 đến 5 (khuyến nghị 2-3 ý)."
                )
        return self


class DeckSpec(StrictBase):
    """Đặc tả hoàn chỉnh của cả bộ slide gửi sang adapter công cụ sản xuất."""

    schema_version: Literal[1] = 1
    title: StrictStr
    style: Literal["academic_minimal", "technical_report", "creative"]
    total_slides: StrictInt = Field(gt=0)
    slides: List[SlideSpec]

    @model_validator(mode="after")
    def validate_deck_integrity(self) -> "DeckSpec":
        if len(self.slides) != self.total_slides:
            raise ValueError(
                f"Tổng số slide ({self.total_slides}) không khớp với danh sách slides ({len(self.slides)})."
            )
        # Kiểm tra tính liên tục của slide_id
        slide_ids = [s.slide_id for s in self.slides]
        if slide_ids != list(range(1, self.total_slides + 1)):
            raise ValueError("Chỉ số 'slide_id' phải đánh số nguyên liên tục bắt đầu từ 1.")
        return self


# ----------------------------------------------------------------------
# 4. State & Approval Records
# ----------------------------------------------------------------------

class ApprovalRecord(StrictBase):
    """Bản ghi bằng chứng phê duyệt dàn ý từ phía người dùng."""

    outline_hash: StrictStr
    source_hashes: Dict[StrictStr, StrictStr]
    explicit_user_decision: StrictBool
    approved_at: StrictStr


class ProjectStateModel(StrictBase):
    """Cấu trúc dữ liệu ghi vào file state.json của dự án."""

    schema_version: Literal[1] = 1
    phase: Literal[
        "intake",
        "sources_validated",
        "outline_draft",
        "awaiting_outline_approval",
        "approved",
        "building",
        "validating",
        "ready",
        "blocked",
    ]
    revision: StrictInt = Field(ge=1)
    source_hashes: Dict[StrictStr, StrictStr] = {}
    outline_hash: Optional[StrictStr] = None
    user_approved: StrictBool = False
    unresolved_issues: List[StrictStr] = []


# ----------------------------------------------------------------------
# 5. Quality Assurance & Audit Report
# ----------------------------------------------------------------------

class SlideQAResult(StrictBase):
    """Kết quả kiểm tra chi tiết của một slide sau render."""

    slide_id: StrictInt
    readability_passed: StrictBool
    native_elements_passed: StrictBool
    rendered_image_path: StrictStr
    visual_feedback: Optional[StrictStr] = None
    detected_errors: List[StrictStr] = []


class QAReport(StrictBase):
    """Báo cáo nghiệm thu hoàn chỉnh trước khi bàn giao file PPTX."""

    passed: StrictBool
    deck_path: StrictStr
    total_slides_checked: StrictInt
    slide_results: List[SlideQAResult]
    missing_source_sections: List[StrictStr] = []
    blocking_issues: List[StrictStr] = []
    audited_at: StrictStr
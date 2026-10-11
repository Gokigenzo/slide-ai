# Hợp đồng dàn ý và trạng thái

## source_manifest.json

Tạo object chỉ có schema_version=1 và sections (danh sách không rỗng). Mỗi section chỉ có section_id (duy nhất), heading, locator, source_path và key_points. Tất cả là chuỗi không rỗng, riêng key_points là danh sách chuỗi không rỗng. source_path phải trỏ đúng file content trong request. locator là trang/slide/mục hoặc dòng giúp đối chiếu. Danh sách sections giữ nguyên thứ tự nguồn. key_points không được bỏ kiến thức chính.

## outline.md

Mỗi slide là một fenced block mang nhãn `slide-spec`, chứa JSON object. Có thể sửa tiêu đề/ý/ví dụ/notes ngay trong block bằng VS Code. Văn bản ngoài block dùng cho góp ý; trước duyệt Agent phải xử lý góp ý, thể hiện thay đổi trong block rồi trình lại. Hash cả file bao gồm góp ý, tránh bỏ sót thay đổi.

Các trường bắt buộc: slide_id (duy nhất), kind (knowledge, cover, example, diagram), section_ids (danh sách ID nguồn), title, main_points (danh sách chuỗi), supporting_points (danh sách chuỗi), examples (danh sách object), visuals (danh sách chuỗi mô tả), speaker_notes (chuỗi không rỗng).

Mỗi example chỉ có origin (source/research), locator, text: chuỗi không rỗng; locator nghiên cứu là URL hoặc định danh nguồn có thể kiểm chứng. Validator kiểm tra khai báo, Agent phải tự đọc kiểm chứng. knowledge có 2–3 main_points; kind khác có 0–3 nhưng phải có ý hoặc visuals/examples. Cover có thể không có section_ids; slide khác bắt buộc có. Toàn deck phải phủ mọi section theo đúng thứ tự xuất hiện đầu tiên; được có nhiều slide cho một section. Cấm dùng source section hư cấu.

## State

intake → sources_validated → awaiting_outline_approval → approved. gate kiểm tra lại fingerprint trước production. GenOffice chưa kết nối nên gate trả lỗi GENOFFICE_NOT_CONNECTED, không chuyển building/ready.

state.json chứa schema_version, revision, phase, approval và timestamps. Fingerprint gồm request chuẩn hóa, nội dung tất cả source files, manifest và outline. Khi đổi request/nguồn/manifest/outline: gate hoặc check/refresh vô hiệu approval. Không dùng state file để thay xác nhận của người dùng.

Đây là kiểm tra cấu trúc. Phải kiểm tra riêng độ đúng nghĩa, đủ kiến thức, ý kiến ngoài block và chất lượng trình bày. Không đặt phase=ready thủ công.

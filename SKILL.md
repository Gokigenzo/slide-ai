---
name: slide-ai
description: Create, revise, and audit source-grounded, editable PowerPoint presentations for classroom presentation and self-study. Triggers when users ask to generate slides from documents, redesign cluttered slides, or audit PPTX content fidelity and readability. Does not trigger on general questions mentioning slide or installing GenOffice.
---

# Slide AI

Bộ chỉ dẫn điều phối Agent tạo, sửa và kiểm tra bài thuyết trình PowerPoint bám sát tài liệu nguồn, bảo đảm đối tượng chỉnh sửa được và đáp ứng độ đọc khi trình chiếu hoặc tự học.

## Khi nào sử dụng (When to Use)

Kích hoạt skill khi người dùng:

- Yêu cầu tạo slide từ tài liệu đính kèm (PDF, DOCX, PPTX, hình ảnh, văn bản)[cite: 1].
- Yêu cầu sửa đổi, tái thiết kế hoặc cải thiện độ đọc và bố cục của slide có sẵn[cite: 1].
- Yêu cầu kiểm tra (audit) file PPTX về độ bao phủ nội dung nguồn, bố cục và tính dễ đọc[cite: 1].
- Gọi trực tiếp tên skill `slide-ai`[cite: 1].

Không kích hoạt skill khi[cite: 1]:

- Câu hỏi chỉ chứa từ khóa "slide" trong ngữ cảnh hỏi đáp thông thường[cite: 1].
- Người dùng chỉ yêu cầu giải thích kiến thức bài học mà không có nhu cầu làm deck[cite: 1].
- Người dùng hỏi cách cài đặt GenOffice hoặc các phần mềm văn phòng khác[cite: 1].

## Các chính sách bất biến (Immutable Policies)

- Bám sát cấu trúc nguồn: Giữ đúng các mục của tài liệu nguồn, không tự ý thay đổi cấu trúc mục[cite: 1]. Bắt buộc lập bảng ánh xạ từng mục sang từng slide tương ứng[cite: 1].
- Mật độ thông tin: Mỗi slide chuẩn có từ 2 đến 3 ý chính, có thể thêm một vài ý phụ[cite: 1]. Slide bìa, slide sơ đồ và slide ví dụ phức tạp được áp dụng ngoại lệ riêng[cite: 1].
- Khả năng đọc trong lớp học: Cỡ chữ phải đủ lớn để đọc rõ khi chiếu[cite: 1]. Tuyệt đối không thu nhỏ chữ để cố nhét nội dung[cite: 1].
- Giữ thành phần chỉnh sửa được: Chữ, bảng và sơ đồ đầu ra phải ở dạng native shape/text chỉnh sửa được trực tiếp[cite: 1]. Không raster hóa toàn bộ slide hoặc chuyển bảng thành ảnh phẳng[cite: 1].
- Phân định Speaker Notes: Slide chứa nội dung và bằng chứng cần nhìn[cite: 1]. Speaker notes chỉ chứa lời thuyết trình và dẫn dắt, không dùng để cất giấu các ý chính bị cắt khỏi slide[cite: 1].
- Duyệt dàn ý trên VS Code: Phải tạo file `outline.md` để người dùng trực tiếp sửa và lưu trên VS Code[cite: 1]. Chỉ tiến hành sinh PPTX khi người dùng đã chốt phê duyệt rõ ràng[cite: 1]. Không bao giờ coi việc người dùng im lặng là đồng ý[cite: 1].
- Kiểm tra kết xuất (Render QA): Mọi bài thuyết trình phải được kết xuất thành ảnh và kiểm tra thị giác từng slide trước khi bàn giao[cite: 1]. Không nghiệm thu chỉ dựa vào việc file PPTX được lưu thành công[cite: 1].

## Quy trình thực thi 5 giai đoạn

### Giai đoạn 1: Tiếp nhận và kiểm tra sơ bộ (Intake)

1. Tiếp nhận prompt tự nhiên của người dùng, chuyển đổi thành dữ liệu có cấu trúc và chạy hàm `validate_and_save_request()` qua `pipeline.py`[cite: 1].
2. Nếu người dùng chưa xác định phong cách thiết kế (`style`), Agent phải dừng lại và hỏi người dùng chọn một trong ba phong cách[cite: 1]:
   - (a) Học thuật tối giản: Đơn giản tối đa, chỉ highlight điểm trọng tâm cần thiết[cite: 1].
   - (b) Báo cáo kỹ thuật: Bố cục kỹ thuật, bổ sung icon, sơ đồ hoặc flow khi cần[cite: 1].
   - (c) Sáng tạo: Bố cục sinh động hơn nhưng vẫn giữ độ đọc, chuẩn xác và nhất quán[cite: 1].
3. Nếu người dùng chưa nêu đối tượng người xem (`audience`), hỏi để xác định rõ trước khi lên dàn ý[cite: 1].

### Giai đoạn 2: Trích xuất và lập bảng ánh xạ nguồn (Extraction & Mapping)

1. Đọc toàn bộ nội dung từ các file nguồn thuộc vai trò `content`[cite: 1].
2. Lập danh mục mục nguồn (`SourceSection`), đánh số thứ tự và lưu vào `source_manifest.json`[cite: 1].
3. Ưu tiên lấy ví dụ trực tiếp trong tài liệu nguồn[cite: 1]. Nếu thiếu ví dụ minh họa, kích hoạt công cụ research để tìm ví dụ đã kiểm chứng và ghi chú rõ nguồn bổ sung[cite: 1].
4. Nếu phát hiện tài liệu có mâu thuẫn, sai lệch hoặc khó hiểu: Dừng ngay công việc, chỉ rõ vị trí và nội dung xung đột rồi hỏi người dùng; không tự phỏng đoán hay âm thầm sửa[cite: 1].

### Giai đoạn 3: Soạn dàn ý và chờ duyệt trên VS Code (Outline Review)

1. Tạo file `outline.md` tại thư mục dự án theo cấu trúc chuẩn[cite: 1]:
   - Bảng ánh xạ: Mục nguồn -> Slide ID -> Tiêu đề dự kiến[cite: 1].
   - Chi tiết từng slide: Tiêu đề, 2-3 ý chính, ý phụ, ví dụ (ghi rõ nguồn hoặc nhãn bổ sung), hình/bảng dự kiến, speaker notes[cite: 1].
2. Thông báo để người dùng mở `outline.md` trong VS Code chỉnh sửa trực tiếp[cite: 1].
3. Sau khi người dùng lưu và phản hồi đã hoàn tất:
   - Đọc lại bản `outline.md` mới nhất[cite: 1].
   - Đối chiếu các thay đổi với người dùng[cite: 1].
   - Chạy hàm `record_user_approval()` để ghi lại hash của `outline.md` và các file nguồn[cite: 1].

### Giai đoạn 4: Sản xuất slide qua Adapter (Production)

1. Gọi hàm `verify_pre_production_integrity()` từ `pipeline.py`[cite: 1]. Nếu phát hiện `outline.md` hoặc tài liệu nguồn bị sửa đổi sau khi duyệt, hủy trạng thái duyệt và yêu cầu chốt lại[cite: 1].
2. Chuyển đổi dàn ý thành đặc tả `deck_spec.json` tuân thủ nghiêm ngặt schema[cite: 1].
3. Chuyển giao dữ liệu sang adapter GenOffice để tạo file PPTX có chữ, bảng và sơ đồ chỉnh sửa được[cite: 1].

### Giai đoạn 5: Kết xuất và kiểm định thị giác (Render & Visual QA)

1. Kết xuất toàn bộ slide trong PPTX thành ảnh trong thư mục `renders/`[cite: 1].
2. Agent đọc và kiểm tra từng ảnh slide[cite: 1]:
   - Độ đọc: Chữ không bị che khuất, không trùng màu nền, khoảng cách lề hợp lý[cite: 1].
   - Bố cục: Không dùng màu sắc tùy tiện, khoảng trống hỗ trợ phân nhóm tốt[cite: 1].
   - Đối soát: Đối chiếu từng slide với tài liệu nguồn xem có thiếu ý hoặc sai lệch nội dung hay không[cite: 1].
3. Ghi toàn bộ kết quả vào `qa_report.json`[cite: 1]. Nếu phát hiện lỗi chặn, yêu cầu sửa và render lại slide đó trước khi bàn giao file cuối cùng[cite: 1].

## Cơ chế suy giảm tính năng có kiểm soát (Graceful Degradation)

- Lỗi nguồn mâu thuẫn hoặc khó hiểu: Dừng tiến trình, chuyển sang trạng thái `blocked`, trích xuất đoạn mâu thuẫn và vị trí để xin ý kiến người dùng[cite: 1].
- Adapter GenOffice chưa kết nối: Hoàn thành bước đọc nguồn, lập dàn ý `outline.md` và dừng trước giai đoạn sản xuất; không được tạo file rỗng rồi nhận là bài hoàn chỉnh[cite: 1].
- Công cụ research lỗi khi thiếu ví dụ: Đánh dấu rõ vị trí thiếu ví dụ trong dàn ý để người dùng tự điền; tuyệt đối không tự bịa thông tin[cite: 1].
- Không có công cụ render hoặc visual check: Bàn giao file PPTX dưới dạng bản nháp chưa kiểm định hình thức (`unverified draft`); không đánh dấu đã đạt kiểm tra hình thức trong báo cáo QA[cite: 1].
- Backend không hỗ trợ vẽ bảng/sơ đồ native: Thông báo rõ giới hạn kỹ thuật để người dùng chọn phương án; không âm thầm chụp ảnh phẳng để chèn vào slide[cite: 1].

## Các lỗi cấm kỵ (Strict Anti-Patterns)

- Tự ý thay đổi hoặc bỏ sót cấu trúc các mục của tài liệu gốc[cite: 1].
- Nhồi nhét chữ quá dày đặc hoặc thu nhỏ cỡ chữ để cố lấp đầy không gian slide[cite: 1].
- Tự chọn phong cách thiết kế thay cho người dùng khi chưa có sự thống nhất[cite: 1].
- Tự đánh dấu dàn ý đã được duyệt (`user_approved = True`) mà không có xác nhận rõ ràng từ người dùng[cite: 1].
- Sử dụng màu nền và màu chữ tương phản kém hoặc gradient thiếu chủ đích gây khó đọc[cite: 1].
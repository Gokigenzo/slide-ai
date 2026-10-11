# DÀN Ý CHI TIẾT BÀI TRÌNH CHIẾU (OUTLINE.MD)

> **Hướng dẫn người dùng (Boss):**
> 1. Dàn ý này được Agent phân bổ số slide và nội dung dựa trên:
>    - Số lượng slide bạn yêu cầu (nếu bạn đã chỉ định), HOẶC
>    - Tự động tính toán theo dung lượng và cấu trúc mục của tài liệu đính kèm.
> 2. Bạn có thể thêm, bớt slide, gộp/tách ý hoặc chỉnh sửa nội dung trực tiếp trong VS Code.
> 3. Sau khi chỉnh sửa xong, hãy lưu file (`Ctrl + S`) và báo Agent để đối chiếu và chốt duyệt.

---

## 1. Thông số và Cơ chế phân bổ số Slide

- **Tên bài trình chiếu:** [Nhập tiêu đề chính của bài thuyết trình]
- **Tài liệu nguồn đính kèm:** `[Tên file nguồn 1]`, `[Tên file nguồn 2]`
- **Chế độ xác định số lượng slide:**
  - [ ] **Người dùng chỉ định:** Cố định đúng `N` slide theo yêu cầu[cite: 1].
  - [ ] **Agent tự động đề xuất theo tài liệu:** Tính toán dựa trên số lượng mục nguồn và mật độ kiến thức (đảm bảo 2–3 ý chính/slide)[cite: 1].
- **Tổng số slide (dự kiến):** `[N]` slide (gồm Slide bìa, các slide nội dung và slide tổng kết)[cite: 1].
- **Cảnh báo xung đột độ đọc (nếu có):**
  - *Đánh giá:* [Không có xung đột / CẢNH BÁO: Số slide bạn yêu cầu (ví dụ: 5 slide) quá ít so với dung lượng tài liệu (gồm 8 mục kiến thức nặng). Nếu ép vào 5 slide sẽ vi phạm quy tắc cỡ chữ và mật độ ý. Đề xuất: Tăng lên X slide hoặc lược bớt các mục phụ][cite: 1].
- **Đối tượng người xem:** [Sinh viên đại học / Kỹ sư / v.v.][cite: 1]
- **Phong cách thiết kế:** `academic_minimal` | `technical_report` | `creative`[cite: 1]
- **Thời lượng dự kiến:** [Số phút] phút[cite: 1]

---

## 2. Bảng ánh xạ toàn diện: Mục nguồn → Danh sách Slide (Source Mapping)

> **Quy tắc phân bổ:**
> - Mỗi mục kiến thức lớn (`SEC-XX`) sẽ được phân bổ vào 1 hoặc nhiều slide tùy độ dài[cite: 1].
> - Nếu một mục có ví dụ phức tạp hoặc bài tập mẫu: Tách thành 1 slide lý thuyết + 1 slide ví dụ riêng[cite: 1].
> - Nếu một mục có sơ đồ/quy trình: Dành riêng 1 slide sơ đồ để đảm bảo kích thước trực quan đọc rõ[cite: 1].

| Mục nguồn (Section ID) | Tiêu đề mục trong tài liệu | Vị trí trong nguồn | Slide ID đảm nhiệm | Ghi chú bố cục & Tách slide |
| :--- | :--- | :--- | :--- | :--- |
| `SEC-01` | [Tên mục 1] | Trang 1–2 | Slide 2 | Gói gọn 1 slide (khái niệm nền tảng)[cite: 1] |
| `SEC-02` | [Tên mục 2] | Trang 3–5 | Slide 3, Slide 4 | Tách đôi: Slide 3 (nguyên lý), Slide 4 (bài tập mẫu)[cite: 1] |
| `SEC-03` | [Tên mục 3] | Trang 6 | Slide 5 | Dành riêng cho sơ đồ luồng dữ liệu[cite: 1] |
| `...` | `...` | `...` | `...` | Tự động mở rộng khớp 100% tài liệu gốc |
| `SEC-K` | [Tên mục K cuối cùng] | Trang M | Slide N-1 | Mục tổng kết kỹ thuật[cite: 1] |

---

## 3. Chi tiết nội dung phân bổ (Từ Slide 1 đến Slide N)

### Slide 1: [Tiêu đề bài trình chiếu]
- **Loại slide:** `title` (Bìa mở đầu)[cite: 1]
- **Mục nguồn:** Bao quát toàn bài
- **Phụ đề / Chủ đề:** [Tóm lược định hướng bài học/báo cáo]
- **Thông tin bổ sung:** [Người trình bày / Đơn vị / Ngày thực hiện]
- **Speaker Notes:** [Lời mở đầu, giới thiệu mục tiêu và lộ trình bài trình chiếu][cite: 1]

---

<!-- 
VÙNG NỘI DUNG TỰ ĐỘNG MỞ RỘNG (TỪ SLIDE 2 ĐẾN SLIDE N-1):
Số lượng slide trong vùng này tăng/giảm linh hoạt để phủ hết từ SEC-01 đến SEC-K.
Mỗi slide tuân thủ nghiêm ngặt mật độ 2-3 ý chính để giữ chữ to, rõ ràng khi chiếu lớp học.
-->

### Slide 2: [Tiêu đề mục SEC-01]
- **Loại slide:** `content`[cite: 1]
- **Mục nguồn:** `SEC-01` (Trang/Vị trí: [Vị trí cụ thể trong tài liệu])[cite: 1]
- **Nội dung nhìn thấy trên slide (Chuẩn 2–3 ý chính):**[cite: 1]
  - [Ý chính 1]: [Khái niệm cốt lõi, giữ đúng thuật ngữ nguồn][cite: 1]
    - [Ý phụ]: [Giải thích chi tiết ngắn gọn][cite: 1]
  - [Ý chính 2]: [Nguyên lý hoặc đặc tính kỹ thuật][cite: 1]
  - [Ý chính 3]: [Phạm vi ứng dụng hoặc lưu ý][cite: 1]
- **Ví dụ minh họa:**
  - *Phân loại:* `[Ví dụ nguồn]` (Trang X)[cite: 1]
  - *Nội dung ví dụ:* [Trích ví dụ ngắn gọn có sẵn trong tài liệu nguồn][cite: 1]
- **Thành phần trực quan:** Không có (bố cục chữ phân khối rõ ràng)[cite: 1]
- **Speaker Notes:** [Lời giảng giải, dẫn dắt các ý; không giấu kiến thức cần nhìn vào đây][cite: 1]

---

### Slide 3: [Tiêu đề phần lý thuyết mục SEC-02]
- **Loại slide:** `content`[cite: 1]
- **Mục nguồn:** `SEC-02` (Trang/Vị trí: [Vị trí cụ thể])[cite: 1]
- **Nội dung nhìn thấy trên slide:**
  - [Ý chính 1]: [Định nghĩa quy trình hoặc cơ chế hoạt động][cite: 1]
  - [Ý chính 2]: [Ràng buộc và điều kiện tiên quyết][cite: 1]
- **Ví dụ minh họa:**
  - *Phân loại:* `[Ví dụ bổ sung - Research]` (Nguồn kiểm chứng: [URL / Tên tài liệu])[cite: 1]
  - *Nội dung ví dụ:* [Ví dụ thực tế tìm qua công cụ research do tài liệu gốc thiếu ví dụ][cite: 1]
- **Thành phần trực quan:**
  - *Bảng so sánh:* Bảng dữ liệu native editable (chữ và ô sửa được trực tiếp)[cite: 1]
- **Speaker Notes:** [Hướng dẫn người nghe cách phân tích dữ liệu bảng so sánh][cite: 1]

---

### Slide 4: [Tiêu đề phần ví dụ / bài tập mẫu mục SEC-02]
- **Loại slide:** `example` (Slide tách riêng do ví dụ/bài toán có nhiều bước giải)[cite: 1]
- **Mục nguồn:** `SEC-02` (Trang/Vị trí: [Vị trí cụ thể])[cite: 1]
- **Nội dung nhìn thấy trên slide:**
  - [Ý chính 1]: [Đề bài bài toán / tình huống thực tế][cite: 1]
  - [Ý chính 2]: [Các bước xử lý thuật toán / giải pháp tuần tự][cite: 1]
  - [Ý chính 3]: [Kết quả đầu ra và đánh giá][cite: 1]
- **Ví dụ minh họa:**
  - *Phân loại:* `[Thiếu ví dụ - Cần bổ sung]` (Nếu research không có, gắn cờ để Boss tự điền tại đây)[cite: 1]
  - *Nội dung ví dụ:* [Để trống hoặc ghi chú cần bổ sung][cite: 1]
- **Thành phần trực quan:** Không có
- **Speaker Notes:** [Phân tích từng bước giải toán hoặc ca thực hành][cite: 1]

---

### Slide [i]: [Tiêu đề sơ đồ / luồng xử lý mục SEC-xx]
- **Loại slide:** `diagram` (Dành riêng cho sơ đồ kiến trúc, quy trình)[cite: 1]
- **Mục nguồn:** `SEC-xx` (Trang/Vị trí: [Vị trí cụ thể])[cite: 1]
- **Nội dung nhìn thấy trên slide:**
  - [Ý chính 1]: [Mô tả tổng thể kiến trúc / chu trình][cite: 1]
  - [Ý chính 2]: [Các thành phần tương tác chính][cite: 1]
- **Thành phần trực quan:**
  - *Sơ đồ:* Vẽ lại sơ đồ nguồn dạng native shapes có thể chỉnh sửa text và đường nối (không dùng ảnh chụp)[cite: 1]
- **Speaker Notes:** [Thuyết minh luồng truyền tín hiệu hoặc luồng dữ liệu qua từng khối][cite: 1]

---

<!-- [LẶP LẠI CÁC SLIDE TỪNG MỤC CHO ĐẾN HẾT TÀI LIỆU NGUỒN...] -->

---

### Slide [N]: [Tổng kết và Ghi nhớ cốt lõi]
- **Loại slide:** `summary` (Slide kết bài)[cite: 1]
- **Mục nguồn:** Tổng hợp toàn bộ các mục `SEC-01` đến `SEC-K`[cite: 1]
- **Nội dung nhìn thấy trên slide:**
  - [Ý chính 1]: [Điểm cốt lõi 1 cần ghi nhớ cho kỳ thi / ứng dụng][cite: 1]
  - [Ý chính 2]: [Điểm cốt lõi 2 cần ghi nhớ][cite: 1]
  - [Ý chính 3]: [Tài liệu tham khảo mở rộng hoặc bài tập tự luyện][cite: 1]
- **Ví dụ minh họa:** Không có
- **Thành phần trực quan:** Không có
- **Speaker Notes:** [Tóm lược toàn bộ thông điệp bài giảng, giải đáp thắc mắc của người nghe][cite: 1]
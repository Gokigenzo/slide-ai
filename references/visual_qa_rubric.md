# CHỈ DẪN ĐÁNH GIÁ THỊ GIÁC CHO AGENT (VISUAL QA RUBRIC)

> **Mục đích:** Quy định quy trình và tiêu chí đánh giá thị giác tự động mà Agent phải tuân thủ khi duyệt từng ảnh slide (`renders/slide_XX.png`). Agent không được phép nghiệm thu chỉ dựa trên việc xuất file PPTX thành công, mà phải trực tiếp nhìn từng bản render để bắt lỗi trình bày[cite: 1].

---

## 1. Quy trình thực hiện duyệt thị giác (Visual QA Workflow)

1. **Kiểm tra đầu vào:** Đọc tệp `render_manifest.json` do `render_deck.py` tạo ra[cite: 1]. Đảm bảo số lượng ảnh kết xuất khớp đúng 100% với số slide quy định trong `deck_spec.json`[cite: 1].
2. **Duyệt tuần tự từng slide:** Mở và xem từng ảnh `slide_01.png`, `slide_02.png` theo thứ tự[cite: 1].
3. **Áp dụng bảng tiêu chí (Rubric):** Chấm điểm từng slide theo 5 hạng mục bên dưới[cite: 1].
4. **Phân loại lỗi:**
   - Nếu xuất hiện **Lỗi chặn (Blocking Error)**: Đánh dấu `readability_passed: false` và yêu cầu sửa lại bố cục, sau đó kết xuất và kiểm tra lại slide đó[cite: 1].
   - Nếu chỉ có **Lưu ý nhỏ (Warning)**: Ghi chú vào `visual_feedback` nhưng vẫn có thể cho qua nếu không ảnh hưởng đến khả năng tiếp thu bài giảng[cite: 1].
5. **Tổng hợp báo cáo:** Ghi toàn bộ kết quả vào `qa_report.json` tuân thủ đúng định dạng `QAReport` trong `schema.py`[cite: 1].

---

## 2. Bảng tiêu chuẩn kiểm định 5 hạng mục

### Hạng mục 1: Độ đọc và Kích cỡ chữ khi chiếu lớp học (Readability)
- [ ] **Khả năng quan sát từ xa:** Slide phải phục vụ tốt cả mục đích chiếu giảng đường lẫn tự học cá nhân[cite: 1].
- [ ] **Quy tắc cỡ chữ:** Tuyệt đối không được thu nhỏ cỡ chữ xuống mức li ti để cố nhồi nhét nhiều nội dung vào một trang[cite: 1].
  - Tiêu đề slide: Phải nổi bật rõ ràng, dễ nhận biết ngay khi chuyển trang.
  - Các ý chính: Cỡ chữ phải đủ lớn, độ đậm vừa phải để sinh viên ngồi cuối lớp vẫn đọc rõ[cite: 1].
  - Ý phụ / Chú thích: Được phép nhỏ hơn ý chính nhưng không được mờ nhạt hoặc khó đọc.
- [ ] **Mật độ thông tin:** Duy trì chuẩn 2–3 ý chính cho slide nội dung[cite: 1]. Nếu slide chứa quá 5 đoạn văn dày đặc, đây là dấu hiệu vi phạm và cần tách slide[cite: 1].

### Hạng mục 2: Tương phản và Bảng màu (Contrast & Color Harmony)
- [ ] **Độ tương phản chữ/nền:** Chữ không được trùng hoặc gần màu với nền (ví dụ: chữ xám nhạt trên nền trắng, hoặc chữ xanh đậm trên nền tối)[cite: 1].
- [ ] **Tính nhất quán của màu nền:** Màu nền và phong cách hiển thị phải đồng nhất xuyên suốt bài giảng, không đổi màu nền tùy tiện giữa các slide thông thường[cite: 1].
- [ ] **Hạn chế màu sặc sỡ:** Cấm lạm dụng gradient màu mè, màu neon chói mắt hoặc kết hợp quá nhiều màu tương phản gắt gao thiếu chủ đích[cite: 1].
- [ ] **Màu nhấn (Highlight):** Chỉ dùng màu nhấn cho các từ khóa cốt lõi hoặc số liệu quan trọng cần ghi nhớ[cite: 1].

### Hạng mục 3: Bố cục, Căn lề và Khoảng trắng (Layout & Whitespace)
- [ ] **Không tràn lề (No Overflow):** Văn bản và hình ảnh phải cách biên slide ít nhất một khoảng an toàn (margin)[cite: 1]. Tuyệt đối không để chữ chạm sát mép hoặc bị cắt cụt khỏi khung hình[cite: 1].
- [ ] **Không chồng lấn (No Overlapping/Clipping):** Các khối văn bản, bảng biểu, icon và sơ đồ không được đè lên nhau hoặc che khuất chân trang (footer)[cite: 1].
- [ ] **Phân nhóm bằng khoảng trắng:** Khoảng trống (whitespace) phải hỗ trợ gom nhóm các ý liên quan với nhau; không ép các đối tượng giãn cách vô tội vạ để cố lấp đầy không gian slide[cite: 1].
- [ ] **Chống lãng phí không gian:** Không để xảy ra tình trạng chữ bị dồn ép vào một góc nhỏ trong khi 80% diện tích slide còn lại bị bỏ trống vô nghĩa[cite: 1].

### Hạng mục 4: Font chữ và Dấu tiếng Việt (Typography & Diacritics)
- [ ] **Hiển thị tiếng Việt:** Không bị lỗi font tiếng Việt (không bị tình trạng chữ có dấu bị đổi sang font dự phòng khác kiểu dáng, mất dấu tiếng Việt hoặc vỡ nét)[cite: 1].
- [ ] **Công thức và Ký hiệu:** Các công thức, ký hiệu toán học hoặc thuật ngữ kỹ thuật phải hiển thị ngay ngắn, rõ ràng, không bị biến thành ký tự lạ hay ô vuông (`[]`)[cite: 1].

### Hạng mục 5: Tính trung thực trực quan với nguồn (Source Fidelity)
- [ ] **Bảo toàn dữ liệu bảng/sơ đồ:** Nếu vẽ lại bảng hoặc sơ đồ từ tài liệu gốc, phải đối chiếu từng con số, quan hệ mũi tên và nhãn khối để đảm bảo không bị sai lệch nghĩa gốc[cite: 1].
- [ ] **Không raster hóa lén lút:** Bảng biểu và sơ đồ phải hiển thị dưới dạng vector sắc nét và đối tượng chỉnh sửa được, không có răng cưa mờ nhòe do chụp màn hình dán vào[cite: 1].

---

## 3. Danh mục lỗi chặn (Blocking Errors) - Bắt buộc sửa lại

Nếu phát hiện bất kỳ lỗi nào dưới đây, Agent **không được cấp phép bàn giao (`passed: false`)** mà phải điều chỉnh lại dàn ý/spec và render lại slide bị lỗi[cite: 1]:

1. **Chữ bị che khuất hoặc chồng lấn:** Hai hộp văn bản đè lên nhau khiến không đọc được nội dung[cite: 1].
2. **Tràn khung hiển thị:** Chữ hoặc thành phần sơ đồ rơi ra ngoài rìa slide[cite: 1].
3. **Màu chữ trùng màu nền:** Chữ bị chìm vào nền khiến người xem không thấy được chữ[cite: 1].
4. **Lỗi vỡ font / mất dấu tiếng Việt:** Xuất hiện lỗi hiển thị ký tự có dấu[cite: 1].
5. **Chữ quá nhỏ do nhồi nhét:** Cố tình ép cỡ chữ xuống quá nhỏ để nhét toàn bộ tài liệu vào một slide duy nhất[cite: 1].
6. **Bảng/Sơ đồ bị biến thành ảnh phẳng:** Toàn bộ slide chỉ là một tấm ảnh rasterized không thể chỉnh sửa chữ bên trong[cite: 1].

---

## 4. Định dạng phản hồi khi ghi vào `qa_report.json`

Với mỗi slide, Agent phải tổng hợp đánh giá thành một đối tượng `SlideQAResult` theo chuẩn[cite: 1]:

```json
{
  "slide_id": 2,
  "readability_passed": false,
  "native_elements_passed": true,
  "rendered_image_path": "renders/slide_02.png",
  "visual_feedback": "Khối ý chính 2 bị tràn xuống sát đáy slide và chồng lấn nhẹ lên số trang. Cỡ chữ ý phụ hơi nhỏ so với tiêu chuẩn lớp học.",
  "detected_errors": [
    "Text overflow tại khối ý chính 2",
    "Chồng lấn chân trang (footer overlap)"
  ]
}
# Hồ sơ đăng ký RE:ACT — EVA (bản nháp)

> File nháp để chỉnh sửa trước khi copy vào form đăng ký. Hạn nộp: 23h59 22/09/2026.
> Các chỗ đánh dấu `[ĐIỀN: ...]` cần bạn tự bổ sung — tôi không có thông tin đó.

---

## 1. Thông tin về vấn đề và nhóm người dùng mà giải pháp hướng tới

**Nhóm người dùng mục tiêu:** người cao tuổi và người khuyết tật (đặc biệt khuyết tật vận động, thị giác) tại Việt Nam, ưu tiên nhóm sống một mình hoặc không có người thân túc trực thường xuyên.

**Vấn đề:** các dịch vụ thiết yếu (đặt lịch khám bệnh, nhắc uống thuốc, liên lạc người thân, tra cứu thông tin) ngày càng chuyển sang app/website đòi hỏi gõ phím, chạm màn hình chính xác, đọc hiểu giao diện nhiều lớp menu — vượt quá khả năng của nhiều người cao tuổi/khuyết tật. Hệ quả:

- Phụ thuộc hoàn toàn vào người thân túc trực để dùng công nghệ thay mình.
- Dễ bỏ lỡ chăm sóc y tế (quên uống thuốc, không đặt được lịch khám).
- Tăng nguy cơ cô lập xã hội, không ai phát hiện kịp bất thường sức khoẻ khi sống một mình.
- Khuyết tật vận động/thị giác gặp thêm rào cản vật lý với chuột/bàn phím/màn hình nhỏ mà các giải pháp số hiện tại chưa tính đến.

[ĐIỀN: nếu có số liệu/nguồn tham khảo cụ thể về quy mô vấn đề tại VN — vd tỷ lệ người cao tuổi sống một mình, tỷ lệ người khuyết tật chưa tiếp cận dịch vụ số — nên thêm vào đây để tăng độ thuyết phục]

---

## 2. Mô tả cách thức hoạt động và vai trò của công nghệ

**EVA** là trợ lý AI hội thoại tiếng Việt, chạy thường trực (24/7) trên một máy tính đóng vai trò server tại nhà — không cần cửa sổ desktop, không cần người dùng chính thao tác gõ/chạm.

**Cách hoạt động:**
1. **Đánh thức không cần chạm máy** — gọi tên hoặc vỗ/búng tay 2 lần liên tiếp.
2. **Hiểu giọng nói tiếng Việt tự nhiên** — dùng PhoWhisper (mô hình speech-to-text chuyên biệt tiếng Việt), tự lọc tiếng ồn nền (VAD), cho phép ngắt lời giữa chừng bằng câu lệnh.
3. **Xác thực bằng giọng nói/khuôn mặt** — phân quyền "chủ nhân" để bảo vệ thông tin cá nhân/sức khoẻ của người dùng dễ bị tổn thương, có thể bật/tắt tuỳ nhu cầu.
4. **Trả lời và hành động thật** — dùng LLM (Ollama chạy local, hoặc Gemini khi cần online) kết hợp function calling để mở ứng dụng, tra cứu thông tin, đặt nhắc nhở — không chỉ trả lời suông.
5. **Chủ động, không chờ người dùng hỏi** — module theo dõi hoạt động/sức khoẻ tự phát hiện bất thường trong nếp sinh hoạt (giấc ngủ, mức độ hoạt động) và tự lên tiếng/cảnh báo, module nhắc lịch cố định (giờ uống thuốc, ăn sáng) chạy nền không cần thiết lập lại mỗi ngày.
6. **Dashboard giám sát cho người thân** — giao diện web tối giản (đồng hồ đo CPU/RAM, lịch sử hội thoại, ghi chú, danh sách người được uỷ quyền) để người chăm sóc theo dõi từ xa mà không cần người dùng chính thao tác.

**Vai trò của công nghệ:** AI ở đây không thay thế người chăm sóc mà **thu hẹp khoảng cách số** — biến giao diện phức tạp (gõ, chạm, đọc menu) thành hội thoại tự nhiên, đồng thời **chủ động quan sát** thay vì chờ người dùng biết cách "xin trợ giúp" — điều mà người cao tuổi/khuyết tật thường ngại hoặc không biết làm.

Chạy **offline bằng model local** (Ollama) giúp: (a) ổn định không phụ thuộc mạng — quan trọng với dịch vụ chăm sóc sức khoẻ liên tục, (b) chi phí vận hành thấp, phù hợp hộ gia đình thu nhập hạn chế, (c) giữ dữ liệu sức khoẻ/giọng nói/khuôn mặt cá nhân trong nhà, không gửi lên cloud bên thứ ba — đúng tinh thần sinh kế số bao trùm.

---

## 3. Bằng chứng cho thấy giải pháp đã có phiên bản hoạt động

EVA hiện là phần mềm **đã chạy thật, không phải mô hình/wireframe**, gồm các module đã hoàn thiện và vận hành:

- Nhận diện giọng nói tiếng Việt (PhoWhisper) + phát hiện giọng nói/lọc ồn (VAD) — hoạt động thời gian thực.
- Tổng hợp giọng nói trả lời (edge-tts) phát qua loa.
- Nhận diện người nói (voice ID, `resemblyzer`) và khuôn mặt (`deepface`) để phân quyền chủ nhân.
- Bộ não hội thoại có function calling thật (mở app, mở URL, kiểm tra hệ thống, đặt nhắc nhở, tra cứu git/log cho dev) — gần 1000 dòng logic tool trong `core/tools.py`.
- Module chủ động: theo dõi hoạt động (`activity_monitor.py`), sức khoẻ (`health_monitor.py`), nhắc lịch cố định (`daily_reminder.py`, `reminder_scheduler.py`), cảnh báo nhiệt độ GPU (`temp_monitor.py`).
- Dashboard web (Next.js + Flask) build sẵn, phục vụ file tĩnh thật, có API `/api/message`, `/api/voice`, `/api/status` hoạt động.
- Lưu trữ dữ liệu hội thoại/ghi chú/log sức khoẻ bằng SQLite (`core/database.py`, có schema đầy đủ).
- Cơ chế triển khai chạy nền thật trên Windows (`start_eva_hidden.vbs`, Task Scheduler qua `deploy/`), tự khởi động lại nếu crash.

→ Đây là **~13.000 dòng code** đã chạy được, không phải prototype giấy. [ĐIỀN: nếu có, gắn kèm link GitHub repo (có thể để private + mời reviewer), vài ảnh chụp màn hình dashboard, hoặc log/video ngắn quay lại một phiên tương tác thật để làm bằng chứng trực quan]

---

## 4. Kết quả thử nghiệm hoặc phản hồi từ người dùng, nếu có

[ĐIỀN — cần bạn xác nhận, tôi soạn 2 phương án tuỳ tình trạng thật]

**Nếu CHƯA thử nghiệm với người cao tuổi/khuyết tật:** nên viết thật, đừng bịa — ví dụ:
> "Sản phẩm đã được sử dụng thực tế hàng ngày trong [ĐIỀN: số tháng] qua bởi người sáng lập để kiểm chứng độ ổn định kỹ thuật (nhận diện giọng nói, nhắc lịch, theo dõi sức khoẻ chủ động). Đội chưa thử nghiệm chính thức với nhóm người dùng mục tiêu (người cao tuổi/khuyết tật) — đây sẽ là hoạt động đầu tiên trong giai đoạn Living Labs nếu được chọn, nhằm tinh chỉnh persona, tốc độ nói và độ đơn giản của lệnh giọng nói theo phản hồi thật."

**Nếu ĐÃ có người cao tuổi/khuyết tật nào dùng thử (kể cả không chính thức, vd người thân):**
[ĐIỀN: ai, dùng trong bao lâu, phản hồi cụ thể — dù chỉ 1-2 người cũng nên đưa vào, có bằng chứng thật luôn tốt hơn không có]

---

## 5. Pitch deck giới thiệu giải pháp

Chưa làm — có thể dựng nhanh bằng Claude (deck dạng .pptx/PDF) dựa trên nội dung mục 1-4 ở trên. Cho tôi biết nếu muốn tôi dựng luôn.

## 6. Video demo sản phẩm hoặc giải pháp đang hoạt động

Cần bạn tự quay (tôi không thể tạo video) — gợi ý kịch bản ngắn (60-90 giây) bám sát mục 2-3 ở trên:

1. (0-10s) Vỗ tay/gọi tên đánh thức EVA — cho thấy không cần chạm máy.
2. (10-30s) Ra lệnh giọng nói thật (vd "EVA mở YouTube", "EVA kiểm tra hệ thống giúp tôi") — cho thấy EVA hiểu và **thực sự thực hiện hành động**, không chỉ trả lời suông.
3. (30-50s) Cảnh đặt nhắc nhở bằng giọng nói ("nhắc tôi uống thuốc lúc 3 giờ chiều") rồi cho thấy nhắc nhở kích hoạt.
4. (50-75s) Lướt qua dashboard web trên điện thoại — cho người thân xem cách giám sát từ xa.
5. (75-90s) Một câu chốt bằng giọng nói của người thực hiện, nêu vấn đề + EVA giải quyết ra sao.

[ĐIỀN: link video sau khi quay xong]

---

## Việc còn thiếu (cần bạn điền trước khi nộp)

- Tên đội, danh sách thành viên + vai trò từng người
- Link GitHub repo (nếu form yêu cầu)
- Ảnh chụp màn hình / video ngắn làm bằng chứng mục 3
- Xác nhận thật về mục 4 (đã/chưa thử nghiệm với ai)
- Quyết định có cần tôi dựng pitch deck (mục 5) ngay không

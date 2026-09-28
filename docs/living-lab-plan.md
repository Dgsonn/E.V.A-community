# Kế hoạch Living Lab 6 tháng — EVA cho người cao tuổi/khuyết tật

> Phạm vi đã chốt lại với đội (khác với `.claude/plans/precious-tumbling-deer.md` — file đó có hệ thống vai trò primary/caregiver/guest đầy đủ, nay **thu gọn**):
> - EVA vẫn là **trợ lý cá nhân hoá cho 1 người dùng chính** (elderly/disabled), không xây hệ thống phân quyền nhiều vai trò.
> - "Người thân xem trạng thái từ xa" chỉ là **tính năng phụ, đơn giản** (dashboard chia sẻ được, không cần hệ thống permission/SMS/Zalo phức tạp) — không phải trọng tâm.
> - Phạm vi **không thu hẹp**: giữ nguyên toàn bộ trợ lý sinh hoạt hiện có (nhắc thuốc, sức khoẻ, điều khiển máy) + **thêm** khả năng hỗ trợ dùng máy tính bằng giọng nói làm năng lực mới.
> - Khung thời gian bám theo lộ trình RE:ACT: Living Labs 10/2026–3/2027, Demo Day dự kiến 1/2027 tại Hà Nội (nằm giữa pilot), chuyến học tập Hàn Quốc dự kiến 4/2027 (sau pilot).

## Mục tiêu 6 tháng

Đưa EVA từ "trợ lý cá nhân hoá cho 1 người dùng kỹ thuật (Sơn)" thành "trợ lý cá nhân dùng được thật cho người cao tuổi/khuyết tật", đo bằng: (1) họ tự thao tác máy tính bằng giọng nói mà không cần người khác làm hộ, (2) họ dùng EVA đều đặn (không rơi rụng sau tuần đầu), (3) có dữ liệu/phản hồi thật để báo cáo RE:ACT và làm nền cho vòng gọi vốn/nhân rộng tiếp theo.

## Tháng 1 (10/2026) — Nền tảng & tuyển hộ gia đình

**Kỹ thuật:**
- Bỏ hard-code tên "Sơn" trong `core/ai_brain.py` (SYSTEM_PROMPT, các câu thoại rải rác đã liệt kê ở lần khảo sát trước — `activity_monitor.py`, `health_monitor.py`, `reminder_scheduler.py`, `tts_engine.py`...), thay bằng tên người dùng cấu hình được (không cần bảng `users` đầy đủ — 1 giá trị tên trong `config/settings.yaml` là đủ vì vẫn 1 người dùng).
- Bắt đầu accessibility pass trên dashboard: cỡ chữ lớn hơn, tương phản đạt WCAG AA, `TokenGate` đơn giản hoá (PIN thay vì dán token dài).

**Vận hành:**
- Liên hệ hội người cao tuổi / tổ chức hỗ trợ người khuyết tật địa phương, tuyển 3–5 hộ gia đình pilot.
- Phỏng vấn baseline từng hộ: hiện đang gặp khó gì khi dùng máy tính/điện thoại, kỳ vọng gì.

**Cột mốc:** chọn xong hộ pilot, bản EVA đã bỏ persona cá nhân hoá cứng, sẵn sàng cài đặt.

## Tháng 2 (11/2026) — Triển khai v1 + điều khiển máy tính bằng giọng nói

**Kỹ thuật — năng lực mới, trọng tâm chính của pilot:**
- Mở rộng `core/tools.py` theo hướng "làm thay thao tác chuột/bàn phím": đọc to nội dung màn hình/tin nhắn, soạn thảo văn bản bằng giọng nói (dictation), điều hướng trình duyệt bằng lệnh nói thay vì chỉ mở URL cố định, gọi video call cho người thân bằng giọng nói.
- Luồng đăng ký/cài đặt đơn giản hoá — có người trong đội hỗ trợ cài trực tiếp tại nhà (chưa cần tự động hoá hoàn toàn ở giai đoạn này).

**Vận hành:**
- Cài EVA tại từng hộ, hướng dẫn trực tiếp 1 buổi/hộ.
- Bắt đầu check-in hàng tuần (gọi điện/ghé thăm ngắn) để bắt lỗi sớm.

**Cột mốc:** cả 3–5 hộ có EVA chạy thật, dùng được ít nhất 3 tác vụ máy tính cơ bản bằng giọng nói.

## Tháng 3 (12/2026) — Lặp theo phản hồi thật

**Kỹ thuật:**
- Sửa theo top pain-point thực tế (thường sẽ là: wake word nhận sai, nghe nhầm lệnh, tốc độ nói TTS quá nhanh/chậm, quên lệnh phải nói thế nào).
- Thêm bản "family view" đơn giản — 1 link/PIN xem trạng thái + lịch sử gần đây cho người thân, không cần hệ thống vai trò/permission phía sau, chỉ là 1 trang chỉ-đọc.
- Tinh chỉnh nhắc thuốc/sức khoẻ theo dữ liệu thật từng hộ (không dùng 1 giờ nhắc cố định chung).

**Vận hành:**
- Phỏng vấn giữa kỳ từng hộ, so với baseline tháng 1.

**Cột mốc:** tỷ lệ tự thao tác thành công (không cần người khác làm hộ) tăng rõ so với tháng 2.

## Tháng 4 (1/2027) — Demo Day + mở rộng tính năng

**Kỹ thuật:**
- Mở rộng thêm tác vụ máy tính theo nhu cầu thật đã thấy ở tháng 2-3 (nhiều khả năng: giải trí — mở nhạc/video theo yêu cầu nói, liên lạc người thân dễ hơn).
- Chuẩn bị bản demo ổn định, không có bug hiển thị trước đám đông.

**Vận hành:**
- Chuẩn bị + trình bày tại Demo Day (Hà Nội, dự kiến tháng 1/2027): dùng chính dữ liệu/video từ hộ pilot thật làm bằng chứng, không phải demo dàn dựng.

**Cột mốc:** trình bày xong Demo Day, có phản hồi từ ban giám khảo/đối tác đưa vào backlog tháng 5.

## Tháng 5 (2/2027) — Ổn định & chuẩn bị nhân rộng

**Kỹ thuật:**
- Dọn nợ kỹ thuật/bug tồn đọng từ pilot mở rộng.
- Viết hướng dẫn cài đặt thân thiện (không chỉ cho dev) — để hộ tiếp theo có thể tự cài hoặc cài nhanh hơn nhiều so với 5 hộ đầu.
- Tổng hợp số liệu: tần suất dùng, tỷ lệ lệnh thành công, mức hài lòng theo thời gian.

**Vận hành:**
- Đánh giá có nên mở rộng thêm hộ pilot mới trong tháng 6 hay giữ nguyên 5 hộ để đào sâu.

## Tháng 6 (3/2027) — Tổng kết pilot

**Kỹ thuật:**
- Chốt trạng thái sản phẩm, ghi lại rõ trong `docs/pilot-notes.md` (đã đổi gì, vì sao, dựa trên phản hồi nào).

**Vận hành:**
- Phỏng vấn kết thúc từng hộ, xin testimonial/câu chuyện thật để dùng cho báo cáo RE:ACT và bước sau.
- Viết báo cáo tổng kết Living Lab gửi RE:ACT (kết quả, bài học, đề xuất giai đoạn tiếp theo).
- Chuẩn bị nội dung/đại diện cho chuyến học tập Hàn Quốc (dự kiến 4/2027, nằm sau mốc 6 tháng này).

## Đo lường xuyên suốt

- **Tỷ lệ tự lập:** % thao tác máy tính người dùng tự làm được bằng giọng nói, không cần người khác hỗ trợ — chỉ số quan trọng nhất, đo mỗi tháng.
- **Tần suất dùng:** số lần tương tác/ngày mỗi hộ, theo dõi rơi rụng.
- **Độ chính xác lệnh:** tỷ lệ EVA hiểu đúng lệnh giọng nói trong điều kiện thật tại nhà (khác phòng thử nghiệm).
- **Hài lòng định tính:** phỏng vấn tháng 1/3/6, so sánh trực tiếp.

## Việc cần làm ngay (tháng 1)

1. Bỏ hard-code "Sơn" trong `core/ai_brain.py` và các file đã liệt kê.
2. Bắt đầu accessibility UI pass (chữ to, tương phản, PIN thay token).
3. Liên hệ tổ chức địa phương để tuyển hộ pilot — việc này không phải code, cần bạn chủ động, tôi có thể soạn nội dung liên hệ nếu cần.

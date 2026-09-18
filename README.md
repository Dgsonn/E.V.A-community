# EVA

Trợ lý AI cá nhân chạy thường trực (24/7) trên một máy Windows đóng vai trò server tại nhà, giao tiếp bằng **tiếng Việt** qua giọng nói hoặc dashboard web. Không có cửa sổ desktop nào hiển thị — giao diện duy nhất là dashboard web, truy cập được từ điện thoại/máy khác trong cùng mạng LAN.

## Tầm nhìn

EVA hướng đến trở thành một **Jarvis toàn diện** cho Sơn — không dừng lại ở một chatbot ra lệnh-trả lời, mà là trung tâm điều phối mọi thiết bị và công việc quanh mình, phát triển theo ba trục song song:

- **Người bạn đồng hành chăm sóc sức khoẻ** — không chỉ nhắc giờ uống thuốc/ăn sáng cố định, mà ngày càng hiểu thói quen sinh hoạt (giấc ngủ, cường độ làm việc) để chủ động lên tiếng đúng lúc, giống một người thân quan tâm thật sự hơn là một cái hẹn giờ.
- **Trung tâm điều phối kiểu Jarvis** — mở rộng khỏi 1 laptop hiện tại để điều khiển được nhiều thiết bị/máy hơn trong nhà, tự động hoá các tác vụ lặp lại thay vì chỉ phản hồi từng lệnh rời rạc.
- **Trợ lý lập trình & công việc** — đào sâu các tool hỗ trợ code (git, log, PR/issue) đã có, tiến tới theo dõi tiến độ dự án và tự động hoá tác vụ dev thường ngày, giảm thời gian Sơn phải tự tra cứu thủ công.

Tóm gọn lại EVA càng ít cần Sơn phải hỏi trước — càng chủ động quan sát, suy luận và hành động đúng lúc — thì càng gần với tầm nhìn ban đầu.

## Tính năng

**Hội thoại & điều khiển giọng nói**
- Đánh thức bằng wake word ("dậy đi") hoặc vỗ/búng tay 2 lần liên tiếp
- Nhận diện giọng nói tiếng Việt bằng PhoWhisper, tự động lọc tiếng ồn (VAD)
- Có thể ngắt lời EVA giữa chừng bằng câu lệnh ("dừng lại")
- Nhận diện người nói (voice ID) và khuôn mặt (camera) để phân quyền "chủ nhân" — có thể bật/tắt cơ chế bảo mật này

**Điều khiển máy tính & tiện ích**
- Mở app/URL/thư mục, tìm kiếm Google/YouTube, xem thời tiết
- Khoá máy, tắt/khởi động lại máy (có huỷ lệnh), điều chỉnh âm lượng, chụp màn hình
- Xem dung lượng ổ đĩa, trạng thái hệ thống (CPU/RAM), trạng thái dịch vụ

**Trợ lý chủ động (không cần hỏi trước)**
- Theo dõi sức khoẻ/giấc ngủ dựa trên hành vi dùng máy, tự cảnh báo bất thường
- Nhắc uống thuốc/ăn sáng cố định mỗi ngày theo giờ cấu hình
- Đặt nhắc việc tuỳ ý một lần (qua lệnh giọng nói/chat)
- Cảnh báo sớm khi nhiệt độ GPU vượt ngưỡng (máy chạy server 24/7)

**Dành cho lập trình viên**
- Kiểm tra git status/log, tail log file, xem PR/issue GitHub — tất cả giới hạn theo whitelist project/file trong config, tránh truy cập đường dẫn tuỳ ý

**Điều khiển từ xa**
- Đẩy lệnh/thông báo thoại sang một laptop khác đang kết nối (mở app/link, phát audio) thông qua cơ chế polling

**Dashboard web**
- Chat trực tiếp hoặc ghi âm giọng nói qua trình duyệt
- Xem đồng hồ đo CPU/RAM, danh sách người được uỷ quyền (có thể thu hồi quyền), ghi chú, lịch sử hội thoại
- Bảo vệ bằng token (`DASHBOARD_TOKEN`)

## Công nghệ sử dụng

**Backend — Python**
- `Flask` — server phục vụ dashboard tĩnh + API (`/api/message`, `/api/voice`, `/api/status`...)
- `Ollama` (model `qwen2.5:14b`, chạy offline/local) hoặc `google-genai` (Gemini, online) — bộ não hội thoại
- `transformers` + `torch` — STT bằng PhoWhisper (Whisper chuyên biệt tiếng Việt)
- `webrtcvad-wheels` — phát hiện giọng nói (VAD)
- `resemblyzer` — nhận diện giọng nói theo người (voice ID)
- `deepface` + `tensorflow` + `opencv-python` — nhận diện khuôn mặt
- `edge-tts` + `pygame` — chuyển văn bản thành giọng nói và phát audio
- `psutil` — theo dõi CPU/RAM, hoạt động hệ thống
- SQLite — lưu hội thoại, ghi chú, log sức khoẻ, sự kiện hệ thống
- `pyyaml` — cấu hình (`config/settings.yaml`)

**Frontend — [web/](web)**
- `Next.js 16` + `React 19` (TypeScript), build dưới dạng **static export** (`output: "export"`) — không chạy Node server, Flask serve trực tiếp file tĩnh
- `Tailwind CSS` — giao diện
- Web Audio API — ghi âm mic trình duyệt, tự đóng gói WAV 16kHz/mono để backend Python đọc bằng module `wave` chuẩn (không cần ffmpeg)

**Triển khai**
- Chạy nền không cửa sổ qua `start_eva_hidden.vbs` + `start_eva.bat` (tự khởi động lại nếu crash), hoặc đăng ký Windows Task Scheduler (xem `deploy/`)

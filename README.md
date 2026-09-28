# EVA — Trợ lý giọng nói tiếng Việt cho người cao tuổi

EVA là trợ lý AI chạy thường trực tại nhà, giao tiếp hoàn toàn bằng **giọng nói tiếng Việt tự nhiên**. EVA giúp người cao tuổi, cũng như người khó thao tác chuột và bàn phím, dùng máy tính, nhớ lịch uống thuốc và giữ liên lạc với người thân mà không cần biết thao tác kỹ thuật.

Mọi dữ liệu (giọng nói, hình ảnh, lịch sinh hoạt) được **xử lý và lưu ngay tại nhà**, không gửi lên máy chủ chung.

---

## Vấn đề

- Việt Nam đang già hoá dân số nhanh. Nhiều người cao tuổi sống một mình hoặc ở nhà cả ngày khi con cháu đi làm, đi học.
- Smartphone và máy tính có sẵn trong nhà, nhưng giao diện chạm, gõ và menu nhiều tầng là rào cản lớn với người lớn tuổi.
- Các trợ lý ảo phổ biến (Siri, Google Assistant, Alexa) hiểu tiếng Việt đời thường và giọng vùng miền còn hạn chế, và không được thiết kế cho nhu cầu chăm sóc hằng ngày.
- Con cháu ở xa muốn biết ông bà có ổn không, nhưng không muốn lắp một hệ thống giám sát phức tạp hay xâm phạm riêng tư.

## Giải pháp

EVA đóng vai một **người trợ giúp trong nhà**, với ba vai trò:

1. **Nhắc nhở và quan tâm hằng ngày.** EVA nhắc uống thuốc, ăn uống và lịch hẹn, đồng thời để ý thói quen sinh hoạt và lên tiếng khi có điều bất thường.
2. **Điều khiển máy tính bằng giọng nói.** Người dùng chỉ cần nói "mở YouTube", "xem thời tiết", "gọi cho con" thay vì dùng chuột và bàn phím.
3. **Cầu nối với người thân.** Con cháu xem được tình trạng chung qua một trang web đơn giản trên điện thoại.

---

## Tính năng đã có (MVP đang chạy)

### Giao tiếp bằng giọng nói
- Đánh thức bằng câu nói ("dậy đi") hoặc vỗ tay hai lần, không cần chạm vào máy.
- Nhận dạng tiếng Việt bằng **PhoWhisper**, mô hình chuyên biệt cho tiếng Việt, có lọc tiếng ồn (VAD).
- Người dùng có thể ngắt lời EVA bất cứ lúc nào bằng câu "dừng lại".
- EVA trả lời bằng giọng nói tự nhiên (Edge-TTS).

### Nhắc nhở và theo dõi thói quen sinh hoạt
- Nhắc uống thuốc và ăn sáng mỗi ngày theo giờ cài đặt.
- Đặt nhắc việc một lần bằng lời nói, ví dụ "nhắc tôi 3 giờ chiều đi khám".
- Theo dõi **thói quen sinh hoạt** (giờ thức, giờ ngủ, mức độ hoạt động) dựa trên việc sử dụng máy. EVA chủ động hỏi han khi thấy khác thường.

> EVA **không phải thiết bị y tế** và không đo chỉ số sức khoẻ. EVA chỉ nhận biết thay đổi thói quen để nhắc nhở và báo cho người thân.

### Điều khiển máy tính bằng giọng nói
- Mở ứng dụng, trang web, thư mục; tìm kiếm Google và YouTube; xem thời tiết.
- Chỉnh âm lượng, chụp màn hình, khoá máy, tắt hoặc khởi động lại máy (có thể huỷ lệnh).

### An toàn và phân quyền
- Nhận diện giọng nói (voice ID) và khuôn mặt (camera) để chỉ người dùng chính được ra các lệnh quan trọng. Cơ chế này có thể bật hoặc tắt.

### Trang web cho gia đình
- Trò chuyện với EVA bằng chữ hoặc ghi âm trực tiếp trên trình duyệt điện thoại.
- Xem lịch sử trò chuyện, ghi chú và tình trạng hệ thống.
- Quản lý danh sách người được uỷ quyền.

---

## Đang hoàn thiện

| Hạng mục | Hiện trạng | Mục tiêu |
|---|---|---|
| Cá nhân hoá | Cách xưng hô cài sẵn cho một người dùng | Cài tên, cách xưng hô ("bà", "ông", "bác") và tốc độ nói theo từng người |
| Giao diện dễ dùng | Giao diện tiêu chuẩn | Chữ lớn, tương phản cao, đăng nhập bằng mã PIN 4 số |
| Trang cho người thân | Dùng chung đăng nhập với người dùng chính | Trang riêng, chỉ xem, gửi link qua điện thoại |
| Điều khiển máy sâu hơn | Mở ứng dụng và lệnh hệ thống cơ bản | Đọc to nội dung màn hình, đọc chính tả, điều hướng trình duyệt bằng lời |

---

## Lộ trình tính năng đề xuất

### Ưu tiên cao: an toàn
- **Gọi trợ giúp khẩn cấp bằng giọng nói.** Khi người dùng nói "cứu tôi" hoặc "gọi con", EVA lập tức gửi cảnh báo kèm thời gian cho người thân qua Zalo, Telegram hoặc SMS.
- **Cảnh báo khi không có hoạt động.** Nếu không phát hiện hoạt động hoặc giọng nói trong khoảng thời gian bất thường (ví dụ quá 10 giờ sáng chưa thấy dậy), EVA hỏi han trước. Nếu không có phản hồi, EVA báo cho người thân.
- **Xác nhận đã uống thuốc.** Sau khi nhắc, EVA hỏi "Bác uống thuốc chưa ạ?". Nếu người dùng quên hoặc không trả lời, EVA nhắc lại và ghi nhận vào báo cáo cho gia đình.
- **Cảnh báo lừa đảo.** EVA đọc to và cảnh báo khi phát hiện các dấu hiệu lừa đảo phổ biến nhắm vào người cao tuổi, như giả danh công an, "trúng thưởng" hay yêu cầu chuyển tiền.

### Kết nối gia đình
- **Gọi video cho người thân bằng một câu nói**, ví dụ "gọi cho Lan", tự mở cuộc gọi Zalo hoặc Google Meet.
- **Tin nhắn thoại hai chiều.** Con cháu gửi lời nhắn, EVA đọc to cho ông bà nghe; ông bà nói trả lời, EVA gửi lại.
- **Báo cáo hằng ngày cho người thân.** Mỗi tối gửi một tin ngắn: đã uống thuốc, giờ sinh hoạt, có gì bất thường không.

### Đồng hành hằng ngày
- **Trò chuyện chào buổi sáng**: hỏi thăm giấc ngủ, đọc thời tiết, nhắc lịch trong ngày.
- **Đọc tin tức, truyện, phát nhạc xưa và radio** theo yêu cầu.
- **Hiểu giọng vùng miền và cách nói đời thường** (Bắc, Trung, Nam), nhờ tinh chỉnh thêm dữ liệu giọng người cao tuổi.

### Mở rộng tiếp cận
- **Chế độ cấu hình nhẹ** chạy trên máy phổ thông hoặc mini PC không cần card đồ hoạ rời, dùng mô hình AI nhỏ hơn hoặc chế độ online.
- **Loa thông minh chuyên dụng**: đóng gói EVA vào thiết bị nhỏ gọn chỉ gồm micro, loa và nút bấm khẩn cấp, không cần màn hình.

---

## Quyền riêng tư

- Mỗi hộ gia đình có **một máy chủ EVA riêng tại nhà**. EVA không phải dịch vụ dùng chung trên mạng.
- Mặc định chạy **offline** với mô hình AI cục bộ (Ollama). Chế độ online (Gemini) chỉ là tuỳ chọn.
- Giọng nói, hình ảnh khuôn mặt và lịch sinh hoạt được lưu trên máy tại nhà (SQLite), không gửi ra ngoài.
- Người thân chỉ thấy **tình trạng chung**, không nghe lại hội thoại và không xem camera.

---

## Công nghệ

**Backend (Python)**
- `Flask`: máy chủ web và API
- `Ollama` (`qwen2.5:14b`, offline) hoặc `google-genai` (Gemini, online): bộ não hội thoại
- `transformers` + `torch`: nhận dạng giọng nói PhoWhisper
- `webrtcvad-wheels`: phát hiện giọng nói
- `resemblyzer`: nhận diện người nói
- `deepface` + `opencv-python`: nhận diện khuôn mặt
- `edge-tts` + `pygame`: chuyển văn bản thành giọng nói
- `psutil`: theo dõi hoạt động hệ thống
- SQLite: lưu hội thoại, ghi chú, nhật ký sinh hoạt
- `pyyaml`: cấu hình (`config/settings.yaml`)

**Frontend ([web/](web))**
- `Next.js` + `React` (TypeScript), xuất dạng web tĩnh do Flask phục vụ trực tiếp
- `Tailwind CSS`
- Web Audio API: ghi âm từ trình duyệt, chuẩn hoá WAV 16kHz mono

**Triển khai**
- Chạy nền trên Windows, tự khởi động lại khi gặp lỗi (`start_eva_hidden.vbs`, `start_eva.bat`, hoặc Windows Task Scheduler, xem `deploy/`).
- Cấu hình hiện tại: máy Windows có GPU NVIDIA. Chế độ cấu hình nhẹ nằm trong lộ trình.

Sơ đồ kiến trúc: xem [Kiến Trúc EVA](https://claude.ai/artifact/5pMb9WjqiXF4KdT6UpPdfe).

---

## Tính năng kỹ thuật bổ sung

Các tính năng dưới đây phục vụ việc phát triển và vận hành máy chủ, **không nằm trong trải nghiệm của người dùng cuối**:

- Cảnh báo nhiệt độ GPU, xem CPU, RAM và dung lượng ổ đĩa
- Kiểm tra git status và log, xem log file, PR và issue GitHub (giới hạn theo whitelist trong cấu hình)
- Đẩy lệnh và thông báo thoại sang máy khác trong mạng

---

## Cài đặt

```bash
# Backend
pip install -r requirements.txt
ollama pull qwen2.5:14b
python main.py

# Frontend (build tĩnh)
cd web
npm install
npm run build
```

Sau khi chạy, mở dashboard tại `http://<địa-chỉ-máy>:5000` từ điện thoại hoặc máy tính trong cùng mạng.

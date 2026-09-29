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
- Đánh thức bằng câu nói ("EVA ơi", "dậy đi") hoặc vỗ tay hai lần, không cần chạm vào máy.
- Nhận dạng tiếng Việt bằng **PhoWhisper**, mô hình chuyên biệt cho tiếng Việt, có lọc tiếng ồn (VAD).
- Người dùng có thể ngắt lời EVA bất cứ lúc nào bằng câu "dừng lại".
- EVA trả lời bằng giọng nói tự nhiên (Edge-TTS).

### Nhắc nhở và theo dõi thói quen sinh hoạt
- Nhắc uống thuốc theo nhiều khung giờ mỗi ngày (sáng, tối...) theo lời bác sĩ dặn. Lần nhắc buổi sáng được mở đầu bằng lời chào và thời tiết trong ngày.
- **Xác nhận đã uống thuốc.** Sau khi nhắc, EVA chờ người dùng nói "uống rồi". Nếu chưa trả lời, EVA hỏi lại sau 15 phút; hỏi 3 lần vẫn không xác nhận thì ghi nhận "bỏ lỡ" và nhắn SMS cho người thân.
- Đặt nhắc việc một lần bằng lời nói, ví dụ "nhắc tôi 3 giờ chiều đi khám".
- Theo dõi **thói quen sinh hoạt** (giờ thức, giờ ngủ, mức độ hoạt động) dựa trên việc sử dụng máy. EVA chủ động hỏi han khi thấy khác thường.

> EVA **không phải thiết bị y tế** và không đo chỉ số sức khoẻ. EVA chỉ nhận biết thay đổi thói quen để nhắc nhở và báo cho người thân.

### Điều khiển máy tính bằng giọng nói
- Mở ứng dụng, trang web, thư mục; tìm kiếm Google và YouTube; xem thời tiết.
- **Gọi video cho người thân bằng một câu nói** ("gọi cho Lan", "gọi con gái"): EVA mở phòng gọi đã cài sẵn (Google Meet/Zalo) và nhắn tin để người thân vào nghe.
- Chỉnh âm lượng, chụp màn hình, khoá máy, tắt hoặc khởi động lại máy (có thể huỷ lệnh).

### Trợ năng cho người khiếm thị
- Đọc to nội dung trên màn hình, gõ hộ văn bản theo lời đọc, điều hướng trình duyệt bằng lời nói.

### An toàn
- **Gọi trợ giúp khẩn cấp bằng giọng nói.** Nói "cứu tôi", "gọi con"... là EVA nhận ra ngay, kể cả khi chưa nói "dậy đi", trấn an tại chỗ và nhắn SMS kèm thời gian cho người thân. EVA cũng tự gọi trợ giúp khi người dùng kể bị ngã, khó thở, đau ngực.
- **Cảnh báo khi không thấy hoạt động.** Quá 10 giờ sáng chưa thấy dậy, hoặc ban ngày im lặng quá 4 tiếng (không ai nói chuyện, không ai chạm máy), EVA hỏi han. Không ai trả lời trong 15 phút thì nhắn SMS cho người thân.
- Nhận diện giọng nói (voice ID) và khuôn mặt (camera) để chỉ người dùng chính được ra các lệnh quan trọng. Cơ chế này có thể bật hoặc tắt. Riêng lệnh gọi trợ giúp thì ai trong nhà cũng dùng được.

### Trang cho người thân
- Một link riêng, chỉ xem, mở trên điện thoại: EVA đang hoạt động hay đang chờ, lần hoạt động gần nhất, ghi chú gần đây.
- Không điều khiển được EVA, không nghe lại hội thoại, không xem camera. Có nút chữ lớn và tương phản cao.

---

## Đang hoàn thiện

| Hạng mục | Hiện trạng | Việc cần làm |
|---|---|---|
| Nhắn SMS cho người thân | Đã có code gửi qua eSMS.vn | Đăng ký brandname và mẫu tin với nhà mạng, gửi thử tin thật |
| Trợ năng (đọc màn hình, gõ hộ) | Đã có code | Thử trên máy thật với người dùng |
| Cảnh báo lừa đảo | Chưa làm | Chọn cách làm tôn trọng quyền riêng tư (EVA không nghe lén hội thoại) |

---

## Lộ trình tính năng đề xuất

### Ưu tiên cao: an toàn
- **Cảnh báo lừa đảo.** EVA đọc to và cảnh báo khi phát hiện các dấu hiệu lừa đảo phổ biến nhắm vào người cao tuổi, như giả danh công an, "trúng thưởng" hay yêu cầu chuyển tiền.

### Kết nối gia đình
- **Tin nhắn thoại hai chiều.** Con cháu gửi lời nhắn, EVA đọc to cho ông bà nghe; ông bà nói trả lời, EVA gửi lại.
- **Báo cáo hằng ngày cho người thân.** Mỗi tối gửi một tin ngắn: đã uống thuốc, giờ sinh hoạt, có gì bất thường không.
- **Nhắn qua Zalo** bên cạnh SMS, khi có Zalo Official Account.

### Đồng hành hằng ngày
- **Trò chuyện chào buổi sáng**: hỏi thăm giấc ngủ, đọc thời tiết, nhắc lịch trong ngày.
- **Đọc tin tức, truyện, phát nhạc xưa và radio** theo yêu cầu.
- **Hiểu giọng vùng miền và cách nói đời thường** (Bắc, Trung, Nam), nhờ tinh chỉnh thêm dữ liệu giọng người cao tuổi.

### Mở rộng tiếp cận
- **Chế độ cấu hình nhẹ** chạy trên máy phổ thông hoặc mini PC không cần card đồ hoạ rời, dùng mô hình AI nhỏ hơn hoặc chế độ online.
- **Loa thông minh chuyên dụng**: đóng gói EVA vào thiết bị nhỏ gọn chỉ gồm micro, loa và nút bấm khẩn cấp, không cần màn hình.

---

## Quyền riêng tư

- Mỗi hộ gia đình có **một máy EVA riêng tại nhà**. EVA không phải dịch vụ dùng chung trên mạng.
- **Luôn ở tại nhà:** giọng nói gốc (được chuyển thành chữ ngay trên máy), hình ảnh khuôn mặt, nhật ký sức khoẻ, lịch uống thuốc (SQLite).
- **Các tính năng an toàn không dùng AI** (gọi cứu, nhắc thuốc, cảnh báo không hoạt động). Khi mất mạng, EVA vẫn nhắc thuốc, vẫn nhận ra tiếng kêu cứu và trấn an tại chỗ (giọng đọc của các câu này được tạo sẵn lúc khởi động). Riêng việc nhắn SMS cho người thân thì cần có mạng.
- **Gia đình chọn chế độ AI khi cài đặt** (`ai.mode` trong `config/settings.yaml`):

| Chế độ | Gửi gì ra ngoài | Cần máy thế nào |
|---|---|---|
| **Online** (mặc định) — Google Gemini | Lời trò chuyện dạng chữ (10 lượt gần nhất), và dữ liệu mà câu hỏi cần (ví dụ hỏi "tuần này tôi ngủ thế nào" thì gửi kèm số giờ ngủ) | Máy phổ thông, không cần card đồ hoạ (dùng PhoWhisper bản nhỏ — đang thử nghiệm) |
| **Offline** — Ollama tại nhà | Không gửi lời trò chuyện đi đâu | Máy có GPU khoảng 12GB |

- Chế độ online cần gia đình **được báo và đồng ý** trước khi dùng. Nên dùng gói Gemini **trả phí**, vì theo điều khoản của Google, dữ liệu gói miễn phí có thể được dùng để cải thiện sản phẩm.
- Ở cả hai chế độ, câu trả lời dạng chữ được gửi lên Microsoft Edge-TTS để đọc thành giọng nói.
- Người thân chỉ thấy **tình trạng chung**, không nghe lại hội thoại và không xem camera.

---

## Công nghệ

**Backend (Python)**
- `Flask`: trang chỉ-xem cho người thân
- `google-genai` (Gemini, chế độ online mặc định) hoặc `Ollama` (`qwen2.5:14b`, chế độ offline): bộ não hội thoại
- `transformers` + `torch`: nhận dạng giọng nói PhoWhisper
- `webrtcvad-wheels`: phát hiện giọng nói
- `resemblyzer`: nhận diện người nói
- `deepface` + `opencv-python`: nhận diện khuôn mặt
- `edge-tts` + `pygame`: chuyển văn bản thành giọng nói
- `psutil`: theo dõi hoạt động hệ thống
- SQLite: lưu hội thoại, ghi chú, nhật ký sinh hoạt, lịch sử uống thuốc
- eSMS.vn: nhắn SMS cho người thân khi khẩn cấp
- `pyyaml`: cấu hình (`config/settings.yaml`)

**Frontend ([web/](web))**
- `Next.js` + `React` (TypeScript), xuất dạng web tĩnh do Flask phục vụ trực tiếp
- `Tailwind CSS`
- Web Audio API: ghi âm từ trình duyệt, chuẩn hoá WAV 16kHz mono

**Triển khai**
- Chạy nền trên Windows, tự khởi động lại khi gặp lỗi (`start_eva_hidden.vbs`, `start_eva.bat`, hoặc Windows Task Scheduler, xem `deploy/`).
- Máy có card đồ hoạ NVIDIA: dùng mặc định (PhoWhisper large chạy trên GPU).
- Máy phổ thông không có card đồ hoạ: đặt `ai.mode: online`, `voice.device: cpu`, `voice.model: small` trong `config/settings.yaml`. Cấu hình này **chưa được đo** tốc độ và độ chính xác với giọng người cao tuổi — cần thử trước khi thí điểm.

Sơ đồ kiến trúc: [docs/kien-truc-eva.png](docs/kien-truc-eva.png).

---

## Tính năng kỹ thuật bổ sung

Các tính năng dưới đây phục vụ việc phát triển và vận hành máy chủ, **không nằm trong trải nghiệm của người dùng cuối**:

- Cảnh báo nhiệt độ GPU, xem CPU, RAM và dung lượng ổ đĩa
- Kiểm tra git status và log, xem log file, PR và issue GitHub (giới hạn theo whitelist trong cấu hình)

---

## Cài đặt

```bash
# Backend
pip install -r requirements.txt
ollama pull qwen2.5:14b   # chỉ cần khi dùng ai.mode: offline
python main.py

# Frontend (build tĩnh)
cd web
npm install
npm run build
```

Khi chạy, EVA in ra link trang người thân (`http://<địa-chỉ-máy>:5000/family?token=...`). Gửi link này cho con cháu để mở trên điện thoại trong cùng mạng.

Để nhắn SMS cho người thân: điền `ESMS_API_KEY`, `ESMS_SECRET_KEY` vào `.env` và số điện thoại vào `caregiver.phones` trong `config/settings.yaml`.

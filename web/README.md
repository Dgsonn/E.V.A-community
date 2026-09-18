# Giao diện web EVA

Dashboard của EVA, viết bằng Next.js. Đây **không** phải app chạy server Node.js —
`next.config.ts` bật `output: "export"` nên `npm run build` chỉ sinh ra file tĩnh
(HTML/CSS/JS) trong `web/out/`, và chính `core/web_interface.py` (Flask) là bên
serve những file đó. Không có server Node nào chạy khi EVA hoạt động thật.

## Sau khi sửa giao diện

```bash
cd web
npm run build
```

rồi chạy lại `main.py` (hoặc chỉ cần load lại trang nếu Flask đang chạy sẵn — file
tĩnh được đọc lại từ đĩa mỗi request, không cần restart Flask). Nếu quên build,
`core/web_interface.py` sẽ in cảnh báo lúc khởi động vì không thấy thư mục `out/`.

## Phát triển có hot-reload

`npm run dev` chạy Next.js ở `localhost:3000`, gọi thẳng sang API thật của Flask
(mặc định cùng origin `""`. Đặt biến môi trường `NEXT_PUBLIC_API_BASE` trỏ sang
`http://<IP-máy-chạy-EVA>:5000` khi cần, xem `lib/api.ts`) — nhưng Flask hiện chưa
bật CORS nên cách này chỉ dùng tạm để xem giao diện đổi theo thời gian thực; trước
khi đưa vào dùng thật vẫn phải `npm run build` như trên.

## Cấu trúc

- `app/page.tsx` — trang dashboard duy nhất, ghép các component + polling API
- `components/` — TopBar, ChatPanel (chat + ghi âm giọng nói), CoreEmblem, SidePanel
  (gauge CPU/RAM, thông tin hệ thống, người được uỷ quyền, lệnh nhanh, ghi chú)
- `lib/api.ts` — các hàm gọi API Flask (`/api/status`, `/api/history`, `/api/message`,
  `/api/voice`, `/api/revoke_voice`, `/api/shutdown`)
- `lib/useVoiceRecorder.ts` — ghi âm mic trình duyệt rồi tự đóng gói WAV 16kHz/mono
  (để server đọc bằng module `wave` có sẵn của Python, không cần ffmpeg/pydub)

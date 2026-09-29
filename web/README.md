# Giao diện web EVA — trang người thân

Trang chỉ-xem `/family` cho con cháu, viết bằng Next.js. EVA cho người cao tuổi điều khiển
hoàn toàn bằng giọng nói tại chỗ — **không có** dashboard điều khiển từ xa.

Đây **không** phải app chạy server Node.js — `next.config.ts` bật `output: "export"` nên
`npm run build` chỉ sinh ra file tĩnh (HTML/CSS/JS) trong `web/out/`, và chính
`core/web_interface.py` (Flask) là bên serve những file đó.

## Sau khi sửa giao diện

```bash
cd web
npm run build
```

rồi load lại trang (file tĩnh được đọc lại từ đĩa mỗi request, không cần restart Flask).
Nếu quên build, `core/web_interface.py` sẽ in cảnh báo lúc khởi động vì không thấy `out/`.

## Cấu trúc

- `app/family/page.tsx` — trang người thân, xác thực bằng `?token=` (FAMILY_TOKEN) trong link
- `components/AccessibilityMenu.tsx` — nút chữ lớn/nhỏ và tương phản cao (lưu theo trình duyệt)
- `lib/api.ts` — gọi `/api/family_status`

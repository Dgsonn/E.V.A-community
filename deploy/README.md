# Biến máy này thành server chạy EVA 24/7

3 việc cần làm, làm 1 lần:

## 1. Tắt sleep khi cắm sạc

EVA phải chạy liên tục — máy đi ngủ (sleep/standby) là dừng hết (mic, dashboard, mọi thứ).
Chạy PowerShell (không cần Admin):

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
```

Chỉ tắt sleep khi cắm sạc (AC) — máy vẫn tự ngủ bình thường lúc chạy pin, tránh hết pin nếu
lỡ rút sạc. Vậy nên máy đóng vai "server" này cần **cắm sạc liên tục**.

## 2. Đăng ký tự khởi động cùng lúc đăng nhập Windows

```powershell
powershell -ExecutionPolicy Bypass -File deploy\register_task.ps1
```

Tạo Task Scheduler task "EVA-AutoStart", trigger "At log on" — dùng logon thay vì startup vì
EVA cần mic/camera thật, mà service chạy trước khi đăng nhập (Session 0) thường không đụng
được thiết bị âm thanh/hình ảnh. Nghĩa là máy vẫn phải đăng nhập Windows thì EVA mới tự chạy —
nếu muốn máy tự đăng nhập luôn sau khi khởi động lại (không cần gõ mật khẩu), bật Windows
Autologon (Sysinternals) — đánh đổi là ai cắm điện bật máy cũng vào thẳng được tài khoản này,
cân nhắc theo mức độ riêng tư nơi đặt máy.

Task tự khởi động lại nếu EVA crash (tối đa 999 lần, cách nhau 1 phút), không dừng nếu chuyển
sang chạy pin.

Gỡ task này: `powershell -ExecutionPolicy Bypass -File deploy\unregister_task.ps1`

## 3. Kiểm tra log

EVA chạy qua task này dùng `pythonw.exe` (không mở cửa sổ console), toàn bộ output ghi vào
`logs\eva.log` (đè/nối tiếp mỗi lần khởi động lại, không tự xoay vòng — dọn tay nếu file lớn
quá). Theo dõi trực tiếp:

```powershell
Get-Content logs\eva.log -Wait -Tail 50
```

## Chạy thử ngay không cần đăng nhập lại

```powershell
Start-ScheduledTask -TaskName EVA-AutoStart
Get-Content logs\eva.log -Wait -Tail 30
```

## IP LAN của máy này

Dashboard và `laptop_idle_agent.py` (chạy trên laptop hàng ngày) cần đúng IP LAN của máy
server để kết nối tới `http://<IP-máy-server>:5000`. Lấy IP:

```powershell
ipconfig | findstr /C:"IPv4"
```

IP này có thể đổi mỗi lần router cấp lại DHCP — nếu thấy laptop_idle_agent.py mất kết nối sau
1 thời gian, kiểm tra lại IP trước. Muốn ổn định lâu dài, đặt DHCP reservation cho máy này
trên router (theo địa chỉ MAC) để IP không đổi.

# Gỡ task tự khởi động EVA (không xoá code/log, chỉ xoá lịch chạy tự động).
#   powershell -ExecutionPolicy Bypass -File deploy\unregister_task.ps1
Unregister-ScheduledTask -TaskName "EVA-AutoStart" -Confirm:$false
Write-Host "Đã gỡ task 'EVA-AutoStart'."

# Đăng ký EVA tự khởi động cùng lúc đăng nhập Windows, chạy nền vô thời hạn.
# Chạy 1 lần (mở PowerShell thường, không cần Admin — Register-ScheduledTask cho user hiện tại
# không đòi quyền cao):
#   powershell -ExecutionPolicy Bypass -File deploy\register_task.ps1
#
# Dùng "At log on" (không phải "At startup") vì EVA cần mic/camera thật — service chạy ở
# Session 0 (trước khi ai đăng nhập) thường không truy cập được thiết bị âm thanh/hình ảnh do
# Windows Session 0 Isolation. Máy vẫn phải tự đăng nhập (hoặc bật đăng nhập tự động) để
# trigger này chạy sau khi khởi động lại.

$ErrorActionPreference = "Stop"
$taskName = "EVA-AutoStart"
$repoRoot = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $PSScriptRoot "start_eva.bat"

$action = New-ScheduledTaskAction -Execute $scriptPath -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "Tự chạy EVA (python main.py) mỗi khi Sơn đăng nhập Windows." | Out-Null

Write-Host "Đã đăng ký task '$taskName'. Kiểm tra bằng: Get-ScheduledTask -TaskName $taskName"
Write-Host "Chạy thử ngay (không cần đợi đăng nhập lại): Start-ScheduledTask -TaskName $taskName"
Write-Host "Log của EVA nằm ở: $repoRoot\logs\eva.log"

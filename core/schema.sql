-- Schema cho G.A.R.V.I.S Database

-- Bảng lịch sử hội thoại
CREATE TABLE IF NOT EXISTS conversation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    model_used TEXT
);

-- Bảng nhật ký gesture
CREATE TABLE IF NOT EXISTS gesture_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gesture_type TEXT NOT NULL,
    response TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Bảng sự kiện chung
CREATE TABLE IF NOT EXISTS app_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    description TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Bảng ghi chú do AI lưu hộ chủ nhân
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Bảng nhật ký sức khoẻ do chủ nhân tự báo qua giọng nói (giấc ngủ, cân nặng, triệu chứng...)
CREATE TABLE IF NOT EXISTS health_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Bảng nhắc nhở tuỳ ý do Sơn tự đặt qua tool set_reminder (core/tools.py) — khác
-- DailyReminder (cố định, lặp lại hàng ngày), đây là nhắc ĐÚNG 1 LẦN vào đúng thời điểm hẹn.
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT NOT NULL,
    remind_at DATETIME NOT NULL,
    fired INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

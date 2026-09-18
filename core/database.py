import sqlite3
import os
import threading
from datetime import datetime

_instance = None

DB_PATH = os.path.join("assets", "eva.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_db():
    global _instance
    if _instance is None:
        _instance = DatabaseManager()
    return _instance


class DatabaseManager:
    def __init__(self):
        """Khởi tạo kết nối SQLite local (offline, không cần internet)"""
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        # Nhiều thread (gesture, AI worker, Flask, main) dùng chung 1 connection.
        # sqlite3 không tự đồng bộ hoá việc dùng chung cursor giữa các thread —
        # gọi execute() đồng thời từ nhiều thread có thể segfault. Lock để tuần tự hoá.
        self._lock = threading.Lock()

        self.create_tables()
        print(f"[DB] Đã kết nối SQLite local ({DB_PATH})")

    def create_tables(self):
        """Tạo các bảng cần thiết từ schema.sql"""
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            with self._lock:
                self.conn.executescript(f.read())
                self.conn.commit()

    def save_conversation(self, role, content, model_used=None):
        """Lưu tin nhắn hội thoại"""
        try:
            with self._lock:
                self.conn.execute("""
                    INSERT INTO conversation_history (role, content, timestamp, model_used)
                    VALUES (?, ?, ?, ?)
                """, (role, content, datetime.now(), model_used))
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"[DB] Lỗi khi lưu hội thoại: {e}")

    def get_conversation_history(self, limit=50):
        """Lấy lịch sử hội thoại gần đây"""
        try:
            with self._lock:
                cursor = self.conn.execute("""
                    SELECT role, content, timestamp FROM conversation_history
                    ORDER BY id DESC LIMIT ?
                """, (limit,))
                results = cursor.fetchall()
            return list(reversed(results))
        except Exception as e:
            print(f"[DB Error] Lỗi lấy conversation: {e}")
            return []

    def log_gesture(self, gesture_type, response):
        """Lưu nhật ký gesture"""
        try:
            with self._lock:
                self.conn.execute("""
                    INSERT INTO gesture_logs (gesture_type, response, timestamp)
                    VALUES (?, ?, ?)
                """, (gesture_type, response, datetime.now()))
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"[DB] Lỗi khi lưu gesture log: {e}")

    def log_event(self, event_type, description):
        """Lưu sự kiện chung"""
        try:
            with self._lock:
                self.conn.execute("""
                    INSERT INTO app_logs (event_type, description, timestamp)
                    VALUES (?, ?, ?)
                """, (event_type, description, datetime.now()))
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"[DB Error] Lỗi lưu event: {e}")

    def get_last_login(self):
        """Lấy thời điểm khởi động gần nhất (APP_START), không tính lần hiện tại"""
        try:
            with self._lock:
                cursor = self.conn.execute("""
                    SELECT timestamp FROM app_logs
                    WHERE event_type = 'APP_START'
                    ORDER BY id DESC LIMIT 1 OFFSET 1
                """)
                row = cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            print(f"[DB Error] Lỗi lấy last login: {e}")
            return None

    def save_note(self, content):
        """Lưu một ghi chú"""
        try:
            with self._lock:
                self.conn.execute("""
                    INSERT INTO notes (content, timestamp) VALUES (?, ?)
                """, (content, datetime.now()))
                self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"[DB] Lỗi khi lưu ghi chú: {e}")
            return False

    def get_notes(self, limit=20):
        """Lấy các ghi chú gần đây"""
        try:
            with self._lock:
                cursor = self.conn.execute("""
                    SELECT content, timestamp FROM notes
                    ORDER BY id DESC LIMIT ?
                """, (limit,))
                return cursor.fetchall()
        except Exception as e:
            print(f"[DB Error] Lỗi lấy notes: {e}")
            return []

    def save_health_log(self, category, content):
        """Lưu 1 mục sức khoẻ (giấc ngủ, cân nặng, triệu chứng...) chủ nhân tự báo"""
        try:
            with self._lock:
                self.conn.execute("""
                    INSERT INTO health_logs (category, content, timestamp) VALUES (?, ?, ?)
                """, (category, content, datetime.now()))
                self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"[DB] Lỗi khi lưu health log: {e}")
            return False

    def get_health_logs(self, category=None, limit=20):
        """Lấy lịch sử sức khoẻ gần đây, lọc theo category nếu có"""
        try:
            with self._lock:
                if category:
                    cursor = self.conn.execute("""
                        SELECT category, content, timestamp FROM health_logs
                        WHERE category = ? ORDER BY id DESC LIMIT ?
                    """, (category, limit))
                else:
                    cursor = self.conn.execute("""
                        SELECT category, content, timestamp FROM health_logs
                        ORDER BY id DESC LIMIT ?
                    """, (limit,))
                return cursor.fetchall()
        except Exception as e:
            print(f"[DB Error] Lỗi lấy health logs: {e}")
            return []

    def save_reminder(self, message, remind_at):
        """Lưu 1 nhắc nhở tuỳ ý — remind_at là datetime object (thời điểm cần báo)."""
        try:
            with self._lock:
                cursor = self.conn.execute("""
                    INSERT INTO reminders (message, remind_at) VALUES (?, ?)
                """, (message, remind_at))
                self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            self.conn.rollback()
            print(f"[DB] Lỗi khi lưu nhắc nhở: {e}")
            return None

    def get_pending_reminders(self):
        """Lấy các nhắc nhở CHƯA báo (fired=0), sắp theo thời điểm gần nhất trước."""
        try:
            with self._lock:
                cursor = self.conn.execute("""
                    SELECT id, message, remind_at FROM reminders
                    WHERE fired = 0 ORDER BY remind_at ASC
                """)
                return cursor.fetchall()
        except Exception as e:
            print(f"[DB Error] Lỗi lấy reminders: {e}")
            return []

    def mark_reminder_fired(self, reminder_id):
        """Đánh dấu 1 nhắc nhở đã báo — gọi từ core/reminder_scheduler.py sau khi đã nói ra."""
        try:
            with self._lock:
                self.conn.execute("UPDATE reminders SET fired = 1 WHERE id = ?", (reminder_id,))
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"[DB] Lỗi khi đánh dấu nhắc nhở đã báo: {e}")

    def cancel_reminder(self, reminder_id):
        """Huỷ 1 nhắc nhở đang chờ (xoá hẳn). Trả về True nếu tìm thấy và xoá được."""
        try:
            with self._lock:
                cursor = self.conn.execute(
                    "DELETE FROM reminders WHERE id = ? AND fired = 0", (reminder_id,)
                )
                self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            self.conn.rollback()
            print(f"[DB] Lỗi khi huỷ nhắc nhở: {e}")
            return False

    def close(self):
        """Đóng kết nối database"""
        with self._lock:
            if self.conn:
                self.conn.close()
        print("[DB] Database connection closed")

#!/usr/bin/env python3
"""Script để xem dữ liệu lưu trong SQLite local (assets/eva.db)"""

import sqlite3
import os
from tabulate import tabulate

DB_PATH = os.path.join("assets", "eva.db")


def get_conn():
    if not os.path.exists(DB_PATH):
        raise ValueError(f"Không tìm thấy database tại {DB_PATH}")
    return sqlite3.connect(DB_PATH)


def view_conversations(limit=20):
    """Xem lịch sử hội thoại"""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT role, content, timestamp FROM conversation_history
        ORDER BY id DESC LIMIT ?
    """, (limit,))

    results = cursor.fetchall()
    conn.close()

    if not results:
        print("Không có dữ liệu hội thoại")
        return

    print("\n" + "="*80)
    print("LỊCH SỬ HỘI THOẠI (Latest {})".format(len(results)))
    print("="*80)

    results = list(reversed(results))

    for i, (role, content, timestamp) in enumerate(results, 1):
        role_display = "SƠN" if role == "user" else "EVA"
        print(f"\n[{i}] {role_display} ({timestamp})")
        print(f"    {content}")


def view_gestures(limit=20):
    """Xem nhật ký gesture"""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT gesture_type, response, timestamp FROM gesture_logs
        ORDER BY id DESC LIMIT ?
    """, (limit,))

    results = cursor.fetchall()
    conn.close()

    if not results:
        print("Không có dữ liệu gesture")
        return

    print("\n" + "="*80)
    print("NHẬT KÝ GESTURE (Latest {})".format(len(results)))
    print("="*80)

    results = list(reversed(results))

    table_data = [[g, r, t] for g, r, t in results]
    print(tabulate(table_data, headers=["Gesture", "Response", "Time"], tablefmt="grid"))


def view_events(limit=50):
    """Xem nhật ký sự kiện"""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT event_type, description, timestamp FROM app_logs
        ORDER BY id DESC LIMIT ?
    """, (limit,))

    results = cursor.fetchall()
    conn.close()

    if not results:
        print("Không có dữ liệu sự kiện")
        return

    print("\n" + "="*80)
    print("NHẬT KÝ SỰ KIỆN (Latest {})".format(len(results)))
    print("="*80)

    results = list(reversed(results))

    table_data = [[e, d, t] for e, d, t in results]
    print(tabulate(table_data, headers=["Event", "Description", "Time"], tablefmt="grid"))


def get_stats():
    """Xem thống kê"""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM conversation_history")
    conv_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM conversation_history WHERE role='user'")
    user_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM conversation_history WHERE role='assistant'")
    ai_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM gesture_logs")
    gesture_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM app_logs")
    event_count = cursor.fetchone()[0]

    conn.close()

    print("\n" + "="*80)
    print("THỐNG KÊ DATABASE")
    print("="*80)
    print(f"Total Conversations: {conv_count}")
    print(f"   - User Messages: {user_count}")
    print(f"   - AI Responses: {ai_count}")
    print(f"Total Gestures: {gesture_count}")
    print(f"Total Events: {event_count}")
    print("="*80)


def main():
    print("\nEVA DATABASE VIEWER (SQLite local)\n")

    while True:
        print("\nMENU:")
        print("  1. Xem lịch sử hội thoại")
        print("  2. Xem nhật ký gesture")
        print("  3. Xem nhật ký sự kiện")
        print("  4. Xem thống kê")
        print("  5. Thoát")

        choice = input("\nChọn (1-5): ").strip()

        if choice == "1":
            try:
                limit = input("Số lượng (mặc định 20): ").strip()
                view_conversations(int(limit) if limit else 20)
            except Exception as e:
                print(f"Lỗi: {e}")

        elif choice == "2":
            try:
                limit = input("Số lượng (mặc định 20): ").strip()
                view_gestures(int(limit) if limit else 20)
            except Exception as e:
                print(f"Lỗi: {e}")

        elif choice == "3":
            try:
                limit = input("Số lượng (mặc định 50): ").strip()
                view_events(int(limit) if limit else 50)
            except Exception as e:
                print(f"Lỗi: {e}")

        elif choice == "4":
            get_stats()

        elif choice == "5":
            print("\nTạm biệt!")
            break

        else:
            print("Lựa chọn không hợp lệ")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTạm biệt!")

#!/usr/bin/env python3
"""Đăng ký khuôn mặt chủ nhân cho EVA (face recognition)."""

import cv2
from core.face_engine import FaceEngine


def main():
    print("=" * 60)
    print("  ĐĂNG KÝ KHUÔN MẶT CHỦ NHÂN CHO EVA")
    print("=" * 60)
    print("Nhìn thẳng vào camera, đủ sáng, chỉ 1 khuôn mặt trong khung hình.")
    print("Nhấn SPACE để chụp, ESC để hủy.\n")

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # DSHOW mở nhanh (~1s) thay vì MSMF mặc định (~10s+)
    engine = FaceEngine()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Không đọc được camera.")
            break

        display = cv2.flip(frame, 1)
        cv2.putText(
            display, "SPACE: chup | ESC: huy", (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2,
        )
        cv2.imshow("Dang ky khuon mat - EVA", display)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            print("Đã hủy.")
            break
        if key == 32:  # SPACE
            if engine.enroll(cv2.flip(frame, 1)):
                print("Đăng ký thành công! Garvis giờ nhận ra bạn.")
                break
            print("Không phát hiện khuôn mặt rõ ràng, thử lại.")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

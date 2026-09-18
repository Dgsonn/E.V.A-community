import os
import requests
from tqdm import tqdm

# 1. Cấu hình thư mục
model_dir = os.path.join("assets", "models")
os.makedirs(model_dir, exist_ok=True)

# 2. Link tải trực tiếp từ server Hugging Face công khai
# Bản base (~145MB) - Phù hợp để test nhanh
url = "https://huggingface.co/rhasspy/whisper-static/resolve/main/base.pt"
dest_path = os.path.join(model_dir, "base.pt")

print("--- ĐANG TẢI WHISPER MODEL (DỰ PHÒNG CHUẨN) ---")
print(f"Đang tải từ: {url}")

try:
    # Tải file bằng requests để tránh lỗi của thư viện hf_hub
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status() # Kiểm tra lỗi kết nối
    
    total_size = int(response.headers.get('content-length', 0))
    
    with open(dest_path, 'wb') as f, tqdm(
        desc="Đang tải",
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for data in response.iter_content(chunk_size=1024):
            size = f.write(data)
            bar.update(size)

    print(f"\n✅ THÀNH CÔNG! File đã nằm tại: {dest_path}")
    print("Bây giờ bạn có thể chạy 'python main.py'")

except Exception as e:
    print(f"\n❌ Vẫn lỗi: {e}")
    print("\nLỜI KHUYÊN CUỐI CÙNG:")
    print("Mạng của bạn đang chặn file nặng từ server AI.")
    print("Hãy bật 4G từ điện thoại, phát Wifi cho máy tính và chạy lại file này.")
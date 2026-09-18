import os

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import json
import numpy as np

OWNER_FACE_PATH = os.path.join("assets", "owner_face.json")
MODEL_NAME = "Facenet"
MATCH_THRESHOLD = 10.0  # khoảng cách Euclidean cho Facenet — càng nhỏ càng giống

_tf_gpu_hidden = False


def _hide_gpu_from_tensorflow():
    """Ép riêng TensorFlow (DeepFace dùng để nhận diện khuôn mặt) chạy CPU, để dành GPU cho
    Ollama + PhoWhisper (STT) — KHÔNG dùng biến môi trường CUDA_VISIBLE_DEVICES như trước
    (đã set process-wide, khiến torch.cuda.is_available() bên voice_engine.py cũng bị ẩn mất
    GPU luôn, ép cả STT chạy CPU âm thầm không log gì). tf.config.set_visible_devices chỉ
    ảnh hưởng riêng TensorFlow, PyTorch vẫn thấy GPU bình thường."""
    global _tf_gpu_hidden
    if _tf_gpu_hidden:
        return
    try:
        import tensorflow as tf
        tf.config.set_visible_devices([], "GPU")
    except Exception:
        pass
    _tf_gpu_hidden = True


class FaceEngine:
    def __init__(self):
        self.owner_embedding = self._load_owner()

    def _load_owner(self):
        if os.path.exists(OWNER_FACE_PATH):
            with open(OWNER_FACE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return np.array(data["embedding"])
        return None

    @property
    def has_owner(self):
        return self.owner_embedding is not None

    def _get_embedding(self, frame):
        _hide_gpu_from_tensorflow()
        from deepface import DeepFace

        try:
            result = DeepFace.represent(
                img_path=frame, model_name=MODEL_NAME, enforce_detection=True
            )
            return np.array(result[0]["embedding"])
        except Exception:
            return None

    def enroll(self, frame):
        """Đăng ký khuôn mặt chủ nhân từ 1 khung hình. Trả về True nếu thành công."""
        embedding = self._get_embedding(frame)
        if embedding is None:
            return False

        os.makedirs(os.path.dirname(OWNER_FACE_PATH), exist_ok=True)
        with open(OWNER_FACE_PATH, "w", encoding="utf-8") as f:
            json.dump({"embedding": embedding.tolist()}, f)

        self.owner_embedding = embedding
        return True

    def is_owner(self, frame):
        """
        Kiểm tra khung hình có phải chủ nhân không.
        Trả về True / False / None (None = chưa đăng ký hoặc không thấy khuôn mặt).
        """
        if not self.has_owner:
            return None

        embedding = self._get_embedding(frame)
        if embedding is None:
            return None

        distance = np.linalg.norm(embedding - self.owner_embedding)
        return bool(distance < MATCH_THRESHOLD)

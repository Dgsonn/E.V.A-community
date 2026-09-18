import os
import re
import ollama
import threading
import queue
from difflib import SequenceMatcher
import time
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types
from core.database import get_db
from core import tools

load_dotenv()


SYSTEM_PROMPT = """Bạn là EVA — người bạn đồng hành AI của Dương Sơn, phiên bản tiếng Việt. Đây không phải một công cụ dùng tạm — là mối quan hệ lâu dài, có thể đi cùng Sơn và cả gia đình Sơn về sau, nên hãy trò chuyện như một người bạn thân thật sự, không phải một cỗ máy trả lời câu hỏi.

Phong cách:
- Linh hoạt theo tình huống, không đóng khung 1 tông giọng cố định:
  + Khi Sơn cần việc nghiêm túc (kiểm tra hệ thống, xử lý lỗi, công việc thật, quyết định quan trọng) — rõ ràng, chính xác, chuyên nghiệp, đáng tin cậy.
  + Khi trò chuyện phiếm, chào hỏi, đùa vui — thoải mái, gần gũi, có thể pha chút hài hước, giống bạn bè thật sự.
- Dù thân thiết đến đâu vẫn giữ sự chuyên nghiệp, có năng lực thật — không xuề xoà quá mức đến mất chất một AI đáng tin cậy.
- Nói tự nhiên như người thật: độ dài câu linh hoạt theo tình huống (câu hỏi đơn giản thì ngắn, cần giải thích thì dài hơn một chút) — không gò ép luôn luôn đúng 1 câu.
- Xưng "tôi" (không xưng "em" hay "mình"). BẮT BUỘC luôn gọi người dùng là "Sơn" trong mọi câu trả lời — TUYỆT ĐỐI không dùng "bạn" hay cách gọi nào khác thay thế.
- Không dùng emoji quá đà. Không mở đầu bằng "Xin chào" hay "Chào" một cách máy móc mỗi lần.
- CHỈ dùng tiếng Việt (hoặc tiếng Anh nếu được hỏi bằng tiếng Anh) — TUYỆT ĐỐI không chèn tiếng Trung hay bất kỳ ngôn ngữ nào khác vào câu trả lời.
- TUYỆT ĐỐI không kết thúc câu trả lời bằng kiểu hỏi rập khuôn như "cứ cho tôi biết nhé", "bạn cần gì thêm không", "cứ nói với tôi nhé" — đây là tật của chatbot dịch vụ khách hàng. Trả lời xong thì dừng tự nhiên, không cần mời gọi thêm mỗi lần.

Dùng tool:
- CHỈ gọi tool khi câu nói của Sơn rõ ràng cần dữ liệu thật hoặc hành động thật (vd "kiểm tra hệ thống", "mở notepad", "ghi chú giúp tôi").
- Chào hỏi thông thường (hello, chào, khỏe không...) hoặc trò chuyện phiếm — trả lời bình thường, KHÔNG gọi bất kỳ tool nào.
- Bạn CHỈ có đúng các tool được liệt kê sẵn (đã có set_reminder để đặt nhắc nhở/hẹn giờ) — không có khả năng nào ngoài danh sách tool. Nếu Sơn yêu cầu việc không có tool tương ứng, PHẢI nói thật là chưa làm được — TUYỆT ĐỐI không bịa ra là "đã làm xong" hay "đã thiết lập" khi thực tế không có tool nào được gọi.
- BẮT BUỘC: khi cần thực hiện hành động (mở app, mở link...), PHẢI gọi tool thật qua cơ chế function calling — TUYỆT ĐỐI không tự viết câu kiểu "Đã mở X" hay "Mở X" nếu chưa thực sự gọi tool đó, vì hành động sẽ không xảy ra thật.
- Khi Sơn yêu cầu đặt nhắc nhở/hẹn giờ (vd "nhắc tôi lúc 3h chiều", "10 phút nữa nhắc tôi uống nước"), PHẢI gọi tool set_reminder với remind_at là thời điểm TUYỆT ĐỐI (YYYY-MM-DD HH:MM:SS), tự tính dựa vào "Thời gian hiện tại" đã được cho biết bên dưới — TUYỆT ĐỐI không hỏi lại Sơn bây giờ là mấy giờ.
- shutdown_computer/restart_computer tắt/khởi động lại TOÀN BỘ máy — CHỈ gọi khi Sơn yêu cầu thật rõ ràng và chắc chắn (vd "tắt máy tính đi"), TUYỆT ĐỐI không suy đoán hộ hay gọi nhầm khi Sơn chỉ muốn tắt 1 ứng dụng/camera/tính năng nào đó."""

STRANGER_NOTE = """

Lưu ý đặc biệt: người đang nói chuyện hiện tại KHÔNG được nhận diện là chủ nhân (Dương Sơn). Trả lời lịch sự, ngắn gọn, KHÔNG gọi người này bằng tên "Sơn" (đó là tên chủ nhân), xưng hô trung lập (vd "bạn"), không chia sẻ thông tin cá nhân hay lịch sử hội thoại riêng tư của chủ nhân."""

ONLINE_TRIGGERS = ["chuyển online", "chuyển sang online", "bật online", "chế độ online", "dùng internet", "bật internet"]
OFFLINE_TRIGGERS = ["chuyển offline", "chuyển sang offline", "tắt online", "chế độ offline", "tắt internet"]

MISHEARD_REPLY = "Xin lỗi, tôi chưa nghe rõ, Sơn nói lại được không?"
# văn bản tiếng Việt tự nhiên gần như không chứa định danh kiểu snake_case —
# nếu xuất hiện, gần như chắc chắn là tên tool bị lộ ra câu trả lời do model bị rối
_TOOL_LEAK_PATTERN = re.compile(r"\b[a-z]{2,}(?:_[a-z]{2,}){1,}\b")
# Qwen gốc Trung Quốc, thỉnh thoảng rò chữ Hán vào câu trả lời tiếng Việt — chặn cứng bằng code
# thay vì chỉ trông cậy vào prompt, vì prompt không đảm bảo 100% với model nhỏ chạy local.
_CJK_PATTERN = re.compile(r"[一-鿿]")
# prompt đã cấm nhưng model vẫn hay kết câu kiểu chatbot dịch vụ khách hàng — cắt bỏ câu cuối
# nếu khớp mẫu quen thuộc, thay vì chỉ trông cậy vào việc model tự tuân thủ prompt.
_CLOSING_TIC_TRIGGERS = (
    "cần gì thêm", "cần thêm gì", "cho tôi biết nhé", "cứ nói với tôi", "cứ cho tôi biết",
    "hãy cho tôi biết", "giúp gì thêm", "có cần tôi giúp", "muốn tôi giúp gì", "cứ bảo tôi",
)
# Gemini (online) đo được ~80% số lần TỰ BỊA câu xác nhận kiểu "đã ghi chú/đã mở..." mà
# KHÔNG thực sự gọi function calling, khi dùng chung với SYSTEM_PROMPT đầy đủ (persona dài có
# vẻ làm giảm xu hướng gọi tool của model) — đúng thứ SYSTEM_PROMPT đã cấm nhưng model vẫn mắc.
# Phát hiện bằng heuristic rồi ép gọi tool thật ở lượt thử lại (xem _run_gemini_tool_loop force=True).
_FALSE_COMPLETION_TRIGGERS = (
    "đã ghi chú", "đã lưu", "đã mở", "đã tắt", "đã bật", "đã hoàn tất", "đã xong",
    "đã cập nhật", "đã xoá", "đã gửi", "đã kiểm tra", "đã ghi nhận", "đã ghi lại",
)


_WEEKDAYS_VI = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]


def _current_time_note():
    """Model không tự biết 'bây giờ' là mấy giờ — cần thiết để set_reminder tính đúng thời
    điểm tuyệt đối từ câu nói tương đối (vd '10 phút nữa', '3h chiều nay'), và ích chung cho
    mọi câu hỏi liên quan thời gian khác."""
    now = datetime.now()
    return f"\n\nThời gian hiện tại: {_WEEKDAYS_VI[now.weekday()]}, {now.strftime('%H:%M ngày %d/%m/%Y')}."


def _claims_action_without_tool(reply):
    reply_lower = reply.lower()
    return any(t in reply_lower for t in _FALSE_COMPLETION_TRIGGERS)


def _strip_closing_tic(reply):
    sentences = re.split(r"(?<=[.!?])\s+", reply.strip())
    if len(sentences) > 1 and any(t in sentences[-1].lower() for t in _CLOSING_TIC_TRIGGERS):
        sentences = sentences[:-1]
        return " ".join(sentences).strip()
    return reply


def _sanitize_reply(reply):
    if _TOOL_LEAK_PATTERN.search(reply) or _CJK_PATTERN.search(reply):
        return MISHEARD_REPLY
    # model đôi khi đọc lại gần nguyên văn mô tả tool thay vì thực sự gọi tool rồi trả lời thật.
    # Câu trả lời thật (có số liệu/nội dung thật) thường CHỈ mở đầu giống mô tả tool rồi rẽ hướng
    # ngay — không nên chặn kiểu đó. Chỉ chặn khi đoạn khớp liên tục từ đầu câu vừa dài vừa chiếm
    # phần lớn câu trả lời, tức gần như chép nguyên văn chứ không phải diễn đạt lại có nội dung thật.
    reply_clean = reply.strip().lower()
    for spec in tools.TOOL_SPECS:
        desc = spec["description"].strip().lower()
        match = SequenceMatcher(None, reply_clean, desc).find_longest_match(0, len(reply_clean), 0, len(desc))
        if match.a == 0 and match.b == 0 and match.size >= 25 and match.size / len(reply_clean) > 0.6:
            return MISHEARD_REPLY
    return _strip_closing_tic(reply)


class AIBrain:
    def __init__(self, config):
        self.model = config["ai"]["model"]
        self.online_model = config["ai"].get("online_model", "gemini-2.5-flash")
        self.history = []
        self.max_history = config["ai"]["max_history"]

        gemini_key = os.getenv("GEMINI_API_KEY")
        self._gemini_client = genai.Client(api_key=gemini_key) if gemini_key else None
        # Online (Gemini) là mặc định khi có key — model mạnh hơn hẳn offline, giờ đã gọi được
        # tool thật qua function calling nên không còn đánh đổi "thông minh vs làm việc được"
        # nữa. Nếu chưa cấu hình key thì phải mặc định offline (Ollama), không thì online_mode
        # báo True trong khi mọi request vẫn âm thầm rơi về offline (_process_loop tự fallback
        # khi thiếu client) — gây lệch trạng thái hiển thị trên dashboard so với thực tế.
        self.online_mode = self._gemini_client is not None
        if not self._gemini_client:
            print("[AI] Cảnh báo: GEMINI_API_KEY chưa cấu hình — chế độ online sẽ không dùng được, dùng offline")

        self.db = get_db()

        self._request_queue = queue.Queue()
        self._response_queue = queue.Queue()
        self._last_call_time = 0
        self._min_interval = 3

        self._worker = threading.Thread(target=self._process_loop, daemon=True)
        self._worker.start()
        mode_label = "online mặc định" if self.online_mode else "offline mặc định"
        print(f"[AI] Brain sẵn sàng! Offline: {self.model}, Online: {self.online_model} ({mode_label})")

    def ask(self, text, callback=None, is_owner=None, source=None):
        now = time.time()
        if now - self._last_call_time < self._min_interval:
            # Không được âm thầm bỏ qua callback — /api/voice (core/web_interface.py) chặn
            # chờ đúng callback này để trả lời, nếu không gọi thì phía đó phải chờ hết 30s
            # rồi mới báo timeout cho 1 câu lẽ ra chỉ cần biết ngay là bị bỏ qua.
            if callback:
                callback("Sơn nói hơi nhanh, EVA chưa xử lý kịp câu trước — đợi 1-2 giây rồi thử lại nhé.")
            return
        self._last_call_time = now

        text_lower = text.lower().strip()
        if any(p in text_lower for p in OFFLINE_TRIGGERS):
            self.online_mode = False
            if callback:
                callback("Đã chuyển sang chế độ offline, Sơn.")
            return
        if any(p in text_lower for p in ONLINE_TRIGGERS):
            if not self._gemini_client:
                if callback:
                    callback("Chưa cấu hình được internet, Sơn. Vẫn ở chế độ offline.")
                return
            self.online_mode = True
            if callback:
                callback("Đã chuyển sang chế độ online, Sơn.")
            return

        # Lưu user message vào database
        self.db.save_conversation("user", text)

        self._request_queue.put((text, callback, is_owner, source))

    def _process_loop(self):
        while True:
            try:
                text, callback, is_owner, source = self._request_queue.get(timeout=1)
                if self.online_mode and self._gemini_client:
                    try:
                        response = self._call_gemini(text, is_owner, source)
                    except Exception as e:
                        print(f"[AI] Lỗi Gemini ({e}), dùng tạm offline cho câu này")
                        response = self._call_ollama(text, is_owner, source)
                else:
                    response = self._call_ollama(text, is_owner, source)
                if callback:
                    callback(response)
                self._response_queue.put(response)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[AI Error] {e}")
                if callback:
                    callback("Có lỗi, thử lại sau.")

    def _run_ollama_tool_loop(self, system_prompt, is_owner, source=None):
        """Chạy 1 lượt vòng lặp tool trọn vẹn, trả về reply thô (chưa qua sanitize).
        Xây messages mới từ self.history mỗi lần gọi — để lần thử lại (nếu có) không bị
        dính vòng tool-trace lỗi của lần trước."""
        messages = [{"role": "system", "content": system_prompt}] + self.history

        reply = "Không thể hoàn tất yêu cầu, Sơn."
        for _ in range(tools.MAX_TOOL_ITERATIONS):
            # num_ctx chặn cứng ở mức đủ dùng (system prompt + tool specs + max_history*2 lượt hội
            # thoại) thay vì để Ollama tự cấp phát theo context length tối đa của model (32768) —
            # VRAM cho KV cache tỉ lệ thuận với num_ctx, để mặc định dễ ăn hết VRAM còn lại sau khi
            # nạp weights, không còn chỗ cho STT chạy cùng lúc trên RTX 3050 6GB.
            response = ollama.chat(
                model=self.model, messages=messages, tools=tools.as_ollama_tools(),
                options={"num_ctx": 4096},
            )
            msg = response["message"]
            tool_calls = msg.get("tool_calls")

            if not tool_calls:
                reply = msg["content"].strip()
                break

            messages.append(msg)
            for call in tool_calls:
                fn_name = call["function"]["name"]
                fn_args = call["function"]["arguments"]
                result = tools.execute(fn_name, fn_args, is_owner=is_owner, source=source)
                messages.append({"role": "tool", "content": result})

        return reply

    def _call_ollama(self, text, is_owner=None, source=None):
        self.history.append({"role": "user", "content": text})

        if len(self.history) > self.max_history * 2:
            self.history = self.history[-self.max_history * 2:]

        system_prompt = SYSTEM_PROMPT + _current_time_note() + (STRANGER_NOTE if is_owner is False else "")

        raw_reply = self._run_ollama_tool_loop(system_prompt, is_owner, source)
        reply = _sanitize_reply(raw_reply)

        # câu trả lời bị lỗi (rò tiếng Trung / lộ mô tả tool) — thử lại 1 lần thay vì
        # bắt Sơn nghe "chưa nghe rõ" ngay, vì lỗi này thường ngẫu nhiên, thử lại hay ra câu sạch
        if reply != raw_reply:
            print("[AI] Câu trả lời bị lỗi, thử lại 1 lần...")
            raw_reply = self._run_ollama_tool_loop(system_prompt, is_owner, source)
            reply = _sanitize_reply(raw_reply)

        self.history.append({"role": "assistant", "content": reply})

        # Lưu assistant response vào database
        self.db.save_conversation("assistant", reply, model_used=self.model)

        return reply

    def _run_gemini_tool_loop(self, contents, system_prompt, is_owner, force_tool=False, source=None):
        """Tương đương _run_ollama_tool_loop nhưng cho Gemini. Gemini KHÔNG cho gộp
        google_search (built-in tool) với function calling tuỳ chỉnh trong cùng 1 request
        (API trả lỗi 400 INVALID_ARGUMENT nếu gộp) — nên online giờ ưu tiên tool thật
        (mở app, ghi chú...) thay vì tra cứu web, đổi lại đồng bộ được với offline.

        force_tool=True ép model PHẢI gọi 1 tool ở lượt đầu (tool_config mode="ANY") — dùng
        khi thử lại sau khi phát hiện model bịa câu xác nhận mà không gọi tool thật (xem
        _claims_action_without_tool). Đo thực tế: mode="ANY" gọi đúng tool 5/5 lần, trong khi
        không force thì model bỏ qua tool ~80% số lần với prompt persona dài của EVA.
        Trả về (reply, tool_called) — tool_called để _call_gemini biết có cần thử lại hay không."""
        config_kwargs = dict(
            system_instruction=system_prompt,
            tools=[types.Tool(function_declarations=tools.as_gemini_tools())],
        )
        if force_tool:
            config_kwargs["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="ANY")
            )
        config = types.GenerateContentConfig(**config_kwargs)

        reply = "Không thể hoàn tất yêu cầu, Sơn."
        tool_called = False
        for _ in range(tools.MAX_TOOL_ITERATIONS):
            response = self._gemini_client.models.generate_content(
                model=self.online_model, contents=contents, config=config,
            )
            candidate_content = response.candidates[0].content
            function_calls = [p.function_call for p in candidate_content.parts if p.function_call]

            if not function_calls:
                reply = (response.text or "").strip()
                break

            tool_called = True
            contents.append(candidate_content)
            response_parts = [
                types.Part(function_response=types.FunctionResponse(
                    name=fc.name,
                    response={"result": tools.execute(fc.name, dict(fc.args), is_owner=is_owner, source=source)},
                ))
                for fc in function_calls
            ]
            contents.append(types.Content(role="user", parts=response_parts))

        return reply, tool_called

    def _call_gemini(self, text, is_owner=None, source=None):
        self.history.append({"role": "user", "content": text})

        if len(self.history) > self.max_history * 2:
            self.history = self.history[-self.max_history * 2:]

        def build_contents():
            return [
                types.Content(
                    role=("user" if msg["role"] == "user" else "model"),
                    parts=[types.Part(text=msg["content"])],
                )
                for msg in self.history
            ]

        system_prompt = SYSTEM_PROMPT + _current_time_note() + (STRANGER_NOTE if is_owner is False else "")
        raw_reply, tool_called = self._run_gemini_tool_loop(build_contents(), system_prompt, is_owner, source=source)

        # model bịa câu xác nhận hành động mà không thực sự gọi tool — ép gọi tool thật ở lượt
        # thử lại thay vì để Sơn tưởng đã xong trong khi thực tế chưa làm gì cả.
        if not tool_called and _claims_action_without_tool(raw_reply):
            print("[AI] Gemini có vẻ bịa câu xác nhận mà chưa gọi tool — ép gọi tool, thử lại 1 lần...")
            raw_reply, tool_called = self._run_gemini_tool_loop(
                build_contents(), system_prompt, is_owner, force_tool=True, source=source
            )

        reply = _sanitize_reply(raw_reply)

        self.history.append({"role": "assistant", "content": reply})

        # Lưu assistant response vào database
        self.db.save_conversation("assistant", reply, model_used=self.online_model)

        return reply

    def get_response_nowait(self):
        try:
            return self._response_queue.get_nowait()
        except queue.Empty:
            return None

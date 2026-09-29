from html import escape

W, H = 1700, 1390
out = []
FONT = "'Segoe UI', Arial, sans-serif"

C = {
    "ink": "#1d2433", "dim": "#5a6475", "line": "#c9ccd3",
    "actor": "#334155", "actor_bg": "#eef2f7",
    "io": "#2f6fb0", "io_bg": "#eaf2fb",
    "brain": "#6b4fa0", "brain_bg": "#f2edf9",
    "bg": "#2e7d5b", "bg_bg": "#e9f5ef",
    "data": "#7a6a55", "data_bg": "#f5f1ea",
    "net": "#b86a1e", "net_bg": "#fbf1e6",
    "p1": "#d0542f", "p1_bg": "#fdf0eb",
}


def text(x, y, s, size=13, weight=400, color=None, anchor="start", italic=False):
    style = "font-style:italic;" if italic else ""
    out.append(
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
        f'fill="{color or C["ink"]}" text-anchor="{anchor}" style="{style}">{escape(s)}</text>'
    )


def rect(x, y, w, h, stroke, fill, dashed=False, r=10, sw=1.5):
    dash = ' stroke-dasharray="7 5"' if dashed else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{dash}/>')


def box(x, y, w, h, title, lines, color, bg, dashed=False, tag=None, title_size=15):
    rect(x, y, w, h, color, bg, dashed)
    out.append(f'<rect x="{x}" y="{y}" width="6" height="{h}" rx="3" fill="{color}"/>')
    text(x + 18, y + 26, title, title_size, 700, color)
    if tag:
        tw = 9 + len(tag) * 7
        rect(x + w - tw - 10, y + 10, tw, 22, C["p1"], "#fff", r=11, sw=1.2)
        text(x + w - tw / 2 - 10, y + 25, tag, 11.5, 700, C["p1"], "middle")
    yy = y + 50
    for ln in lines:
        col, wt, sz = C["ink"], 400, 13
        if isinstance(ln, tuple):
            ln, kind = ln
            if kind == "p1":
                col, wt = C["p1"], 600
            elif kind == "dim":
                col = C["dim"]
        text(x + 18, yy, ln, sz, wt, col)
        yy += 20


def arrow(x1, y1, x2, y2, color="#64748b", both=False, dashed=False, label=None, lx=None, ly=None):
    dash = ' stroke-dasharray="6 5"' if dashed else ""
    start = ' marker-start="url(#ah-s)"' if both else ""
    out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2"{dash} marker-end="url(#ah)"{start}/>')
    if label:
        text(lx if lx is not None else x1 + 8, ly if ly is not None else (y1 + y2) / 2 + 4, label, 12, 600, C["dim"])


def layer_header(x, y, s, color, note=None):
    text(x, y, s.upper(), 12.5, 700, color)
    if note:
        text(x + len(s) * 9.2 + 16, y, note, 12.5, 400, C["dim"], italic=True)


W, H = 1720, 1410
SAFE = C["p1"]          # màu cam đỏ cho các luồng an toàn (SOS, SMS)
SAFE_BG = C["p1_bg"]

out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
out.append('<defs>'
           '<marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#64748b"/></marker>'
           '<marker id="ah-s" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#64748b"/></marker>'
           f'<marker id="ah-safe" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{SAFE}"/></marker>'
           '</defs>')
out.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

# ---------- Tiêu đề ----------
text(40, 50, "Kiến trúc hệ thống EVA Community", 28, 700)
text(40, 78, "Trợ lý giọng nói tiếng Việt cho người cao tuổi & người khiếm thị — chạy tại nhà, điều khiển hoàn toàn bằng giọng nói", 15, 400, C["dim"])
rect(1300, 34, 16, 16, SAFE, SAFE_BG, r=3)
text(1324, 47, "Luồng an toàn: SOS, nhắc thuốc, báo người thân", 13, 600, SAFE)

# ---------- Người dùng ----------
AY, AH = 110, 105
box(40, AY, 1040, AH, "Người cao tuổi / người khiếm thị", [
    "Nói chuyện với EVA tại chỗ qua mic + loa của máy — không cần nhìn màn hình, không cần chuột, bàn phím",
    "Đánh thức bằng “EVA ơi” hoặc vỗ tay 2 lần · kêu “cứu tôi” thì EVA nghe thấy ngay, không cần đánh thức",
], C["actor"], C["actor_bg"])
box(1100, AY, 560, AH, "Người thân / con cháu (điện thoại)", [
    "Nhận SMS khi khẩn cấp, bỏ lỡ thuốc, không thấy hoạt động",
    "Link /family: xem tình trạng chung (chỉ xem)",
], C["actor"], C["actor_bg"])

# ---------- Máy chủ ----------
SX, SY, SW, SH = 40, 262, 1620, 880
rect(SX, SY, SW, SH, "#94a3b8", "#f8fafc", r=16, sw=2)
text(850, SY + 32, "Máy tính tại nhà (PC / laptop có GPU) · main.py", 17, 700)

# Lớp 1: Giao tiếp
L1 = SY + 70
layer_header(60, L1, "1 · Giao tiếp", C["io"])
box(60, L1 + 12, 490, 176, "VoiceEngine — nghe", [
    "Đánh thức: “EVA ơi”, “dậy đi” hoặc vỗ tay 2 lần",
    "webrtcvad lọc tiếng → PhoWhisper (tiếng Việt)",
    "Nhận diện người nói (resemblyzer), khuôn mặt (tuỳ chọn)",
    ("Câu kêu cứu → SOS ngay, không cần đánh thức", "p1"),
    ("Nghe thấy tiếng người → báo “có người ở nhà”", "dim"),
    ("(chỉ ghi nhận thời điểm, không lưu nội dung)", "dim"),
], C["io"], C["io_bg"])
box(570, L1 + 12, 490, 176, "TTSEngine — nói", [
    "Edge-TTS giọng tiếng Việt → loa",
    "Tốc độ nói chỉnh được cho người nghe chậm",
    "Bộ đệm câu hay dùng → phản hồi tức thì",
    ("Câu nhắc thuốc / cảnh báo / SOS xếp hàng chờ,", "p1"),
    ("không bị mất khi EVA đang nói dở", "p1"),
], C["io"], C["io_bg"])
box(1100, L1 + 12, 540, 176, "WebInterface (Flask) — trang người thân", [
    "/family — trang chỉ xem, chữ lớn, tương phản cao",
    "/api/family_status — đang hoạt động hay đang chờ,",
    "lần hoạt động gần nhất, ghi chú gần đây",
    ("FAMILY_TOKEN trong link: không điều khiển được gì,", "dim"),
    ("không nghe lại hội thoại, không xem camera", "dim"),
], C["io"], C["io_bg"])

arrow(300, AY + AH, 300, L1 + 10, label="nói", lx=310, ly=AY + AH + 30)
arrow(815, L1 + 10, 815, AY + AH, label="nghe", lx=825, ly=AY + AH + 30)
arrow(1370, AY + AH, 1370, L1 + 10, label="mở link chỉ xem", lx=1380, ly=AY + AH + 30)

# Lớp 2: Bộ não
L2 = L1 + 230
layer_header(60, L2, "2 · Bộ não", C["brain"], "mọi câu nói đi qua on_user_input → AIBrain")
box(60, L2 + 12, 520, 178, "AIBrain — hiểu câu nói, quyết định làm gì", [
    "Online (mặc định): Google Gemini — cần gia đình đồng ý",
    "Offline (tuỳ chọn): Ollama qwen2.5:14b, cần GPU mạnh",
    "Xưng hô theo từng gia đình (“bà”, “ông Ba”...)",
    "Gọi công cụ qua function calling",
    "Lọc lỗi: lộ tên tool, chữ Hán, câu kết rập khuôn",
    ("“uống rồi” / “chưa” được xử lý thẳng, không qua AI", "dim"),
], C["brain"], C["brain_bg"])
arrow(580, L2 + 100, 618, L2 + 100, color=C["brain"])
rect(620, L2 + 12, 1020, 178, C["brain"], C["brain_bg"])
out.append(f'<rect x="620" y="{L2 + 12}" width="6" height="178" rx="3" fill="{C["brain"]}"/>')
text(638, L2 + 38, "tools.py — 36 công cụ EVA có thể dùng", 15, 700, C["brain"])
chips = [
    ("Điều khiển máy", ["mở app / link / thư mục", "âm lượng, chụp màn hình", "khoá, tắt, khởi động lại"], False),
    ("Trợ năng", ["đọc to màn hình", "gõ hộ (đọc chính tả)", "điều hướng trình duyệt"], False),
    ("Sức khoẻ & nhắc việc", ["ghi sức khoẻ, xem xu hướng", "đặt / xem / huỷ nhắc", "ghi chú"], False),
    ("Tiện ích & liên lạc", ["gọi video người thân", "thời tiết, Google/YouTube", "CPU, RAM, ổ đĩa, git"], False),
    ("request_help", ["AI tự gọi trợ giúp khi", "nghe kể té ngã, khó thở,", "đau ngực — ai cũng gọi được"], True),
]
cx, cw, cg = 638, 188, 10
for i, (t, ls, safe) in enumerate(chips):
    x = cx + i * (cw + cg)
    col = SAFE if safe else C["brain"]
    rect(x, L2 + 54, cw, 124, col, SAFE_BG if safe else "#ffffff", r=8, sw=1.2)
    text(x + 12, L2 + 76, t, 13.5, 700, col)
    for j, ln in enumerate(ls):
        text(x + 12, L2 + 100 + j * 20, ln, 12.5, 400)

# Lớp 3: Luồng nền
L3 = L2 + 232
layer_header(60, L3, "3 · Luồng nền chủ động", C["bg"], "tự lên tiếng không cần hỏi → nói qua TTS, lưu lịch sử")
bw, bg_ = 252, 13.6
bgs = [
    ("HealthMonitor", ["Ngủ < 6 tiếng nhiều đêm", "Báo triệu chứng lặp lại", "→ nhắc nghỉ ngơi, đi khám"], False),
    ("ActivityMonitor", ["Quá 10h chưa thấy dậy, hoặc", "ban ngày im lặng > 4 tiếng", "→ hỏi han → 15 phút không", "   ai trả lời → báo người thân", ("+ suy đoán giấc ngủ", "dim")], True),
    ("MedicationReminder", ["Sáng: chào + đọc thời tiết", "Nhắc thuốc → chờ “uống rồi”", "→ im lặng: hỏi lại 15 phút/lần", "→ 3 lần không trả lời:", "   ghi “bỏ lỡ”, báo người thân"], True),
    ("ReminderScheduler", ["Nhắc 1 lần do người dùng đặt", "“3 giờ chiều nhắc tôi…”", ("Còn nguyên sau khi", "dim"), ("khởi động lại máy", "dim")], False),
    ("TempMonitor", ["Cảnh báo máy quá nóng", "(máy chạy 24/7)"], False),
    ("Notifier", ["Nhắn SMS kèm giờ cho", "mọi số người thân đã cài", "Tự thử lại 3 lần nếu lỗi mạng", ("Không bao giờ nói “đã báo”", "dim"), ("khi chưa gửi được", "dim")], True),
]
for i, (t, ls, safe) in enumerate(bgs):
    x = 60 + i * (bw + bg_)
    col = SAFE if safe else C["bg"]
    box(x, L3 + 12, bw, 158, t, ls, col, SAFE_BG if safe else C["bg_bg"], title_size=14.5)

# Lớp 4: Dữ liệu
L4 = L3 + 212
layer_header(60, L4, "4 · Dữ liệu — lưu tại nhà", C["data"])
box(60, L4 + 12, 700, 88, "SQLite (eva.db)", [
    "conversation_history · health_logs (gồm lịch sử uống thuốc) · reminders",
    "notes · app_logs (sự kiện, SOS, cảnh báo không hoạt động) · gesture_logs",
], C["data"], C["data_bg"])
box(780, L4 + 12, 420, 88, "config/settings.yaml", [
    "Xưng hô, tốc độ nói, giờ uống thuốc, câu kêu cứu,",
    "ngưỡng không hoạt động, số ĐT người thân",
], C["data"], C["data_bg"])
box(1220, L4 + 12, 420, 88, ".env — bí mật, không đưa lên git", [
    "FAMILY_TOKEN · ESMS_API_KEY · ESMS_SECRET_KEY",
    "GEMINI_API_KEY · OPENWEATHER_API_KEY",
], C["data"], C["data_bg"])

# ---------- Internet ----------
IY = SY + SH + 58
layer_header(40, IY - 14, "Internet", C["net"])
nets = [
    ("Microsoft Edge-TTS", ["Đổi câu trả lời thành giọng nói", ("gửi: chữ cần đọc (có bộ đệm)", "dim")], False),
    ("Google Gemini", ["Chế độ online (mặc định)", ("gửi: lời trò chuyện dạng chữ", "dim")], False),
    ("OpenWeatherMap", ["Tra thời tiết", ("gửi: tên thành phố", "dim")], False),
    ("Hugging Face", ["Tải model PhoWhisper lần đầu", ("không gửi dữ liệu người dùng", "dim")], False),
    ("eSMS.vn", ["Chuyển SMS tới điện thoại người thân", ("gửi: nội dung cảnh báo ngắn", "dim")], True),
]
nw, ng = 312, 15
for i, (t, ls, safe) in enumerate(nets):
    x = 40 + i * (nw + ng)
    col = SAFE if safe else C["net"]
    box(x, IY, nw, 92, t, ls, col, SAFE_BG if safe else C["net_bg"], title_size=14.5)
    arrow(x + nw / 2, SY + SH, x + nw / 2, IY - 2, color=col if safe else "#94a3b8", dashed=True)

# SMS: từ eSMS.vn vòng lên người thân theo lề phải
ex = 40 + 4 * (nw + ng) + nw  # mép phải ô eSMS
out.append(f'<path d="M {ex} {IY + 46} H {W - 22} V {AY + AH / 2} H 1662" fill="none" stroke="{SAFE}" '
           f'stroke-width="2.2" stroke-dasharray="7 5" marker-end="url(#ah-safe)"/>')
text(W - 30, AY + AH / 2 - 10, "SMS", 12.5, 700, SAFE, "end")

# ---------- Chân trang ----------
text(40, H - 70, "Luồng khẩn cấp: nghe “cứu tôi” → EVA trấn an tại chỗ → Notifier → eSMS.vn → SMS tới người thân — đi thẳng, không chờ AI suy nghĩ.", 13, 600, SAFE)
text(40, H - 46, "Chỉ các dịch vụ Internet ở trên nhận dữ liệu rời khỏi nhà — giọng nói gốc, hình khuôn mặt và cơ sở dữ liệu luôn nằm trên máy tại nhà.", 13, 600, C["net"])
text(40, H - 22, "Mất mạng: vẫn nhắc thuốc, vẫn nhận ra tiếng kêu cứu và trấn an tại chỗ (giọng đọc tạo sẵn) — riêng SMS cần mạng. EVA không phải thiết bị y tế.", 13, 400, C["dim"])
text(W - 40, H - 22, "Sau Giai đoạn 1 · 09/2026", 12, 400, C["dim"], "end")

out.append("</svg>")

import sys
with open(sys.argv[1], "w", encoding="utf-8") as f:
    f.write("\n".join(out))

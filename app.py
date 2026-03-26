import os
import time
import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import google.generativeai as genai

# Load biến môi trường từ file .env (bỏ qua nếu chưa cài python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ===== CẤU HÌNH LOGGING =====
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),                        # In ra console
        logging.FileHandler("app.log", encoding="utf-8")  # Ghi ra file
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type"]}})

# Cấu hình Gemini API Key
# Đặt biến môi trường GEMINI_API_KEY hoặc thay thế trực tiếp vào đây
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-2.5-flash")

# Log trạng thái API key khi khởi động
if GEMINI_API_KEY:
    logger.info("✅ GEMINI_API_KEY đã được tải thành công (độ dài: %d ký tự).", len(GEMINI_API_KEY))
else:
    logger.critical("❌ GEMINI_API_KEY chưa được cấu hình! Kiểm tra file .env")


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/generate_recipe", methods=["POST", "OPTIONS"])
def generate_recipe():
    """
    Nhận dữ liệu JSON gồm:
      - ingredients (list[str] hoặc str): Nguyên liệu hiện có
      - diet (str): Chế độ ăn kiêng (vd: "chay", "keto", "không")
      - allergies (list[str] hoặc str): Dị ứng thực phẩm (vd: ["đậu phộng", "hải sản"])

    Trả về JSON chứa:
      - dish_name: Tên món ăn
      - recipe: Công thức nấu từng bước
      - calories: Ước tính lượng calories
    """
    # Trả về 200 ngay cho preflight OPTIONS request
    if request.method == "OPTIONS":
        return jsonify({"ok": True}), 200

    logger.info("📥 [REQUEST] POST /api/generate_recipe từ %s", request.remote_addr)

    data = request.get_json(force=True, silent=True)
    if not data:
        logger.warning("⚠️  Body không hợp lệ hoặc thiếu JSON.")
        return jsonify({"error": "Yêu cầu phải có dữ liệu JSON hợp lệ."}), 400

    ingredients = data.get("ingredients", "")
    diet = data.get("diet", "Không có yêu cầu đặc biệt")
    allergies = data.get("allergies", "Không có")

    # Chuyển list thành chuỗi nếu cần
    if isinstance(ingredients, list):
        ingredients = ", ".join(ingredients)
    if isinstance(allergies, list):
        allergies = ", ".join(allergies) if allergies else "Không có"

    logger.debug("   ingredients : %s", ingredients)
    logger.debug("   diet        : %s", diet)
    logger.debug("   allergies   : %s", allergies)

    if not ingredients:
        logger.warning("⚠️  Thiếu nguyên liệu trong request.")
        return jsonify({"error": "Vui lòng cung cấp danh sách nguyên liệu (ingredients)."}), 400

    prompt = f"""
Bạn là một đầu bếp chuyên nghiệp. Dựa trên thông tin sau, hãy đề xuất một món ăn phù hợp và cung cấp thông tin theo đúng định dạng yêu cầu.

Nguyên liệu hiện có: {ingredients}
Chế độ ăn kiêng: {diet}
Dị ứng thực phẩm: {allergies}

Hãy trả lời theo đúng định dạng sau (không thêm bất kỳ nội dung nào ngoài định dạng):

TÊN MÓN ĂN: <tên món>

CÔNG THỨC NẤU:
1. <bước 1>
2. <bước 2>
3. <bước 3>
(tối đa 6 bước, ngắn gọn, súc tích)

ƯỚC TÍNH CALORIES: <con số> kcal (mỗi khẩu phần)
"""

    try:
        logger.info("🤖 Đang gọi Gemini API...")
        t0 = time.time()

        # Retry tối đa 3 lần khi gặp lỗi 429 (quota exceeded)
        max_retries = 3
        retry_delay = 35  # giây
        response = None
        for attempt in range(1, max_retries + 1):
            try:
                response = model.generate_content(prompt)
                break
            except Exception as api_err:
                if "429" in str(api_err) and attempt < max_retries:
                    logger.warning("⚠️  Lỗi 429 quota (lần %d/%d), thử lại sau %ds...", attempt, max_retries, retry_delay)
                    time.sleep(retry_delay)
                else:
                    raise

        elapsed = time.time() - t0
        text = response.text.strip()
        logger.info("✅ Gemini phản hồi thành công (%.2fs — %d ký tự)", elapsed, len(text))

        # Parse kết quả từ Gemini
        dish_name = ""
        recipe = ""
        calories = ""

        lines = text.split("\n")
        section = None
        recipe_lines = []

        for line in lines:
            line = line.strip()
            if line.startswith("TÊN MÓN ĂN:"):
                dish_name = line.replace("TÊN MÓN ĂN:", "").strip()
                section = "name"
            elif line.startswith("CÔNG THỨC NẤU:"):
                section = "recipe"
            elif line.startswith("ƯỚC TÍNH CALORIES:"):
                calories = line.replace("ƯỚC TÍNH CALORIES:", "").strip()
                section = "calories"
            elif section == "recipe" and line:
                recipe_lines.append(line)

        recipe = "\n".join(recipe_lines)

        logger.info("📤 [RESPONSE] dish_name=%r | calories=%r", dish_name, calories)
        return jsonify({
            "dish_name": dish_name,
            "recipe": recipe,
            "calories": calories,
            "raw": text  # Trả về toàn bộ phản hồi gốc để debug nếu cần
        }), 200

    except Exception as e:
        logger.error("❌ Lỗi khi gọi Gemini API: %s", str(e), exc_info=True)
        return jsonify({"error": f"Lỗi khi gọi Gemini API: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)

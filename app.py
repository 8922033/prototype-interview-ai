import os
import base64

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from google import genai

# =========================
# 環境変数
# =========================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY が設定されていません")

client = genai.Client(api_key=GEMINI_API_KEY)

# =========================
# Flask
# =========================

app = Flask(__name__)

app.secret_key = os.getenv(
    "SECRET_KEY",
    "prototype_interview_ai"
)

# =========================
# ルート
# =========================

@app.route("/")
def index():
    return render_template("index.html")

# =========================
# システムプロンプト
# =========================

def build_system_prompt(personality, questions, url):

    personality_text = ""

    if personality == "active":
        personality_text = """
ユーザーは積極的に話すタイプです。
会話を広げながら自然に深掘りしてください。
"""
    else:
        personality_text = """
ユーザーは受け身です。
短く質問し、一問一答で進めてください。
"""

    q_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])

    return f"""
あなたはプロトタイプ評価インタビューAIです。

目的：ユーザーの使用感を引き出す

{personality_text}

【質問項目】
{q_text}

【プロトタイプURL】
{url}

必要に応じて
- 理由
- 具体例
- 改善点
を深掘りしてください。

会話を自然に進めてください。
"""

# =========================
# チャットAPI
# =========================

@app.route("/chat", methods=["POST"])
def chat():

    try:
        data = request.get_json()

        personality = data.get("personality", "passive")
        questions = data.get("questions", [])
        history = data.get("history", [])
        url = data.get("prototype_url", "")

        image_base64 = data.get("prototype_image", "")
        mime_type = data.get("prototype_image_mime_type", "image/png")

        system_prompt = build_system_prompt(personality, questions, url)

        contents = []

        # システム
        contents.append({
            "role": "user",
            "parts": [{"text": system_prompt}]
        })

        # 画像
        if image_base64:
            contents.append({
                "role": "user",
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": image_base64
                        }
                    },
                    {
                        "text": "この画像はプロトタイプです。内容を理解してください。"
                    }
                ]
            })

        # 履歴
        for h in history:
            contents.append({
                "role": h.get("role", "user"),
                "parts": [{"text": h.get("content", "")}]
            })

        # ユーザー最新発話
        user_text = history[-1]["content"] if history else ""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents
        )

        text = getattr(response, "text", None) or "応答なし"

        return jsonify({
            "success": True,
            "message": text
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================
# 起動
# =========================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
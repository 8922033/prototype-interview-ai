import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev_key")

# -------------------------
# トップページ
# -------------------------
@app.route("/")
def index():
    return render_template("index.html")


# -------------------------
# プロンプト
# -------------------------
def build_system_prompt(personality, questions, url):

    if personality == "active":
        personality_text = "ユーザーは積極的。会話を広げて深掘りする。"
    else:
        personality_text = "ユーザーは受け身。短く質問し一問一答で進める。"

    q_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])

    return f"""
あなたはプロトタイプ評価インタビューAIです。

目的：使用感の深い理解

{personality_text}

【質問項目】
{q_text}

【プロトタイプURL】
{url}

・自然な会話で進める
・浅い回答は深掘りする
・話題逸脱は戻す
"""


# -------------------------
# チャットAPI
# -------------------------
@app.route("/chat", methods=["POST"])
def chat():

    try:
        data = request.get_json()

        personality = data.get("personality", "passive")
        questions = data.get("questions", [])
        history = data.get("history", [])
        url = data.get("prototype_url", "")

        images = data.get("prototype_images", [])

        system_prompt = build_system_prompt(personality, questions, url)

        contents = []

        # system
        contents.append({
            "role": "user",
            "parts": [{"text": system_prompt}]
        })

        # 画像（複数対応）
        for img in images:
            contents.append({
                "role": "user",
                "parts": [{
                    "inline_data": {
                        "mime_type": img.get("mime_type", "image/png"),
                        "data": img.get("data")
                    }
                }]
            })

        # 履歴
        for h in history:
            contents.append({
                "role": h.get("role", "user"),
                "parts": [{"text": h.get("content", "")}]
            })

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


if __name__ == "__main__":
    app.run(debug=True)
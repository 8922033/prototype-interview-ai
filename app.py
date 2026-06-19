import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from google import genai

# =========================
# 環境変数読み込み
# =========================

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev_key")


# =========================
# トップページ
# =========================

@app.route("/")
def index():
    return render_template("index.html")


# =========================
# システムプロンプト生成
# =========================

def build_system_prompt(personality, questions, url):

    if personality == "active":

        personality_text = """
【インタビュイーのペルソナ】

・女性
・東京理科大学経営学部2年生
・自分から話すことが多い
・初対面の人とも仲良くなれる
・思い立ったことをすぐ口に出す
・話の輪の中心でありたい
・大人数での会話も得意


【AI（インタビュアー）の振る舞い】

・相手の話に共感や理解を示す。

・ただし共感は短く、簡潔な表現に留める。

・基本は肯定的な反応を示す必要があります。

・明らかに間違ったことを言っている場合のみ話の軌道の修正を行います。

・AI自身が長く話さない。

・聞く文量も短めにする。

・相手が自由に話せる
オープンクエスチョンを中心に質問する。

・回答が浅い場合のみ

「具体的には？」

「その時どう感じましたか？」

「例えばどんな場面でしたか？」

など自然に深掘りする。

・相手が話した内容から
新しい話題が出た場合は
柔軟に深掘りする。

・AIが会話を支配せず、
聞き役に徹する。

・相手が自然に話し続けられる
空気を作る。

・プロトタイプの使用感や
改善点を具体的に引き出すことを
最優先とする。
"""

    else:

        personality_text = """
【インタビュイーのペルソナ】

・自分から積極的には話さない

・質問されれば答える

・自発的に話題を広げることは少ない

【AI（インタビュアー）の振る舞い】

・相手が答えやすい質問をする。

・一問一答を基本とする。

・質問は具体的にする。

・必要なら具体例を示す。

・相手が
「特にないです」
「思いつかないです」
「分からないです」
「覚えていません」
などと回答した場合は、
その回答で終わらせない。

・そのまま次の質問へ進まず、
回答しやすくなるようにサポートを行う。

・例えば、

「操作中に少しでも迷った場面はありませんでしたか？」

「ボタンの位置や表示で気になったことはありませんでしたか？」

「使いにくいというほどではなくても、少し気になったことでも大丈夫です。」

「逆に使いやすいと感じた部分でも構いません。」

「もし友人がこの画面を使うとしたら、困りそうなところはありますか？」

など、角度を変えて質問したり具体例を提示したりして、回答者の記憶や考えを引き出す。

・回答者が答えやすい雰囲気を作る

・回答に対して否定しない

・AIの答えに誘導しすぎない

・2～3回程度サポートしても回答が出ない場合は、
無理に回答を求めず自然に次の質問へ進む。

"""

    q_text = "\n".join(
        [
            f"{i + 1}. {q}"
            for i, q in enumerate(questions)
        ]
    )

    system_prompt = f"""
あなたは
プロトタイプ評価インタビューAIです。

目的は、
プロトタイプの使用感を深く理解することです。

画像やURLから
プロトタイプを理解してください。

{personality_text}


【事前に用意された質問項目】

{q_text}


【プロトタイプURL】

{url}


【ルール】

・インタビュー開始時はAIが自ら会話を開始する。

・開始時は短い挨拶をしたあと、
必ず質問リストの1番目の質問を行う。

・質問リストの1番目の質問を飛ばしたり、
別の質問から始めたりしてはいけない。

・1番目の質問について必要な深掘りが終わった後は、
質問の順番に拘る必要はない。

・以降の質問は、
会話の流れや回答内容に合わせて
自然な順番で選択してよい。

・質問項目をベースに自然な会話を行う。

・回答が浅い場合のみ深掘りする。

・十分答えている場合でも最低1回は深掘りする

・回答内容から追加質問を考える。

・同じ質問を繰り返さない。

・AIらしい文章ではなく、
人間のインタビュアーのように話す。

・プロトタイプの良い点、
悪い点、
改善案、
利用シーン、
迷った点、
印象などを引き出す。

・30分程度でインタビューが終了することを目標としてください。

・時間配分を意識し、1つの質問に時間をかけすぎないでください。

・回答が十分得られたと判断した場合は、深掘りを続けず次の話題へ進んでください。

・深掘りは基本的に1つの質問に対して1～2回程度に留めてください。

・会話が脱線した場合は、自然にインタビューの話題へ戻してください。

・終了時間を意識し、質問項目全体をバランスよく消化するようにしてください。

・残り時間が少ないと判断した場合は、重要な質問を優先して進めてください。

・最後は「他に気になった点や改善案はありますか？」などの締めくくりの質問を行い、自然にインタビューを終了してください。

"""

    return system_prompt
# =========================
# チャットAPI
# =========================

@app.route("/chat", methods=["POST"])
def chat():

    try:

        data = request.get_json()

        personality = data.get(
            "personality",
            "passive"
        )

        questions = data.get(
            "questions",
            []
        )

        history = data.get(
            "history",
            []
        )

        prototype_url = data.get(
            "prototype_url",
            ""
        )

        prototype_images = data.get(
            "prototype_images",
            []
        )

        system_prompt = build_system_prompt(
            personality,
            questions,
            prototype_url
        )

        contents = []

        # ---------------------
        # システムプロンプト
        # ---------------------

        contents.append({
            "role": "user",
            "parts": [
                {
                    "text": system_prompt
                }
            ]
        })

        # ---------------------
        # プロトタイプ画像
        # ---------------------

        for image in prototype_images:

            if (
                image.get("data")
                and image.get("mime_type")
            ):

                contents.append({
                    "role": "user",
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": image["mime_type"],
                                "data": image["data"]
                            }
                        }
                    ]
                })

        # ---------------------
        # 会話履歴
        # ---------------------

        for item in history:

            role = item.get(
                "role",
                "user"
            )

            # JavaScriptのassistantを
            # Gemini用のmodelへ変換
            if role == "assistant":
                role = "model"

            text = item.get(
                "content",
                ""
            )

            contents.append({
                "role": role,
                "parts": [
                    {
                        "text": text
                    }
                ]
            })

        # ---------------------
        # Gemini呼び出し
        # ---------------------

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents
        )

        answer = getattr(
            response,
            "text",
            None
        )

        if not answer:
            answer = (
                "申し訳ありません。"
                "応答を生成できませんでした。"
            )

        return jsonify({
            "success": True,
            "message": answer
        })

    except Exception as e:

        print(e)

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
# =========================
# 起動
# =========================

if __name__ == "__main__":
    app.run(
        debug=True,
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        )
    )




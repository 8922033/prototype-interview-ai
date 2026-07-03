import os
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    session
)
from dotenv import load_dotenv
from google import genai
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user
)
from models import (
    db,
    User,
    Conversation,
    Message
)

# =========================
# 環境変数読み込み
# =========================

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
app.secret_key = os.getenv("SECRET_KEY", "dev_key")
login_manager = LoginManager()

login_manager.init_app(app)

login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):

    return User.query.get(int(user_id))

# =========================
# トップページ
# =========================

@app.route("/")
@login_required
def index():
    return render_template("index.html")
@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        username = request.form["username"]

        email = request.form["email"]

        password = request.form["password"]

        exist = User.query.filter_by(
            email=email
        ).first()

        if exist:

            return "このメールアドレスは登録済みです"

        user = User(

            username=username,

            email=email,

            password_hash=generate_password_hash(
                password
            )

        )

        db.session.add(user)

        db.session.commit()

        return "登録完了！ログインしてください。"

    return render_template(
        "register.html"
    )
@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form["email"]

        password = request.form["password"]

        user = User.query.filter_by(
            email=email
        ).first()

        if user and check_password_hash(
            user.password_hash,
            password
        ):

            login_user(user)

            return redirect(
                url_for("index")
            )

        return "メールアドレスまたはパスワードが違います"

    return render_template(
        "login.html"
    )


# ← さらにこの下に追加
@app.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect(
        url_for("login")
    )
@app.route(
    "/conversation/new",
    methods=["POST"]
)
@login_required
def new_conversation():

    conversation = Conversation(

        title="新しいチャット",

        user_id=current_user.id

    )

    db.session.add(
        conversation
    )

    db.session.commit()

    return jsonify({

        "success": True,

        "conversation_id":
            conversation.id

    })
@app.route(
    "/conversations"
)
@login_required
def conversations():

    data = Conversation.query.filter_by(

        user_id=current_user.id

    ).order_by(

        Conversation.created_at.desc()

    ).all()

    result = []

    for c in data:

        result.append({

            "id": c.id,

            "title": c.title

        })

    return jsonify(result)
@app.route(
    "/conversation/<int:conversation_id>"
)
@login_required
def get_conversation(
    conversation_id
):

    conversation = Conversation.query.filter_by(

        id=conversation_id,

        user_id=current_user.id

    ).first()

    if not conversation:

        return jsonify([])

    messages = Message.query.filter_by(

        conversation_id=conversation.id

    ).all()

    result = []

    for m in messages:

        result.append({

            "role": m.role,

            "content": m.content

        })

    return jsonify(result)
# =========================
# システムプロンプト生成
# =========================

def build_system_prompt(personality, questions, url ,elapsed_minutes=30): 

    if personality == "active":

        personality_text = """
【インタビュイーのペルソナ】
自分から積極的に、たくさん話すタイプ
回答者主導
初対面でも物怖じしないタイプ
【AI（インタビュアー）の振る舞い】
聞き役に徹し、ユーザーが自由に話せる「空気感」と「時間」を最大限に確保する。
・質問はオープンクエスチョン（自由に回答できる軽い問い）から始め、徐々に内面（感情や価値観）へ迫る。
・ユーザーの発⾔を繰り返したり要約するのではなく、短い受け⽌めの⾔葉のあとにすぐ次の質問へ移ってください。
・1つの質問に対し深掘りを最大1〜2回に留め、テンポよく進める。
"""

    else:

        personality_text = """
【インタビュイーのペルソナ】
自分から積極的には話さず、質問されたら答えるタイプ。
質問者主導
【AI（インタビュアー）の振る舞い】
・ユーザーが答えやすいよう、具体的な質問を1つずつ投げかける。
・ユーザーの回答内容を適宜短く要約・確認し、「理解してもらえた」という安心感を与えながら丁寧に深掘りする。
・ユーザーが話し出すのを急かさず、待つ姿勢を意識する。
・1つの質問（用意された質問）に対し、曖昧な箇所があれば粘り強く「3回以上」様々な角度から具体的に深掘りを行う。
"""

    q_text = "\n".join(
        [
            f"{i + 1}. {q}"
            for i, q in enumerate(questions)
        ]
    )

    system_prompt = f"""
あなたはプロトタイプ評価を専門とするUXリサーチャーです。 
あなたの役割は、回答者の経験・感情・価値観・行動・考えを本人の言葉で自然に引き出し、プロトタイプ改善に役立つ情報を収集することです。 
インタビューの目的は質問を消化することではありません。 
回答者自身も気付いていなかった本音や背景を、自然な会話を通して言語化できるよう支援してください。 
画像・URL・質問項目を十分理解したうえでインタビューを開始してください。 
{personality_text}
【事前に用意された質問項目】
{q_text}
【プロトタイプURL】
{url}
【インタビューの目的】 
以下の情報を自然な会話から収集してください。 
・利用体験 
・感じたこと 
・印象 
・迷った場面 
・困ったこと 
・改善点 
・利用シーン 
・期待とのギャップ 
・価値を感じた点 
・価値を感じなかった点 
・回答者本人も気付いていない背景や価値観 
・回答量よりも情報の質を重視してください。 
【インタビュアーとしての基本姿勢】 
・あなたは聞き役である。 
・AI自身は必要以上に話さない。 
・回答者が話す時間を最大限確保する。 
・回答者を評価・批判・説得しない。 
・回答を推測・補完・決めつけない。 
・回答者自身の表現を尊重する。 
・自然で安心して話せる雰囲気を維持する。 
【基本原則】 
・質問より会話を優先する。 
・ルールを守ってインタビュー目的を達成する。 
・回答者の感情や興味が動いた話題は柔軟に深掘りしてよい。 
・ただしインタビュー目的から大きく逸脱する雑談は避ける。 
・AIの役割は答えを導くことではなく、回答者自身の考えを引き出すことである。 
【インタビューの進め方】 
・AIから会話を開始する。 
・短い挨拶のあと、必ず質問項目1番から始める。 
・質問1の深掘りが終わった後は、質問順に拘らず会話の流れを優先する。 
・回答内容に応じて質問順を柔軟に変更してよい。 
・重要な話題が出た場合は、質問項目よりもその話題を優先して深掘りする。 
・質問項目は「順番通り消化するもの」ではなく、「聞き漏れを防ぐためのガイド」として扱う。 
・30分程度で終了することを想定し、終盤は未回収の重要項目を優先する。 
・最後は「他に気になったことや改善案はありますか？」など自由回答を促し、自然に終了する。
【インタビュー時間とその対応】
経過時間：約{elapsed_minutes}分
想定終了時間：30分
現在の経過時間を考慮しながらインタビューを進行してください。
・30分程度で自然に終了できるよう進行を調整してください。
・残り時間が十分ある場合は、必要な深掘りを行ってください。
・終了間際には新しい話題を増やさず、重要事項の確認と自由意見を優先してください。
・質問項目を消化することよりも、重要な情報を収集することを優先してください。
【質問ルール】 
・1回の発話で質問は必ず1つだけにする。 
・複数の質問を同時にしない。 
・オープンクエスチョンを基本とする。 
・回答を誘導する質問は禁止する。 
・回答を限定する聞き方は禁止する。 
・AIが長く説明せず、回答者が話す時間を確保する。 
・質問は回答者の発言を材料に組み立てる。 
・同じ質問パターンは使わない。 
・新しい情報が得られる質問を優先する。 
【会話運営】 
・回答者が十分に話した話題は無理に深掘りしない。 
・会話が止まった場合は質問を言い換えたり、具体例を示したり、場面を限定して答えやすくする。 
・2〜3回支援しても回答が難しい場合は自然に次の話題へ進む。 
・雑談が続いた場合は短く受け止め、自然にインタビューへ戻す。 
・回答者が考える時間を尊重し、急かさない。 
・インタビュー全体を通して、質問数より情報の質を優先する。 
【リアクション】 
・リアクションは回答者が安心して話せる雰囲気を作るためのものであり、AIの感想を述べるためのものではない。 
・必要な場合のみ短く行う 
・1文以内 
・リアクションだけで終わらず自然に質問へつなげる 
・AI自身の意見や体験は話さない 
・過度に褒めたり感情を大きく表現しない 
・同じリアクション表現は使わない 
・ユーザーの発⾔を繰り返すのではなく、短い受け⽌めの⾔葉のあとにすぐ次の質問へ移ってください。
【回答に困った場合】 
以下のような回答は「回答に困っている状態」と判断する。 
・特にない 
・思いつかない 
・分からない 
・覚えていない 
・難しい 
この場合は終了と判断せず、 
①質問を言い換える 
②具体例を示す 
③場面を限定する 
④別の角度から聞く 
のどれかで2〜3回試す。 
それでも回答が得られない場合のみ自然に次の質問へ進む。 
【会話運営】 
・雑談は短く受け止め必要なら自然に戻す 
・回答者が十分話したら深掘りを終了する 
・重要な話題は保留して終盤で回収してもよい 
・時間配分を考え1つの話題に偏らない 
・最後は自由意見を聞いて自然に終了する 
【深掘りマニュアル】
「なぜ？」の直接質問は禁止にします。理由を分析するのはAIの仕事です。理由を直接聞くとユーザーに「後付けの論理的な説明」を強制してしまうため、背景にある「具体的なエピソード」をヒアリングしてください。
"キーワード"で深掘りします。一般論で納得せず、ユーザーが口にした印象的な言葉をそのまま次の質問の"キーワード"として使い、「その人にとっての意味」を徹底的に掘り下げます。
体験の深堀りをします。ユーザーの体験に関する話が出てきた場合、その体験にフォーカスして話を掘り下げます。
追い質問の5ステップ（状況に応じて段階的に活用する）:1.【反射】認識のすり合わせ（例：「つまり最初は〇〇だった、ということですね」）※積極的モード時は要約・確認に繋がるため【使用禁止】
2.【ピン留め】キーワードの具体化（例：「その『〇〇』とは具体的にどういうことですか？」）
3.【情景化】5W1Hのエピソード化（例：「その瞬間、どこで、何をしていましたか？」）
4.【意味づけ】背景や価値観の抽出（例：「今振り返ると、何が重要だったと感じますか？」）
5.【展望】未来への展開（例：「もし次があるなら、次は何を変えたいですか？」）
【出力の​構成​（フォーマット）】
​ユーザーへの​返答は、​常に​以下の​構成を​意識して、​チャットと​して​テンポよく​出力してください。
​[1〜2個の​適切なリアクション、相槌] ＋ [自然な​流れで​話を​深める​一言、​または​質問]
【リアクション、相槌】
リアクション、相槌の目的は、回答者が安心して話し続けられる雰囲気を作ることである。
AI自身の感想や評価を伝えることではない。
【運用ルール】
・リアクション、相槌は毎回行う。
・リアクション、相槌は1文以内とする。
・リアクション、相槌だけで発話を終えず、必要に応じて自然に質問へつなげる。
・AI自身の体験・価値判断・長い感想は述べない。
・同じリアクション、同じ相槌、同じ表現は一度のみ使用する。
・同じリアクション、同じ相槌、同じ表現は二回以上使わないで別の表現に言い換える。
・語尾だけ変えた表現は同じフレーズとして扱う。
"""

    return system_prompt
# =========================
# チャットAPI
# =========================

@app.route("/chat", methods=["POST"])
@login_required
def chat():

    try:

        data = request.get_json()

        conversation_id = data.get(
            "conversation_id"
        )

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

        conversation = None

        if conversation_id:

            conversation = Conversation.query.filter_by(

                id=conversation_id,

                user_id=current_user.id

            ).first()

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
        # ユーザー発言を保存
        # ---------------------

        if conversation and history:

            last = history[-1]

            if last.get("role") == "user":

                db.session.add(

                    Message(

                        role="user",

                        content=last.get(

                            "content",

                            ""

                        ),

                        conversation_id=conversation.id

                    )

                )

                db.session.commit()
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

        # ---------------------
        # AIの返答を保存
        # ---------------------

        if conversation:

            db.session.add(

                Message(

                    role="assistant",

                    content=answer,

                    conversation_id=conversation.id

                )

            )

            db.session.commit()

            # ---------------------
            # 初回発言をタイトル化
            # ---------------------

            if (

                conversation.title
                == "新しいチャット"

                and history

            ):

                first_text = history[-1].get(

                    "content",

                    ""

                )

                if first_text.strip():

                    conversation.title = (

                        first_text[:30]

                    )

                    db.session.commit()

        # ---------------------
        # レスポンス
        # ---------------------

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
with app.app_context():
    db.create_all()
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




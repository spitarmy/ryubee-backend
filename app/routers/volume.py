"""AI体積見積もりルーター: 画像をOpenAI GPT-4o Visionに投げてJSONを受け取る"""
import os
import json
import base64
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from openai import AsyncOpenAI
from app.database import get_db
from app import models, auth

router = APIRouter(prefix="/v1/volume-estimate", tags=["volume"])

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# モデル定義など
SYSTEM_PROMPT = """
あなたは、不用品回収・ゴミ処理のプロフェッショナル見積もりAIです。
ユーザーから提供された画像（複数可）と追加環境情報をもとに、極めて正確な「立米(m3)」を算出し、以下のJSONフォーマットで応答してください。

【計算プロセスと精度向上の超重要ルール】
1. 画像の「奥行き(Depth)」を必ず認識してください。写真に映る表面積だけでなく、立体としての体積(幅×高さ×奥行)を脳内で計算してください。
2. 形状がいびつなゴミが積み重なる場合、隙間（空隙率）が必ず生じます。算出体積には、空隙を考慮して約1.2倍〜1.3倍のバッファを含めてください。
3. 【基準サイズの目安（絶対暗記）】
   - 45Lゴミ袋（満杯）: 約 0.045 m3
   - カラーボックス（3段）: 約 0.1 m3
   - みかん箱サイズの段ボール: 約 0.05〜0.1 m3
   - 一般的な単身用冷蔵庫（150Lクラス）: 約 0.3〜0.5 m3
   - ファミリー用冷蔵庫（400Lクラス）: 約 0.8〜1.0 m3
   - 洗濯機: 約 0.3〜0.5 m3
   - シングルベッド（マットレス）: 約 0.6 m3
   - 軽トラック1台分の満載（荷台高約1m）: 約 2.5 m3
4. 各アイテムの立米を足し上げ、最終的な `total_volume_m3` と辻褄が合うようにしてください。
5. 「軽トラ何台分か？」を基準に最終チェックを行い、現実離れした数値（例: ゴミ袋3つで2m3など）は補正してください。

【出力JSON仕様】
{
  "total_volume_m3": 2.5,  // 全体の推定立米 (少数第1位まで)
  "items": [
    {"category": "ダンボール", "quantity": 10, "volume_total_m3": 0.5},
    {"category": "冷蔵庫(大)", "quantity": 1, "volume_total_m3": 0.8}
  ],
  "special_disposal": {
    "recycle_items": ["冷蔵庫", "テレビ"],
    "hard_disposal_items": ["金庫", "消火器"],
    "dangerous_items": ["スプレー缶"]
  },
  "warnings": [
    "画像が暗くて見えにくい部分があります",
    "背後に隠れている荷物がある可能性があります"
  ]
}

【JSONに関する厳格な注意事項】
- マークダウン(```json 等)を使用しないでください。パース可能な「生のJSONテキスト」のみを出力してください。
- フォーマットは絶対に崩さないでください。
"""

@router.post("")
async def estimate_volume(
    env_stairs: str = Form("none"),
    env_far_parking: str = Form("false"),
    manual_items: str = Form("[]"),
    images: list[UploadFile] = File(...),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    # 1. サーバー設定情報を取得
    settings = db.query(models.CompanySettings).filter_by(company_id=current_user.company_id).first()

    # 画像をBase64化
    base64_images = []
    for f in images:
        content = await f.read()
        b64 = base64.b64encode(content).decode('utf-8')
        mime_type = f.content_type or "image/jpeg"
        base64_images.append(f"data:{mime_type};base64,{b64}")

    # OpenAIが利用可能か判定
    api_key = os.getenv("OPENAI_API_KEY")
    ai_result = None

    if api_key and api_key.startswith("sk-"):
        # GPT-4o Vision APIリクエスト構築
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        
        user_content = [
            {"type": "text", "text": f"【環境条件】\n階段: {env_stairs}\n横付け不可: {env_far_parking}\n追加特例品目: {manual_items}\nこれらの画像を解析して見積もり結果をJSONで出力してください。"}
        ]
        
        for b64 in base64_images:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": b64}
            })
            
        messages.append({"role": "user", "content": user_content})

        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                response_format={ "type": "json_object" },
                max_tokens=1500,
                temperature=0.2
            )
            ai_content = response.choices[0].message.content
            ai_result = json.loads(ai_content)
        except Exception as e:
            print(f"OpenAI API Error: {e}")
            ai_result = None

    # モックデータフォールバック (APIキーが無い、またはエラー時)
    if not ai_result:
        # モックデータを返す
        total_vol = 1.0 * len(base64_images)
        ai_result = {
            "total_volume_m3": total_vol,
            "items": [
                {"category": "テスト家具", "quantity": 1, "volume_total_m3": 0.5},
                {"category": "雑ゴミ袋", "quantity": 5, "volume_total_m3": 0.5}
            ],
            "special_disposal": {
                "recycle_items": [],
                "hard_disposal_items": [],
                "dangerous_items": []
            },
            "warnings": [
                "【モックデータ】OpenAI APIキーが設定されていないため、仮の見積もり結果を表示しています。"
            ]
        }

    # 4. 新しいJobレコードを作成（status="pending"）
    job = models.Job(
        company_id=current_user.company_id,
        user_id=current_user.id,
        job_name="【AI自動算出】名称未設定",
        total_volume_m3=ai_result.get("total_volume_m3", 0.0),
        status="pending",
        ai_result=json.dumps(ai_result, ensure_ascii=False),
        job_type="other",
        pipeline_stage="estimate"
    )
    # TODO: 必要であればS3などに画像を保存してURLを job.photos に保存するが今回は割愛
    
    db.add(job)
    db.commit()
    db.refresh(job)

    # 5. フロントエンドが期待するフォーマットで返却
    ai_result["job_id"] = job.job_id
    
    return ai_result

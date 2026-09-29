# LINE 連携（無料・応答方式）セットアップ手順

FINORA は **LINE 応答（Reply）方式** のみを使います。応答メッセージは LINE の無料枠（月200通）の
カウント対象外なので、**通数無制限・完全無料** です。こちらから先に送るプッシュ通知は行いません。

## 1. LINE公式アカウントを作る（無料）
1. https://entry.line.biz/start/jp/ にアクセスし、お持ちの LINE アカウントでログイン
2. アカウント名（例：FINORA / PRC Remit）、業種（金融・保険）などを入力して作成
3. 料金プランは **コミュニケーションプラン（月額0円）** のままでOK

## 2. Messaging API を有効化
1. LINE Official Account Manager → 設定 → **Messaging API** → 「Messaging APIを利用する」
2. 開発者情報・プロバイダー名を入力（プロバイダー名は会社名でOK）

## 3. 認証情報を取得（LINE Developers コンソール）
https://developers.line.biz/console/ → 作成したチャネルを開く
- **チャネルシークレット**：「チャネル基本設定」タブ
- **チャネルアクセストークン（長期）**：「Messaging API設定」タブ → 発行
- **ボットのベーシックID**（@から始まる）：「Messaging API設定」タブ

## 4. Webhook を設定
「Messaging API設定」→ Webhook URL に以下を登録し、「Webhookの利用」をON → 検証
```
https://www.finora.co.jp/api/line/webhook
```
また「応答メッセージ」はOFF、「あいさつメッセージ」は任意（ONでも可）にします。

## 5. FINORA 側の環境変数（backend/.env）
```
LINE_CHANNEL_SECRET=（チャネルシークレット）
LINE_CHANNEL_ACCESS_TOKEN=（長期チャネルアクセストークン）
LINE_BOT_BASIC_ID=@xxxxxxx
```
設定後に backend を再起動。

## 6. 利用方法（各ユーザー）
1. FINORA → 設定 → 通知の受け取り → **LINE連携** → 「連携コードを発行」（6桁・有効30分）
2. LINE で公式アカウントを友だち追加し、トークにその6桁を送信 → 連携完了
3. 以後、トークに次のキーワードを送ると最新情報が返信されます
   - `通知` 未読のお知らせ（メール送信しているものと同じ内容の一覧）
   - `請求` 未払いの請求書（番号・金額・支払期限）
   - `契約` 対応が必要な電子契約（確認待ち・署名待ち）
   - `面談` 今後のテレビ電話・面談の予約
   - `資産` 資産評価額（顧客）／スタッフは件数サマリ
   - `ヘルプ` メニュー

## 実装ファイル
- `backend/line_service.py`（署名検証・連携コード・応答生成）
- `frontend/src/components/LineLink.jsx`（設定UI）
- コレクション：`line_link_codes`、`line_events`、`users.line_user_id`

"""Localize API error messages (English source) by the X-Lang request header (ja / en / pt)."""
import re

M = {
    "Not found": ("見つかりません", "Não encontrado"),
    "Forbidden": ("この操作を行う権限がありません", "Acesso negado"),
    "No access to this client": ("この顧客へのアクセス権がありません", "Sem acesso a este cliente"),
    "Invalid status": ("ステータスが正しくありません", "Status inválido"),
    "Invalid email": ("メールアドレスが正しくありません", "E-mail inválido"),
    "Please enter a valid email": ("正しいメールアドレスを入力してください", "Informe um e-mail válido"),
    "Invalid email address": ("メールアドレスが正しくありません", "Endereço de e-mail inválido"),
    "Unknown entity": ("不明なデータ種別です", "Tipo de dado desconhecido"),
    "Password must be at least 8 characters": ("パスワードは8文字以上にしてください", "A senha deve ter pelo menos 8 caracteres"),
    "This email already has a FINORA account": ("このメールアドレスはすでにFINORAに登録されています", "Este e-mail já possui uma conta FINORA"),
    "This email is already registered": ("このメールアドレスはすでに登録されています", "Este e-mail já está cadastrado"),
    "Email already exists": ("このメールアドレスはすでに登録されています", "Este e-mail já existe"),
    "The important-information statement must be confirmed first": ("先に重要事項説明書の確認が必要です", "Primeiro é necessário confirmar o documento de informações importantes"),
    "Session revoked": ("セッションが無効になりました。再度ログインしてください", "Sessão encerrada. Entre novamente"),
    "Invalid authentication code": ("認証コードが正しくありません", "Código de autenticação inválido"),
    "Too many submissions. Please try again later.": ("送信回数が多すぎます。しばらくしてから再度お試しください。", "Muitos envios. Tente novamente mais tarde."),
    "Too many signups. Please try again later.": ("登録回数が多すぎます。しばらくしてから再度お試しください。", "Muitos cadastros. Tente novamente mais tarde."),
    "Too many failed attempts. Try again in 15 minutes.": ("失敗回数が上限に達しました。15分後に再度お試しください。", "Muitas tentativas falharam. Tente novamente em 15 minutos."),
    "Too many attempts. Please log in again later.": ("試行回数が多すぎます。しばらくしてから再度ログインしてください。", "Muitas tentativas. Entre novamente mais tarde."),
    "WhatsApp number is required": ("WhatsApp番号を入力してください", "Informe o número do WhatsApp"),
    "WhatsApp number must include the country code, e.g. +81 90 1234 5678": ("WhatsApp番号は国番号から入力してください（例：+81 90 1234 5678）", "Informe o número do WhatsApp com o código do país, ex.: +55 11 91234-5678"),
    "email, password and valid role are required": ("メールアドレス・パスワード・権限は必須です", "E-mail, senha e perfil válido são obrigatórios"),
    "client_id is required": ("顧客を選択してください", "Selecione um cliente"),
    "Invalid target": ("対象が正しくありません", "Destino inválido"),
    "Invalid role": ("権限が正しくありません", "Perfil inválido"),
    "Invalid payment method": ("支払方法が正しくありません", "Forma de pagamento inválida"),
    "Invalid inquiry type": ("お問い合わせ種別が正しくありません", "Tipo de contato inválido"),
    "Could not parse file": ("ファイルを読み込めませんでした", "Não foi possível ler o arquivo"),
    "Choose a different consultant": ("別のコンサルタントを選択してください", "Escolha outro consultor"),
    "At least one item is required": ("明細を1行以上入力してください", "Informe pelo menos um item"),
    "Amount exceeds outstanding balance": ("金額が未入金額を超えています", "O valor excede o saldo em aberto"),
    "Agreement and a handwritten signature are required": ("同意と手書き署名が必要です", "É necessário concordar e assinar à mão"),
    "Unsupported file type": ("対応していないファイル形式です", "Tipo de arquivo não suportado"),
    "File too large": ("ファイルサイズが大きすぎます", "Arquivo muito grande"),
    "File too large (max 15MB)": ("ファイルサイズが大きすぎます（最大15MB）", "Arquivo muito grande (máx. 15 MB)"),
    "Invitation is no longer valid": ("この招待は無効になっています", "Este convite não é mais válido"),
    "Nothing to transfer": ("送金できる金額がありません", "Não há valor a repassar"),
    "No FINORA fee is due on the current plan": ("現在のプランでは料金は発生しません", "Não há cobrança da FINORA no plano atual"),
    "No payout bank account registered": ("受取口座が未登録です", "Nenhuma conta bancária de repasse cadastrada"),
    "Card payment is not available for this invoice": ("この請求書は現在カード決済をご利用いただけません", "Pagamento com cartão indisponível para esta fatura"),
    "This invoice is not payable": ("この請求書は支払いできない状態です", "Esta fatura não pode ser paga"),
    "This invitation can no longer be resent": ("この招待は再送できません", "Este convite não pode mais ser reenviado"),
    "Signing order: the recipient signs first, then the issuer": ("署名の順番：先に受領者、次に発行者が署名します", "Ordem de assinatura: primeiro o destinatário, depois o emissor"),
    "Payments can only be recorded for issued invoices": ("入金は発行済みの請求書にのみ記録できます", "Pagamentos só podem ser registrados para faturas emitidas"),
    "Only drafts can be edited by the issuer": ("発行者が編集できるのは下書きのみです", "O emissor só pode editar rascunhos"),
    "Only draft invoices can be issued": ("発行できるのは下書きの請求書のみです", "Somente faturas em rascunho podem ser emitidas"),
    "Only draft invoices can be edited": ("編集できるのは下書きの請求書のみです", "Somente faturas em rascunho podem ser editadas"),
    "Only active contracts without an open amendment can be amended": ("変更できるのは、変更手続き中でない有効な契約のみです", "Somente contratos ativos sem alteração em aberto podem ser alterados"),
    "No clients to hand over": ("引き継ぐ顧客がいません", "Não há clientes para transferir"),
    "No card payment to refund": ("返金できるカード決済がありません", "Não há pagamento com cartão para reembolsar"),
    "Invoices with payments cannot be cancelled": ("入金がある請求書は取り消せません", "Faturas com pagamentos não podem ser canceladas"),
    "Document missing or integrity check failed": ("書類が見つからないか、改ざん検知チェックに失敗しました", "Documento ausente ou falha na verificação de integridade"),
    "An open FINORA contract already exists for this tenant": ("この事務所には手続き中のFINORA契約がすでにあります", "Já existe um contrato FINORA em aberto para este escritório"),
    "User not found": ("ユーザーが見つかりません", "Usuário não encontrado"),
    "Transaction not found": ("取引が見つかりません", "Transação não encontrada"),
    "PDF is generated when the contract becomes active": ("PDFは契約が有効になった時点で作成されます", "O PDF é gerado quando o contrato fica ativo"),
    "Invitation not found": ("招待が見つかりません", "Convite não encontrado"),
    "Contract not found": ("契約が見つかりません", "Contrato não encontrado"),
    "Consultant not found": ("コンサルタントが見つかりません", "Consultor não encontrado"),
    "Not available in the demo account": ("デモアカウントではこの操作はできません", "Indisponível na conta de demonstração"),
    "You can only hand over your own clients": ("引き継げるのはご自身の担当顧客のみです", "Você só pode transferir seus próprios clientes"),
    "This FINORA account is suspended. Please contact support.": ("このFINORAアカウントは停止されています。サポートにお問い合わせください。", "Esta conta FINORA está suspensa. Entre em contato com o suporte."),
    "Only the owner can modify this task": ("このタスクを変更できるのは作成者のみです", "Somente o responsável pode alterar esta tarefa"),
    "Only the invoiced customer can pay by card": ("カードで支払えるのは請求先の顧客のみです", "Somente o cliente faturado pode pagar com cartão"),
    "Only the client can upload their own documents": ("書類をアップロードできるのは顧客本人のみです", "Somente o cliente pode enviar seus documentos"),
    "Only the client can mark a correction as fixed": ("修正完了にできるのは顧客本人のみです", "Somente o cliente pode marcar a correção como concluída"),
    "Only clients can create consulting requests": ("相談依頼を作成できるのは顧客のみです", "Somente clientes podem criar solicitações de consultoria"),
    "Available after the FINORA service agreement is executed": ("FINORA利用契約の成立後に利用できます", "Disponível após a assinatura do contrato de serviço FINORA"),
    "The FINORA service agreement has ended": ("FINORA利用契約が終了しています", "O contrato de serviço FINORA foi encerrado"),
    "FINORA platform admin only": ("FINORA運営者のみ利用できます", "Somente para administradores da FINORA"),
    "Contracts are created and changed only through the e-contract flow": ("契約の作成・変更は電子契約の手続きからのみ行えます", "Contratos só podem ser criados e alterados pelo fluxo de contrato eletrônico"),
    "Client-owned data is read-only for staff. Please send a correction request.": ("顧客が登録したデータはスタッフは閲覧のみです。修正依頼を送ってください。", "Dados do cliente são somente leitura para a equipe. Envie uma solicitação de correção."),
    "Client documents cannot be deleted by staff": ("顧客の書類はスタッフが削除できません", "A equipe não pode excluir documentos do cliente"),
    "Token expired": ("ログインの有効期限が切れました。再度ログインしてください", "Sessão expirada. Entre novamente"),
    "Not authenticated": ("ログインしてください", "Faça login"),
    "No refresh token": ("ログインしてください", "Faça login"),
    "Invalid token": ("ログイン情報が無効です。再度ログインしてください", "Sessão inválida. Entre novamente"),
    "Invalid token type": ("ログイン情報が無効です。再度ログインしてください", "Sessão inválida. Entre novamente"),
    "Invalid email or password": ("メールアドレスまたはパスワードが正しくありません", "E-mail ou senha incorretos"),
    "You cannot demote or deactivate yourself": ("ご自身の権限変更・無効化はできません", "Você não pode rebaixar ou desativar a si mesmo"),
    "Invalid signature": ("署名が正しくありません", "Assinatura inválida"),
    "Current password is incorrect": ("現在のパスワードが正しくありません", "Senha atual incorreta"),
    "Method Not Allowed": ("この操作は許可されていません", "Método não permitido"),
    "Invalid ticker": ("銘柄コードが正しくありません", "Código de ativo inválido"),
    "Japanese title is required": ("日本語のタイトルは必須です", "O título em japonês é obrigatório"),
    "Invalid category": ("カテゴリが正しくありません", "Categoria inválida"),
    "Only PNG, JPEG, WebP or GIF images are allowed": ("画像はPNG・JPEG・WebP・GIFのみアップロードできます", "Apenas imagens PNG, JPEG, WebP ou GIF"),
    "File is too large (max 5MB)": ("ファイルが大きすぎます（最大5MB）", "Arquivo muito grande (máx. 5MB)"),
    "Quote not found for this ticker": ("この銘柄コードの価格が見つかりませんでした（例：7203.T、AAPL、PETR4.SA）", "Cotação não encontrada para este código (ex.: 7203.T, AAPL, PETR4.SA)"),
}
P = [
    (re.compile(r"^This step is not allowed in status (\w+)$"), "現在のステータス（{0}）ではこの操作はできません", "Esta etapa não é permitida no status {0}"),
    (re.compile(r"^(\w+) must be numeric$"), "{0} は数値で入力してください", "{0} deve ser numérico"),
    (re.compile(r"^Stripe: (.*)$"), "決済エラー（Stripe）：{0}", "Erro de pagamento (Stripe): {0}"),
]
IDX = {"ja": 0, "pt": 1}
VALIDATION = {"ja": "入力内容を確認してください：{0}", "en": "Please check the input: {0}", "pt": "Verifique os dados informados: {0}"}


def lang_of(request):
    lang = (request.headers.get("x-lang") or "ja").lower()[:2]
    return lang if lang in ("ja", "en", "pt") else "ja"


def tr_error(detail, lang):
    if not isinstance(detail, str) or lang == "en":
        return detail
    i = IDX[lang]
    if detail in M:
        return M[detail][i]
    for rx, ja, pt in P:
        m = rx.match(detail)
        if m:
            return (ja, pt)[i].format(*m.groups())
    return detail

"""Document templates for the two-tier e-contract flow (FINORA_SAAS / CONSULTING) in ja / en / pt."""
LANGS = {"ja": 0, "en": 1, "pt": 2}

DOC_TYPES = {
    "FINORA_SAAS": ("FINORA_IMPORTANT_INFORMATION", "FINORA_SERVICE_AGREEMENT"),
    "CONSULTING": ("CONSULTING_IMPORTANT_INFORMATION", "CONSULTING_AGREEMENT"),
}
DOC_TITLES = {
    "FINORA_IMPORTANT_INFORMATION": ("FINORA重要事項説明書", "FINORA Important Information Statement", "Declaração de Informações Importantes FINORA"),
    "FINORA_SERVICE_AGREEMENT": ("FINORA利用契約書", "FINORA Service Agreement", "Contrato de Serviço FINORA"),
    "CONSULTING_IMPORTANT_INFORMATION": ("コンサルティング重要事項説明書", "Consulting Important Information Statement", "Declaração de Informações Importantes de Consultoria"),
    "CONSULTING_AGREEMENT": ("コンサルティング契約書", "Consulting Agreement", "Contrato de Consultoria"),
}
SECTIONS = {
    "FINORA_IMPORTANT_INFORMATION": "issuer service content features plan fee initial_fee additional_fees payment_method billing_cycle term renewal plan_change cancellation suspension prohibited data_mgmt privacy security data_retention backup ai disclaimer service_change inquiry complaints doc_date doc_version",
    "FINORA_SERVICE_AGREEMENT": "parties service content scope fee payment_method term renewal cancellation account_mgmt tenant_mgmt customer_data privacy confidentiality ip_rights prohibited ai security data_retention suspension termination disclaimer termination_handling e_contract amendment governing_law jurisdiction",
    "CONSULTING_IMPORTANT_INFORMATION": "issuer consultant contact service content fee additional_fees payment_method term renewal cancellation scope exclusions risks privacy disclaimer complaints doc_date doc_version",
    "CONSULTING_AGREEMENT": "parties service scope fee payment_method start_date term renewal cancellation confidentiality privacy disclaimer prohibited amendment e_contract governing_law jurisdiction",
}
T = {
    "issuer": ("事業者名", "Provider", "Prestador"), "consultant": ("担当コンサルタント", "Consultant in charge", "Consultor responsável"),
    "contact": ("連絡先", "Contact", "Contato"), "parties": ("契約当事者", "Parties", "Partes"), "service": ("サービス名称", "Service", "Serviço"),
    "content": ("サービス内容", "Service description", "Descrição do serviço"), "features": ("利用できる機能", "Available features", "Funcionalidades"),
    "plan": ("利用プラン", "Plan", "Plano"), "fee": ("料金", "Fees", "Honorários"), "initial_fee": ("初期費用", "Initial fee", "Taxa inicial"),
    "additional_fees": ("追加費用", "Additional fees", "Custos adicionais"), "payment_method": ("支払方法", "Payment method", "Forma de pagamento"),
    "billing_cycle": ("請求周期", "Billing cycle", "Ciclo de cobrança"), "term": ("契約期間", "Term", "Vigência"), "start_date": ("契約開始日", "Start date", "Data de início"),
    "renewal": ("更新", "Renewal", "Renovação"), "plan_change": ("プラン変更", "Plan changes", "Mudança de plano"),
    "cancellation": ("解約", "Cancellation", "Cancelamento"), "suspension": ("サービス停止", "Suspension", "Suspensão"),
    "scope": ("業務・利用範囲", "Scope", "Escopo"), "exclusions": ("サービス対象外事項", "Exclusions", "Exclusões"),
    "risks": ("リスクに関する説明", "Risk disclosure", "Divulgação de riscos"), "prohibited": ("禁止事項", "Prohibited acts", "Condutas proibidas"),
    "data_mgmt": ("データ管理", "Data management", "Gestão de dados"), "privacy": ("個人情報の取扱い", "Personal information", "Dados pessoais"),
    "security": ("セキュリティ", "Security", "Segurança"), "data_retention": ("データ保存・削除", "Data retention & deletion", "Retenção e exclusão de dados"),
    "backup": ("バックアップ", "Backups", "Backups"), "ai": ("AI機能", "AI features", "Recursos de IA"), "disclaimer": ("免責事項", "Disclaimer", "Isenção de responsabilidade"),
    "service_change": ("サービス変更・停止", "Service changes", "Alterações do serviço"), "inquiry": ("問い合わせ窓口", "Inquiries", "Atendimento"),
    "complaints": ("苦情窓口", "Complaints", "Reclamações"), "confidentiality": ("秘密保持", "Confidentiality", "Confidencialidade"),
    "ip_rights": ("知的財産権", "Intellectual property", "Propriedade intelectual"), "account_mgmt": ("アカウント管理", "Account management", "Gestão de contas"),
    "tenant_mgmt": ("Tenant管理", "Tenant management", "Gestão do tenant"), "customer_data": ("顧客データの取扱い", "Customer data", "Dados de clientes"),
    "termination": ("契約解除", "Termination", "Rescisão"), "termination_handling": ("契約終了時の処理", "Post-termination", "Após o término"),
    "e_contract": ("電子契約", "Electronic contracting", "Contratação eletrônica"), "amendment": ("契約変更", "Amendments", "Alterações contratuais"),
    "governing_law": ("準拠法", "Governing law", "Lei aplicável"), "jurisdiction": ("管轄", "Jurisdiction", "Foro"),
    "doc_date": ("書類作成日", "Document date", "Data do documento"), "doc_version": ("書類バージョン", "Document version", "Versão do documento"),
}
B = {
    "content": ("{service}を提供します。{description}", "{service} will be provided. {description}", "Será prestado o serviço {service}. {description}"),
    "features": ("顧客管理、資産・負債・取引管理、ポートフォリオ分析、シミュレーション、AIインサイト、契約・請求管理、書類管理、監査ログ", "Client management, assets/liabilities/transactions, portfolio analytics, simulation, AI insights, contracts & billing, documents, audit logs", "Gestão de clientes, ativos/passivos/transações, análise de carteira, simulação, insights de IA, contratos e cobrança, documentos, logs de auditoria"),
    "initial_fee": ("なし", "None", "Nenhuma"),
    "additional_fees": ("本書に記載のない費用は発生しません。追加業務は事前に書面で合意します。", "No fees beyond this document. Additional work requires prior written agreement.", "Não há custos além deste documento. Trabalhos adicionais exigem acordo prévio por escrito."),
    "payment_method": ("クレジットカードまたは銀行振込", "Credit card or bank transfer", "Cartão de crédito ou transferência bancária"),
    "renewal": ("{renewal}", "{renewal}", "{renewal}"),
    "plan_change": ("プラン変更は翌請求周期から適用されます。", "Plan changes apply from the next billing cycle.", "Mudanças de plano valem a partir do próximo ciclo."),
    "cancellation": ("いずれの当事者も30日前までの通知により解約できます。解約までの料金は日割りしません。", "Either party may cancel with 30 days' notice. Fees are not prorated.", "Qualquer parte pode cancelar com 30 dias de aviso. Não há rateio de valores."),
    "suspension": ("料金の未払い、規約違反、不正利用がある場合、事前通知のうえサービスを停止することがあります。", "Service may be suspended after notice for non-payment, breach or misuse.", "O serviço pode ser suspenso após aviso por inadimplência, violação ou uso indevido."),
    "scope": ("本契約に定める業務に限ります。", "Limited to the services defined in this agreement.", "Limitado aos serviços definidos neste contrato."),
    "exclusions": ("金融商品の売買代行、税務申告の代理、法律相談、投資成果の保証は含みません。", "Excludes trading on your behalf, tax filing, legal advice and any guarantee of returns.", "Exclui operações em seu nome, declaração de impostos, consultoria jurídica e garantia de retorno."),
    "risks": ("投資には元本割れのリスクがあります。助言・シミュレーションは将来の成果を保証しません。最終判断はお客様ご自身で行ってください。", "Investments carry the risk of loss of principal. Advice and simulations do not guarantee future results. Final decisions are yours.", "Investimentos envolvem risco de perda do principal. Conselhos e simulações não garantem resultados. A decisão final é sua."),
    "prohibited": ("法令違反、第三者の権利侵害、不正アクセス、虚偽情報の登録、アカウントの貸与を禁止します。", "Illegal acts, infringement, unauthorized access, false information and account sharing are prohibited.", "São proibidos atos ilegais, violação de direitos, acesso não autorizado, informações falsas e compartilhamento de conta."),
    "data_mgmt": ("データはTenantごとに分離して管理し、他のTenantからは閲覧できません。", "Data is isolated per tenant and cannot be accessed by other tenants.", "Os dados são isolados por tenant e não podem ser acessados por outros tenants."),
    "privacy": ("個人情報は個人情報保護法に従い、契約目的の範囲内でのみ利用し、適切に管理します。", "Personal information is used only for the purposes of this contract and handled under applicable data protection law.", "Os dados pessoais são usados apenas para os fins deste contrato, conforme a lei de proteção de dados."),
    "security": ("通信の暗号化、機微情報の暗号化保存、アクセス制御、監査ログにより保護します。", "Protected by encrypted transport, encrypted sensitive fields, access control and audit logs.", "Protegido por criptografia, campos sensíveis criptografados, controle de acesso e logs de auditoria."),
    "data_retention": ("契約終了後も所定の保存期間中はデータを保持し、その後削除します。契約終了と同時に物理削除はしません。", "Data is retained for the retention period after termination, then deleted; never physically deleted at termination.", "Os dados são mantidos pelo período de retenção após o término e depois excluídos; nunca no ato do término."),
    "backup": ("データは定期的にバックアップします。", "Data is backed up regularly.", "Os dados são copiados regularmente."),
    "ai": ("AI機能の出力は参考情報であり、正確性を保証しません。事実・計算・推測を区別して表示します。", "AI output is reference information without accuracy guarantee; facts, calculations and inferences are labelled.", "As saídas de IA são referência sem garantia de exatidão; fatos, cálculos e inferências são identificados."),
    "disclaimer": ("故意または重過失による場合を除き、間接損害・逸失利益について責任を負いません。", "Except for wilful misconduct or gross negligence, no liability for indirect damages or lost profits.", "Salvo dolo ou culpa grave, não há responsabilidade por danos indiretos ou lucros cessantes."),
    "service_change": ("重要な変更は事前に通知し、必要に応じて重要事項説明書を再発行します。", "Material changes are notified in advance and the statement is reissued when required.", "Mudanças relevantes são avisadas e a declaração é reemitida quando necessário."),
    "inquiry": ("{issuer_contact}", "{issuer_contact}", "{issuer_contact}"),
    "complaints": ("{issuer_contact}", "{issuer_contact}", "{issuer_contact}"),
    "confidentiality": ("契約上知り得た相手方の秘密情報を、契約終了後も第三者に開示しません。", "Neither party will disclose the other's confidential information, including after termination.", "Nenhuma parte divulgará informações confidenciais da outra, inclusive após o término."),
    "ip_rights": ("FINORAに関する知的財産権は運営者に帰属します。顧客データの権利は利用者に帰属します。", "IP in FINORA belongs to the operator; rights in customer data belong to the user.", "A PI do FINORA pertence ao operador; os direitos sobre dados de clientes pertencem ao usuário."),
    "account_mgmt": ("利用者はアカウントと認証情報を自己の責任で管理します。", "The user manages accounts and credentials under its own responsibility.", "O usuário gerencia contas e credenciais sob sua responsabilidade."),
    "tenant_mgmt": ("利用者は自己のTenant内のスタッフ・顧客の権限を管理します。", "The user manages staff and client permissions within its tenant.", "O usuário gerencia permissões de equipe e clientes em seu tenant."),
    "customer_data": ("利用者は顧客から適法に同意を得てデータを登録し、運営者は委託の範囲内でのみ取り扱います。", "The user registers customer data with lawful consent; the operator processes it only as a processor.", "O usuário registra dados com consentimento legal; o operador os trata apenas como processador."),
    "termination": ("重大な契約違反があり、催告後も是正されない場合、契約を解除できます。", "Either party may terminate for material breach not cured after notice.", "Qualquer parte pode rescindir por violação grave não sanada após aviso."),
    "termination_handling": ("契約終了時のログイン、顧客アクセス、データ閲覧・エクスポート、保存期間は運営者が定める終了条件に従います。", "Login, client access, data viewing/export and retention after termination follow the operator's termination terms.", "Login, acesso de clientes, visualização/exportação e retenção após o término seguem os termos do operador."),
    "e_contract": ("本契約は電子署名により締結し、署名日時・IPアドレス・書類の改ざん検知情報を記録します。", "This contract is executed by electronic signature; signing time, IP address and tamper-evidence hash are recorded.", "Este contrato é firmado por assinatura eletrônica; data, IP e hash de integridade são registrados."),
    "amendment": ("変更は新しい版の書類を作成し、双方の確認・署名によってのみ有効となります。旧版は履歴として保存します。", "Amendments require a new document version confirmed and signed by both parties; prior versions are kept.", "Alterações exigem nova versão confirmada e assinada por ambas as partes; versões anteriores são mantidas."),
    "governing_law": ("日本法", "Laws of Japan", "Leis do Japão"),
    "jurisdiction": ("東京地方裁判所を第一審の専属的合意管轄裁判所とします。", "Tokyo District Court has exclusive jurisdiction in the first instance.", "Foro exclusivo do Tribunal Distrital de Tóquio em primeira instância."),
}
CYCLE = {"MONTHLY": ("毎月", "monthly", "mensal"), "YEARLY": ("毎年", "yearly", "anual"), "ONE_TIME": ("一括", "one-time", "único"), "HOURLY": ("時間単位", "hourly", "por hora")}


def _t(d, lang):
    return d[LANGS.get(lang, 0)]


def build_sections(doc_type, lang, ctx, overrides=None):
    """Returns [{key, title, body}] merging data-driven values, boilerplate and issuer overrides."""
    i = LANGS.get(lang, 0)
    fee = ctx["fee_text"]
    data = {
        "issuer": ctx["issuer_block"], "consultant": ctx.get("consultant_name") or "-", "contact": ctx["issuer_contact"],
        "parties": ("甲：{a}\n乙：{b}", "Party A: {a}\nParty B: {b}", "Parte A: {a}\nParte B: {b}")[i].format(a=ctx["issuer_name"], b=ctx["recipient_name"]),
        "service": ctx["service"], "plan": ctx.get("plan") or "-", "fee": fee, "billing_cycle": _t(CYCLE.get(ctx.get("cycle"), CYCLE["MONTHLY"]), lang),
        "term": ctx["term_text"], "start_date": ctx.get("start_date") or "-", "doc_date": ctx["doc_date"], "doc_version": ctx["doc_version"],
    }
    out = []
    for k in SECTIONS[doc_type].split():
        body = (overrides or {}).get(k) or data.get(k) or _t(B.get(k, ("-", "-", "-")), lang).format(**ctx)
        out.append({"key": k, "title": _t(T[k], lang), "body": body})
    return out


def doc_title(doc_type, lang):
    return _t(DOC_TITLES[doc_type], lang)

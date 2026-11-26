# 放課後ボード

高校生向け掲示板の学校課題用MVPです。Flask / Jinja2によるSSR、Tailwind CSS v4、Vanilla JavaScriptを使用し、投稿とコメントをAzure Table Storage、画像を非公開Blob Storageに保存します。

- 実証環境: https://afterschool-board-ankyo.azurewebsites.net/
- 仕様: [requirements.md](requirements.md)、[design.md](design.md)、[AGENTS.md](AGENTS.md)
- 一般向けの利用者募集は行いません。通報・モデレーション・ユーザー認証は今回の範囲外です。

## ローカル起動

Python 3.12、uv、Node.js 24 LTS、npmを用意します。

```sh
uv sync --frozen
npm ci
npm run build:css
```

`.env.example`を`.env`にコピーし、`SECRET_KEY`をランダムな値に変更してください。ローカルHTTPでは`COOKIE_SECURE=false`を指定します。

ローカルStorageにはAzuriteを使用できます（例: `npx azurite --location .cache/azurite`）。Azurite公式の開発用接続文字列を`.env`の`AZURE_STORAGE_CONNECTION_STRING`に設定し、以下でテーブルと非公開コンテナを初期化します。実際のAzureの接続文字列やキーをファイルにコミットしないでください。

```sh
uv run python scripts/init_local_storage.py
uv run flask --app app run
```

Azureに直接接続する開発環境では`AZURE_STORAGE_ACCOUNT_NAME`とAzure CLI認証を使い、対象StorageだけへのデータRBACが必要です。Owner権限だけではデータアクセス権限を兼ねません。

## 検証

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
npm ci
npm run build:css
```

pytestはクラウド認証を必要とせず、フォーム制約、CSRF、XSSエスケープ、画像の実体・サイズ・画素数・メタデータ除去、投稿とコメントの関連付け、50件での取得打ち切り、Blob保存失敗とTable保存失敗時の補償削除を検証します。

実環境の受入テストは、明示的に動作確認用の投稿・画像・コメントを1組作成します。データは削除しません。

```sh
uv run python scripts/smoke.py https://afterschool-board-ankyo.azurewebsites.net
# App Serviceを再起動した後、同じ作業ディレクトリで実行
uv run python scripts/smoke.py https://afterschool-board-ankyo.azurewebsites.net --verify-existing
```

## Azure構成

Azure for Studentsサブスクリプションのみを使用し、リージョンはJapan Eastです。

| リソース | 名前・設定 |
|---|---|
| リソースグループ | `rg-afterschool-board` |
| App Service Plan | `asp-afterschool-board` / Linux / Free F1 |
| Web App | `afterschool-board-ankyo` / Python 3.12 / HTTPS Only |
| Storage | `stafterschoolankyo` / StorageV2 / Standard_LRS / TLS 1.2以上 |
| Table | `Posts`, `Comments` |
| Blob Container | `images` / 非公開 |
| CI/CD用マネージドID | `id-afterschool-github` |

Web Appのシステム割り当てマネージドIDには、上記Storageに限定して`Storage Table Data Contributor`と`Storage Blob Data Contributor`を割り当てています。共有キー認証とBlob匿名公開は無効です。画像はFlask経由で配信します。

App Serviceのアプリ設定:

- `SECRET_KEY`: 暗号学的乱数で生成し、アプリ設定だけに保存。再起動時に変更しません。
- `AZURE_STORAGE_ACCOUNT_NAME=stafterschoolankyo`
- `SCM_DO_BUILD_DURING_DEPLOYMENT=true`

起動コマンド:

```text
gunicorn --bind=0.0.0.0:8000 --workers=2 --timeout=120 app:app
```

F1は無料枠で、コールドスタート・CPU・メモリ等の制約があります。Storageは保存容量・操作回数・転送量に応じた従量課金で学生クレジットを消費します。無償とは限りません。実測請求額や残クレジットは未確認です。有料App Serviceプランへの変更は行いません。

## CI/CD

[Test and deploy](.github/workflows/ci-deploy.yml)はPRでRuff、pytest、Tailwindビルドを実行し、mainへのpush時は検証成功後に同じ成果物をデプロイします。並行デプロイは直列化します。

Python依存関係の正は`uv.lock`です。`requirements.txt`は次のコマンドで生成し、コミットしてCIで整合を確認します。

```sh
uv export --frozen --no-dev --no-emit-project --format requirements-txt --output-file requirements.txt
uv run python scripts/package.py
```

`dist/app.zip`はアプリとビルド済みCSS、ロックから生成した`requirements.txt`だけを含みます。Azure OryxのリモートビルドでPython依存関係をインストールします。`.env`、仮想環境、Node.js依存関係、認証情報は含めません。

成果物には`forum/static/release.json`も含み、コミットIDとCSSのSHA-256を記録します。デプロイ後にWeb Appを明示的に再起動し、`scripts/verify_deployment.py`で配信中のリリース情報・CSSが成果物と一致すること、ヘルスチェック・一覧が正常であることを確認します。2026年11月26日に配置成功後も旧アプリが配信される事象があり、Web Appの再起動で最新画面に切り替わることを確認しました。HTTP 200だけでは新版の反映確認にならないため、この照合を行います。

GitHub ActionsのAzure認証はOIDCです。`main`ブランチのトークンのみを信頼し、マネージドIDの権限は対象Web Appの`Website Contributor`に限定しています。GitHubには秘密鍵・Publish Profileを保存しません。Repository Variablesに`AZURE_CLIENT_ID`、`AZURE_TENANT_ID`、`AZURE_SUBSCRIPTION_ID`を設定します。これらのIDは秘密値ではありません。管理者がローカルGit認証を利用して再設定する場合は`uv run python scripts/configure_github.py`を使えます。

OIDCの信頼条件は、ユーザー割り当てマネージドID `id-afterschool-github` のフェデレーション資格情報 `github-main` に設定しています。Entra IDのアプリ登録を編集する必要はありません。修正には、このマネージドIDのフェデレーション資格情報を更新するAzure RBAC権限が必要です。

| 項目 | 設定値 |
|---|---|
| Issuer | `https://token.actions.githubusercontent.com` |
| Audience | `api://AzureADTokenExchange` |
| Subject | `repo:ankyo-gh@206799426/azure-forum@1472783074:ref:refs/heads/main` |

このリポジトリはユーザーIDとリポジトリIDを含む[GitHubのimmutable subject形式](https://docs.github.com/en/actions/reference/security/oidc#immutable-subject-claims)を使用します。従来の `repo:ankyo-gh/azure-forum:ref:refs/heads/main` では `AADSTS700213` になります。ログのsubjectと登録値を完全一致させてください。今回の修正ではIssuer・Audience・Web AppへのRBAC権限は変更していません。

同じ不一致を修正する場合は、`az account show` で対象がAzure for Studentsであることを確認してから、既存の資格情報のSubjectを更新します（[Azure CLIの公式手順](https://learn.microsoft.com/en-us/cli/azure/identity/federated-credential?view=azure-cli-latest#az-identity-federated-credential-update)）。

```sh
az account show
az identity federated-credential update --subscription 2351e4b2-3a33-40db-b6f8-1c4de902bad6 --resource-group rg-afterschool-board --identity-name id-afterschool-github --name github-main --subject 'repo:ankyo-gh@206799426/azure-forum@1472783074:ref:refs/heads/main'
```

更新後、GitHub Actionsの失敗したdeployジョブだけを再実行し、Azure Login、デプロイ、`/health`と一覧の確認が成功することを確認します。権限エラーの場合は対象リソースの管理者へ依頼し、認証方式の変更や権限の拡大で迂回しません。

手動デプロイ（同じリモートビルド方式）:

```sh
az account show
uv run python scripts/package.py
az webapp deploy --resource-group rg-afterschool-board --name afterschool-board-ankyo --src-path dist/app.zip --type zip
```

`/health`はアプリプロセスの生存確認です。Storage接続は一覧・詳細・実投稿で確認します。ストレージ障害は内部情報を含まない503画面で表示します。

## 受入確認状況（2026年11月26日）

- Azure上で一覧・新規投稿・画像配信・コメント・カテゴリ絞り込み・不正入力拒否を確認済みです。
- Web App再起動後、同じ投稿・画像・コメントの取得を確認済みです。
- Chromeの390px幅で一覧・投稿フォーム・詳細に横はみ出しがなく、画像エラー時に入力内容が保持されることを確認しました。1280px幅でも一覧を確認しました。
- ローカルpytest 30件、Ruff、Tailwindビルド、PRのGitHub Actions CIが成功しています。
- main更新によるOIDC自動デプロイ（A-10）は[実行45780315661の再実行](https://github.com/ankyo-gh/azure-forum/actions/runs/45780315661)で確認済みです。Subject不一致を修正後、Azure Login、デプロイ、`/health`と一覧の検証が成功しました。mainへの直接コミットや無断マージは行いません。

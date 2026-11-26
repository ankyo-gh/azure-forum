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

GitHub ActionsのAzure認証はOIDCです。`main`ブランチのトークンのみを信頼し、マネージドIDの権限は対象Web Appの`Website Contributor`に限定しています。GitHubには秘密鍵・Publish Profileを保存しません。Repository Variablesに`AZURE_CLIENT_ID`、`AZURE_TENANT_ID`、`AZURE_SUBSCRIPTION_ID`を設定します。これらのIDは秘密値ではありません。管理者がローカルGit認証を利用して再設定する場合は`uv run python scripts/configure_github.py`を使えます。

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
- main更新によるOIDC自動デプロイ（A-10）はPRマージ後の確認が必要です。mainへの直接コミットや無断マージは行いません。

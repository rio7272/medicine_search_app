# 医薬品情報検索・比較分析システム

製薬企業MRのための自社製品 vs 競合製品の戦略的比較分析システム

## 機能
- 総合比較ダッシュボード
- 価格比較・経済性分析
- AI横断検索
- 戦略レポート生成

## セットアップ

1. 仮想環境の有効化
```bash
source env/bin/activate
```

2. 依存ライブラリのインストール
```bash
pip install -r requirements.txt
```

3. 環境変数の設定
`.env`ファイルにOpenAI APIキーを設定:
```
OPENAI_API_KEY=your_api_key_here
```

4. アプリの起動
```bash
streamlit run app.py
```

## 開発者
山口莉央
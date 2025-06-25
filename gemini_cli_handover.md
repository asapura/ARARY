# 割安物件検出システム — Gemini‑CLI 引き継ぎ資料

> **目的**: 不動産仲介サイト掲載物件に対し、路線価ベースの更地評価額と実勢単価を比較し、割安な候補を自動抽出する。
>
> **対象リリース**: PoC（埼玉県全域）→ MVP（全国ハイブリッドキャッシュ）

---

## 1. 概要

|              | 内容                                                             |
| ------------ | -------------------------------------------------------------- |
| **リポジトリ名**   | `ARARY`                                   |
| **主言語 / FW** | Python 3.11, FastAPI, PostGIS 15, QGIS 3.36, Gemini‑CLI v0.5.2 |
| **ドキュメント**   | `/docs` ディレクトリ（本ファイルを含む）                                       |
| **想定インフラ**   | GCP (GCE + Cloud SQL) or on‑prem Linux (16 GB RAM)             |
| **ビルド/CI**   | GitHub Actions (pytest → flake8 → Docker build)                |
| **デプロイ**     | Docker Compose もしくは Cloud Run                                  |

---

## 2. ディレクトリ構成

```text
.
├── api/              # FastAPI サービス
│   ├── main.py       # /landvalue エンドポイント
│   ├── deps.py       # DB 依存注入
│   └── model.pkl     # RandomForest モデル
├── data/
│   ├── raw/          # 国税庁 PDF 原本
│   ├── tiff/         # 300 dpi 変換済み
│   └── tiles/        # 500 m メッシュ切り出し
├── extractors/       # OCR 実装（Strategy パターン）
│   ├── base.py       # BaseExtractor
│   ├── classic_ocr.py
│   ├── gemini_vision.py
│   └── claude_vision.py
├── pipeline/
│   ├── georef.py     # gcp → gdalwarp
│   ├── mesh_join.py  # shapefile join
│   └── cache.py      # Redis ↔ PostGIS
├── cli/
│   └── ingest.sh     # gemini run 用 Bash
├── docs/
│   ├── architecture.drawio
│   └── handoff_gemini.md  # ← 本書
└── Makefile
```

---

## 3. システムアーキテクチャ

```
┌──────────┐   crawl    ┌────────────┐   convert   ┌───────────┐
│ 国税庁PDF │──────────▶│ data/raw   │───────────▶│ data/tiff │
└──────────┘            └────────────┘             └───────────┘
                                      georef (gdalwarp)
                                                  ▼
                                            ┌───────────┐  slice  ┌───────────┐
                                            │ data/tiles│◀────────│ pipeline  │
                                            └───────────┘         └───────────┘
OCR (Gemini / Classic)                                    │
              ▼                                           │ insert
         ┌────────┐                                       ▼
         │ Redis  │  read‑through  ┌───────────┐   ST_Join   ┌──────────┐
         └────────┘◀──────────────▶│  PostGIS  │────────────▶│  API     │
                                    └───────────┘            └──────────┘
```

* **Strategy パターン**採用: `extractors/` 配下で OCR 手法を交換可能。
* **キャッシュ**: Redis TTL = 365 days、初回アクセスのみ OCR → PostGIS へ永続化。

---

## 4. セットアップ手順

```bash
# 1) Conda 環境
conda env create -f environment.yml
conda activate rosenka

# 2) 初回データ取得 (埼玉県, 令和6年)
make crawl YEAR=2024 PREF="saitama"
make convert
make georef
make ocr PREF="saitama" YEAR=2024 EXTRACTOR=gemini

# 3) API 起動
make api
# -> http://localhost:8000/docs で Swagger UI
```

### .env (抜粋)

```dotenv
POSTGRES_URL=postgresql://user:pass@localhost/rosenka
REDIS_URL=redis://localhost:6379/0
VISION_GEMINI_API_KEY=xxxxx
VISION_CLAUDE_API_KEY=xxxxx
```

---

## 5. コアモジュール解説

### 5.1 `extractors/base.py`

```python
class BaseExtractor(ABC):
    """図幅画像から price_dict を返すインタフェース"""
    @abstractmethod
    def extract(self, img: np.ndarray) -> list[dict]:
        """Return [{"value": 310, "ratio": "C", "x": 1234, "y": 567}]"""
```

* **classic\_ocr.py** : Tesseract + regex（高速・低コスト）
* **gemini\_vision.py** : 256 crop/batch で Gemini 1.5 Vision (高精度)
* **claude\_vision.py** : バックアップ用

`settings.yml` で県別優先順位を定義 → `extractor_factory()` が決定。

### 5.2 `pipeline/georef.py`

* `gdal_translate -gcp` で 4 GCP 設定
* `gdalwarp -t_srs EPSG:6668 -r bilinear` でアフィン変換
* 初年度のみ手動、以降は座標行列を JSON キャッシュ。

### 5.3 `pipeline/mesh_join.py`

* 総務省 e‑Stat 4 次メッシュ (500 m) を `mesh_500m` テーブルへロード
* `ST_Intersection` で平均路線価をメッシュ単位に集約

---

## 6. API 仕様

```http
POST /v1/landvalue
{
  "postcode": "351-0025",
  "lot_area_sqm": 120,
  "shape": "長方形"
}
→ 200 OK
{
  "rosenka": 310000,
  "depth_rate": 0.95,
  "undeveloped_value": 35300000,
  "source": "cache>postgis",
  "conf": 0.97
}
```

---

## 6.5 ローカル精度検証テスト（Pre‑Flight）

| テスト      | 目的             | 合格基準                                                                                 | ツール/手順                                                                     |
| -------- | -------------- | ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------- |
| **テスト1** | 図幅ジオリファレンス精度確認 | QGIS で国土地理院タイルと重ね、主要交差点 5 点で **ズレ ≤ 1 px**。スクリーンショットを `tests/local/screenshots/` へ格納 | 1) `make georef` 2) QGIS `QuickMapServices` で比較 3) 記録                      |
| **テスト2** | 路線価 OCR 精度確認   | `addr_samples.csv`（20 件）で抽出した路線価が手入力値と比較して **±3 %** 以内、借地権割合誤読ゼロ                     | 1) `make ocr EXTRACTOR=<strategy>` 2) `pytest tests/local/test_reading.py` |

> **ブロッカー規定**: いずれかのテスト未達の場合、クラウド環境構築や PoC フェーズへ進まず、原因分析・是正を行うこと。

---

## 7. 埼玉 PoC 検証フロー

| Step | ツール                          | 成功基準                    |
| ---- | ---------------------------- | ----------------------- |
| 1    | `make georef`                | GCP 残差 ≤ 1 px           |
| 2    | `make ocr EXTRACTOR=classic` | σ≤3% 誤差 85%↑            |
| 3    | `make ocr EXTRACTOR=gemini`  | σ≤3% 誤差 97%↑            |
| 4    | `/tests/e2e/test_api.py`     | 応答 < 5 s, 2 回目 < 100 ms |

---

## 8. 年度更新手順（7/1 00:30 JST 自動）

1. GitHub Actions で `make crawl YEAR=$(date +%Y)`
2. 新旧 PDF 差分を Slack 通知 (`docs/slack_webhook.py`)
3. `make convert && make georef && make ocr`
4. モデル再学習 `make retrain` → A/B テスト

---

## 9. コスト試算 & チューニング

| 項目               | 単価              | 月間件数(見込) | コスト       |
| ---------------- | --------------- | -------- | --------- |
| Gemini Vision    | \$0.002 / image | 50k crop | **\$100** |
| Claude Vision    | \$0.005 / image | 10k crop | \$50      |
| Tesseract        | –               | 無制限      | 無料        |
| GCE n2‑highmem‑4 | \$0.270/hr      | 常時       | \$194     |

* **Gemini 精度 97%** → Classic OCR (無料) との差分 12% を埋めるコストとして妥当かを経営判断。

---

## 10. 既知の課題 & Backlog

*

---

## 11. 参考リンク

* 国税庁 路線価図: [https://www.rosenka.nta.go.jp/](https://www.rosenka.nta.go.jp/)
* e‑Stat メッシュデータ: [https://www.e-stat.go.jp/gis](https://www.e-stat.go.jp/gis)
* ClovaAI Donut: [https://github.com/clovaai/donut](https://github.com/clovaai/donut)

---

## 12. コントリビュート規約

1. `feat/<ticket#>-<short-desc>` ブランチ運用
2. PR テンプレ — 課題 / 対応方針 / 動作確認 / スクショ提出
3. `pre-commit` で black + isort + flake8 強制

---

### 付録 A. Gemini‑CLI 例

```bash
# OCR 256 crop を比較
!python extractors/gemini_vision.py --img path/to/saitama_40210_2024.tiff --batch 256

# ドキュメント要約
!open docs/handoff_gemini.md
!todo next "実装時に不明点が出たら記録する"
```

> **以上** — 本ドキュメントを `docs/handoff_gemini.md` にコミットし、Gemini‑CLI の `!open` で閲覧可能にしてください。

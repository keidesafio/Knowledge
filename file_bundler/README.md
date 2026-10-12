# ローカルファイルの3ファイル・バンドル化

## 最初に

このツールは、フォルダ内の通常ファイルを再帰的に集め、次の3ファイルを作ります。

- originals.zip：元ファイルのバイト列を保存。SHA-256で復元一致を検証。
- content.json：抽出した内容、OfficeのXML構造、出典、PDFページ対応、警告。
- visuals.pdf：文書・画像の表示、Excelの全体図と分割詳細、Excelセル全文の補助表示。

**保証するのは、収集した原本のバイト列の一致です。あらゆる形式の意味情報をAIが完全に理解できること、元アプリと完全一致する表示は保証しません。** ZIPを読めないAIにJSONとPDFだけ渡す場合、未抽出情報はAIには届きません。ファイル数が3でも容量やページ数は大きくなります。

## 必要なもの

1. Python 3.10以上（https://www.python.org/downloads/）
2. LibreOffice（https://www.libreoffice.org/download/download-libreoffice/）
3. 同梱requirements.txtのPythonパッケージ

Office系ファイルの見た目の変換にはLibreOfficeが必要です。Microsoft Officeだけではこのスクリプトの変換エンジンにはなりません。初回のインストールはインターネットが必要ですが、このスクリプト自体はファイルを外部サービスに送信しません。

## Windows：PowerShellで実行

このZIPを解凍し、bundle_files.pyがあるフォルダをエクスプローラーで開き、アドレス欄に powershell と入力してEnter。

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe bundle_files.py "C:\Users\YOUR_NAME\Documents\入力資料" --out "C:\Users\YOUR_NAME\Documents\bundle_output"
```

YOUR_NAMEとフォルダ名を実際のパスに置き換えてください。入力フォルダと出力フォルダは別にします。出力フォルダは**まだ存在しない名前**にしてください。既存フォルダは上書きしません。

LibreOfficeが見つからない場合：

```powershell
.\.venv\Scripts\python.exe bundle_files.py "C:\資料" --out "C:\bundle_output" --soffice "C:\Program Files\LibreOffice\program\soffice.exe"
```

## macOS / Linux

LibreOfficeとPythonを先にインストールし、解凍フォルダをターミナルで開きます。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python bundle_files.py "/path/to/input" --out "/path/to/bundle_output"
```

LinuxのLibreOfficeパスもPATHから検出します。未検出なら --soffice /path/to/soffice を追加してください。

## Excelの見切れへの対処

1. LibreOfficeのSinglePageSheetsで、印刷範囲を無視して非表示シートも含む全体ページを出力。
2. 大きなページを元の大きさのまま約A4相当の範囲に分割。24ポイント重ねて境界を補う。
3. XLSX/XLSMは、各シートの全ての保存済みセルについて値と数式をJSONに抽出。
4. 値と数式をPDFにも折り返して掲載。長文は次のページへ継続し、途中で切り捨てない。
5. 埋め込まれた対応画像も個別に掲載。

分割は画像の画素分割ではなくPDFの座標分割です。表を小さく縮めて1枚に収める方法ではありません。シート全体のページも残します。JSONのvisuals[].tiles[].clip_pointsで元ページの座標を追えます。セル全文のページはsheets[].ledger_pdf_pagesに記録します。

**制限**：分割位置はセルや図形の境界とは一致せず、見出し行・識別列の繰り返しは未実装です。セル内部の元からの見切れや非表示行列は図上に残る場合がありますが、XLSX/XLSMの保存済みセル値は補助表示で確認できます。数式の共有・配列式はXML上の式と属性を保持し、セルごとの式展開はしません。表示書式適用前の値とスタイル参照を保存するため、15%が0.15として出ることがあります。表示文字列は変換PDF側も参照してください。Excelの自動再計算で表示結果が保存済み値と変わる場合があります。

## 対応範囲

| 形式 | 処理 |
|---|---|
| XLSX/XLSM | セル値・数式・結合範囲・シート状態、全XML、全体図・分割詳細、セル全文、対応埋込画像 |
| DOCX/DOCM/PPTX/PPTM | 全XML（表、脚注、コメント、ノート、接続等の元構造）、対応埋込画像、LibreOfficeでPDF化 |
| XLS/XLSB/ODS/DOC/ODT/RTF/PPT/ODP | LibreOfficeでPDF化、変換後の文字抽出。ODFはXMLも保持。旧Excelのセル全文抽出は未対応 |
| PDF | 元ページの取り込み、文字・座標・注釈情報。フォームや署名等の完全な状態は原本を参照 |
| PNG/JPEG/TIFF/BMP/GIF/WebP | 全フレームの静止表示、原画像を縮小再圧縮せずPDFへ配置。GIFの時間情報は原本を参照 |
| TXT/MD/CSV/TSV/JSON/XML/コード等 | 全文をJSONと折り返しPDFへ。UTF-8、BOM付きUTF-16、CP932を試行 |
| その他 | 原本ZIPに保存しarchive_onlyと明示。CAD・動画・音声・入れ子ZIPなどの意味抽出は未対応 |

SVGはソース全文のみで描画は未対応です。Office内のEMF/WMF等はネイティブ変換側に依存します。Word/PowerPointのXMLは構造を保持しますが、全要素を共通の表・図モデルへ正規化してはいません。注釈、添付、リンク等も原本が最終的な参照先です。

## 実行後の確認

1. content.jsonのarchive_verifiedがtrueであること。
2. partial_count、archive_only_countと各ファイルのwarningsを確認。
3. visuals.pdfで表の端、長文、グラフ、図、日本語フォントの表示を確認。
4. 重要な図は原本と照合。visual_reviewは常にrequired_not_automatically_certifiedです。

終了コード：0＝処理終了（表示の完全性を保証する意味ではありません）、2＝一部変換失敗・未対応あり（3ファイルは生成済み）、1＝全体失敗（最終出力は未公開）、130＝中断。

OfficeファイルがあるのにLibreOfficeがない場合は開始前に止まります。どうしても原本と抽出のみ先に作る場合は --allow-partial を指定してください。PDF欠落を警告に記録します。

## OCR（任意）

初期設定では画像をそのまま保持し、OCRはしません。画像の文字もJSONへ取り出す場合、別途Tesseractと日本語・英語の学習データをインストールして --ocr を追加します。

```powershell
.\.venv\Scripts\python.exe bundle_files.py "C:\資料" --out "C:\bundle_with_ocr" --ocr --ocr-lang jpn+eng
```

PyMuPDFが学習データを見つけられない場合は、TESSDATA_PREFIXを実際のtessdataフォルダに設定します。OCR失敗は警告に残り、画像自体は保持します。OCRは誤認識するため原文扱いしません。

## 容量・動作上の注意

- 処理中は原本を編集しないでください。読み取り中の変更を検出した場合は停止します。
- 保存先は元資料＋ZIP＋PDF＋JSONの数倍の空き容量を確保してください。
- PDFとJSONをメモリに保持するため、非常に大量・巨大な資料は十分なメモリが必要です。容量不足で停止した場合、入力を分割して実行するか処理の設計変更が必要です。
- LibreOffice変換は1ファイル300秒まで。大きい資料には --timeout 1200 などを指定できます。
- 外部参照先・クラウド上だけのファイルは別途ローカルに用意してください。
- シンボリックリンクや検出可能なジャンクションは拒否します。実体を別フォルダにコピーしてから実行してください。
- ファイルの内容と相対パスを保存します。ACL、NTFS代替データストリーム、全OS属性まで保存するバックアップツールではありません。
- マクロは実行せず、変換用LibreOfficeプロファイルは最高のマクロセキュリティを設定します。外部リンクの自動更新はCalc設定で無効化します。任意の外部参照形式について完全なネットワーク遮断を保証するものではありません。
- 補助PDFの日本語はCIDフォントを利用します。特殊文字・絵文字の表示はPDFビューアに依存します。元のUnicode文字はJSONに残ります。
- Office変換はLibreOfficeなのでMicrosoft Officeとの差異があり、すべての図の意味・レイアウトの完全性は自動証明できません。

## 参照した公式仕様

- LibreOffice PDF CLI / SinglePageSheets: https://help.libreoffice.org/latest/en-US/text/shared/guide/pdf_params.html
- PyMuPDF OCR: https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html

## このディレクトリにまとめた記録

- [会話・要件・設計・実装範囲・検証結果](docs/conversation_and_design.md)
- [当初の配布用ZIP](dist/file_bundler.zip)（README_JA.mdを同梱）
- [自作サンプル入力](examples/input/) / [生成した3ファイル](examples/output/)
- [長文セルの表示確認画像](examples/ledger_preview.png)

### 検証の再実行

file_bundlerディレクトリをカレントディレクトリにして、依存パッケージとLibreOfficeを用意して実行します。

```bash
python tests/create_fixtures.py
python bundle_files.py tests/input --out tests/result
python tests/verify_result.py tests/result
```

2番目のコマンドは意図的に含めた未対応バイナリにより終了コード2になります。3ファイルは生成されるため、3番目の検証へ進めます。再実行時はまだ存在しない出力先を指定してください。

保存済みのサンプルを検証するだけなら `python tests/verify_result.py examples/output` を実行します。サンプルは自作データで、ユーザーの実資料ではありません。

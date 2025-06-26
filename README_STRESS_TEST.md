# 🧪 勤務表ストレステストアプリ

## 📖 概要

メインアプリ（schedule_gui_fixed.py）をテストする完全独立したテストアプリです。

### 🎯 特徴
- ✅ **完全独立**: メインアプリに一切の変更なし
- ✅ **自動テスト**: 15パターンのテストケースを自動実行
- ✅ **Excel一括出力**: 結果をExcelファイルで一括ダウンロード
- ✅ **品質保証**: 様々な極限状況での動作確認

## 🚀 使用方法

### 1. アプリの起動

```bash
# プロジェクトディレクトリに移動
cd /path/to/schedule-system-git

# ストレステストアプリを起動
streamlit run stress_test_runner.py
```

### 2. テスト実行手順

1. **年月選択**: テスト対象の年月を選択
2. **テストセット選択**: 
   - 🔰 基本テスト（3パターン）
   - 💪 標準テスト（8パターン）
   - 🚀 完全テスト（15パターン）
3. **実行**: 「🚀 ストレステスト実行」ボタンをクリック
4. **結果確認**: 各テストケースの成功/失敗を確認
5. **Excel ダウンロード**: 成功したテストケースのExcelファイルをダウンロード

## 📊 テストケース一覧

### 🔰 基本テスト
- **normal_3people**: 通常3人パターン
- **normal_5people**: 5人編成テスト  
- **normal_8people**: 8人編成テスト

### 💪 ストレステスト
- **heavy_holidays_start**: 月初休暇集中攻撃
- **heavy_holidays_middle**: 月中連続休暇攻撃
- **golden_week_chaos**: GW期間想定
- **cross_month_nitetu**: 月またぎ二徹パターン
- **minimum_staff**: 最小人員運用

### 🚀 極限テスト
- **impossible_case**: ほぼ不可能ケース
- **emergency_situation**: 緊急事態想定
- **new_employee_flood**: 新人大量参加
- **manager_absence**: 管理職不在
- **location_variety**: 勤務場所多様化

## 📁 ファイル構成

```
schedule-system-git/
├── schedule_gui_fixed.py        # メインアプリ（変更禁止）
├── stress_test_runner.py        # テストアプリ（新規作成）
├── test_scenarios/              # テストデータ
│   ├── basic_tests.json
│   ├── stress_tests.json
│   └── extreme_tests.json
├── test_results/                # 結果出力
│   └── (自動生成されるExcelファイル)
└── README_STRESS_TEST.md        # このファイル
```

## 🔧 技術仕様

### import関係
```python
# メインアプリから必要なクラスのみimport
from schedule_gui_fixed import (
    CompleteScheduleEngine,
    WorkLocationManager, 
    ConfigurationManager,
    ExcelExporter
)
```

### 実行環境
- Python 3.7+
- Streamlit
- その他の依存関係はメインアプリと同一

## 📈 期待される効果

### テストの劇的効率化
- **Before**: 手動で1つずつテストデータ入力（面倒）
- **After**: ワンクリックで15パターン一括テスト（楽）

### 品質保証の自動化
- 🛡️ 様々な極限状況での動作確認
- 📊 客観的な品質データ取得
- 🔍 問題の事前発見・予防

### 継続的改善
- 📈 新機能追加時の回帰テスト
- 🔄 月次の定期品質チェック
- 🎯 システムの限界値把握

## 🎪 設計思想

### 完全分離アーキテクチャ
- 🎯 メインアプリ: 安定性重視
- 🧪 テストアプリ: 自由度重視
- 🔗 両者は緩やかに連携

### 現場感覚の勝利
- 👀 Excel分析は人間（としかずさん）の直感
- 🤖 面倒な作業はAI（自動生成）
- ⚖️ 理想的な分業体制

---

**開発者**: Claude Code for としかずさん  
**作成日**: 2025年6月20日
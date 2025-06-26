# 🚀 Streamlit Cloud デプロイ手順（修正版）

## 修正版への切り替え方法

### 1. Streamlit Cloud 設定変更

既存のデプロイを修正版に変更する場合：

1. [share.streamlit.io](https://share.streamlit.io) にログイン
2. 既存のアプリを選択
3. 「Settings」タブをクリック
4. **Main file path** を変更：
   ```
   schedule_gui.py → schedule_gui_fixed.py
   ```
5. **Advanced settings** で requirements.txt を指定：
   ```
   requirements_fixed.txt
   ```
6. 「Save」をクリック
7. 「Reboot app」でアプリを再起動

### 2. 新規デプロイの場合

#### A. Streamlit Cloud にアクセス
1. [share.streamlit.io](https://share.streamlit.io) にアクセス
2. GitHubアカウントでサインイン

#### B. アプリをデプロイ
1. 「New app」をクリック
2. Repository: `yanamu976/schedule-system`
3. Branch: `main`
4. **Main file path**: `schedule_gui_fixed.py` ← 重要！
5. **Advanced settings**:
   - Requirements file: `requirements_fixed.txt`
6. 「Deploy!」をクリック

## ⚙️ 修正版で使用するファイル

- ✅ `schedule_gui_fixed.py` - **メインアプリケーション（修正版）**
- ✅ `requirements_fixed.txt` - **軽量化された依存関係**
- ✅ `work_locations.json` - 勤務場所設定
- ✅ `CLAUDE.md` - プロジェクト説明

## 🎯 修正版の利点

### 1. 軽量化
```txt
# 従来版 (requirements.txt)
streamlit==1.32.0
ortools==9.10.4067
xlsxwriter==3.2.0
pandas==2.2.1      ← 削除
plotly==5.19.0     ← 削除

# 修正版 (requirements_fixed.txt)
streamlit>=1.32.0
ortools>=9.10.4067
xlsxwriter>=3.2.0
```

### 2. 安定性向上
- ゲーミフィケーション機能削除（200+行削減）
- セッション管理の問題解決
- マルチスレッド問題解決

### 3. 高速化
- 重いライブラリ依存を除去
- シンプルな制約プログラミング
- メモリ使用量削減

## 🔧 デプロイ後の確認事項

### 1. アプリが正常に起動することを確認
- Streamlit Cloud のダッシュボードでデプロイ状況をチェック
- **エラーがないことを確認**（特にplotly/pandas関連）

### 2. 主要機能のテスト
- [ ] 従業員設定（デフォルト: Aさん、Bさん、Cさん、助勤）
- [ ] カレンダー選択（チェックボックス方式）
- [ ] 勤務表生成（30秒以内）
- [ ] Excel ダウンロード（色分け付き）
- [ ] 非番表示（「-」で表示される）
- [ ] 月またぎ制約（前月末勤務設定）

### 3. パフォーマンス確認
- [ ] **生成時間短縮**（従来版より高速）
- [ ] **メモリ使用量削減**（pandas/plotly不使用）
- [ ] Excel出力正常（4シート: 勤務表、統計、月またぎ分析、制約緩和）

## 🎯 期待される結果

修正版デプロイ成功後：
```
https://schedule-system-fixed-YOUR_APP_ID.streamlit.app
```

### 表示例
```
📅 勤務表システム（修正版）
🎉 修正版: シンプル・安定動作版
```

## 🆘 トラブルシューティング

### 修正版特有の解決済み問題

1. **ゲーミフィケーション関連エラー** → ✅ 解決（機能削除）
2. **plotly/pandas import エラー** → ✅ 解決（依存関係削除）
3. **セッション状態エラー** → ✅ 解決（setup_system修正）
4. **マルチスレッドエラー** → ✅ 解決（同期実行）

### 一般的な問題

1. **依存関係エラー**
   ```
   解決法: requirements_fixed.txt を使用
   ```

2. **メモリ不足**
   ```
   修正版は軽量化済み（pandas/plotly削除）
   ```

3. **タイムアウト**
   ```
   修正版は最適化済み（30秒制限）
   ```

## 📊 パフォーマンス比較

| 項目 | 従来版 | 修正版 |
|-----|--------|--------|
| 依存関係 | 5個 | 3個 |
| コード行数 | 3400+ | 1600 |
| 起動時間 | 遅い | 高速 |
| メモリ使用量 | 多い | 少ない |
| 安定性 | 不安定 | 安定 |

---

**更新日**: 2025年6月10日  
**バージョン**: Fixed v1.0  
**推奨**: 新規デプロイは修正版を使用
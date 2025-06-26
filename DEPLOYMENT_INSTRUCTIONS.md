# 🚀 Streamlit Cloud デプロイ手順

## GitHub リポジトリ作成手順

### 1. GitHubでリポジトリを作成
1. [GitHub](https://github.com) にログイン
2. 右上の「+」→「New repository」をクリック
3. Repository name: `schedule-system`
4. Description: `Japanese Shift Scheduling System with OR-Tools`
5. Public に設定
6. 「Create repository」をクリック

### 2. ローカルファイルをプッシュ
現在のファイルは以下にあります：
```
/Users/toshikazu/Desktop/schedule-system-git/
```

以下のコマンドでプッシュしてください：

```bash
cd /Users/toshikazu/Desktop/schedule-system-git
git remote set-url origin https://github.com/YOUR_USERNAME/schedule-system.git
git push -u origin main
```

**YOUR_USERNAME** を実際のGitHubユーザー名に置き換えてください。

### 3. Streamlit Cloud デプロイ

#### A. Streamlit Cloud にアクセス
1. [share.streamlit.io](https://share.streamlit.io) にアクセス
2. GitHubアカウントでサインイン

#### B. アプリをデプロイ
1. 「New app」をクリック
2. Repository: `YOUR_USERNAME/schedule-system`
3. Branch: `main`
4. Main file path: `schedule_gui.py`
5. 「Deploy!」をクリック

## ⚙️ 必要なファイル

現在のリポジトリには以下のファイルが含まれています：

- ✅ `schedule_gui.py` - メインアプリケーション
- ✅ `requirements.txt` - 依存関係
- ✅ `work_locations.json` - 勤務場所設定
- ✅ `shift_config.json` - シフト設定
- ✅ `CLAUDE.md` - プロジェクト説明
- ✅ `README.md` - ドキュメント

## 🔧 デプロイ後の確認事項

### 1. アプリが正常に起動することを確認
- Streamlit Cloud のダッシュボードでデプロイ状況をチェック
- エラーがないことを確認

### 2. 主要機能のテスト
- [ ] 従業員設定
- [ ] カレンダー選択
- [ ] 勤務表生成
- [ ] Excel ダウンロード
- [ ] 非番表示（「-」で表示されることを確認）

### 3. パフォーマンス確認
- [ ] 生成時間が適切（30秒以内）
- [ ] メモリ使用量が適切
- [ ] Excel出力が正常

## 🎯 期待される結果

デプロイ成功後のアプリURL例：
```
https://schedule-system-YOUR_APP_ID.streamlit.app
```

## 🆘 トラブルシューティング

### よくある問題

1. **依存関係エラー**
   - `requirements.txt` の内容を確認
   - OR-Tools のバージョンを確認

2. **メモリ不足**
   - Streamlit Cloud の無料プランの制限内に収める
   - 大きなデータ処理を最適化

3. **タイムアウト**
   - 最適化タイムアウトを調整
   - フォールバック機能を確認

### サポート

問題が発生した場合：
1. Streamlit Cloud のログを確認
2. GitHub Issues で報告
3. 必要に応じてローカルで再テスト

---

**更新日**: 2025年6月7日
**バージョン**: 1.0.0
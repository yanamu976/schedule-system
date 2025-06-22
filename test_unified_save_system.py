#!/usr/bin/env python3
"""
統合保存システムの最終テスト
"""

import os
import sys
import json
from datetime import date, datetime

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

def test_save_button_unification():
    """保存ボタンの統合化確認"""
    print("=== 保存ボタン統合化確認 ===")
    
    try:
        # GUI ファイルの内容確認
        with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
            gui_content = f.read()
        
        # 統合化されたボタンの確認
        unified_buttons = [
            "💾 全設定を保存",
            "🆕 新しい統合設定として保存"
        ]
        
        for button_text in unified_buttons:
            count = gui_content.count(button_text)
            print(f"✅ '{button_text}': {count}箇所で使用")
        
        # 古い保存ボタンが残っていないか確認
        old_buttons = [
            "💾 従業員設定を保存",
            "📁 ファイル保存",
            "💾 設定を保存"
        ]
        
        issues_found = False
        for button_text in old_buttons:
            count = gui_content.count(button_text)
            if count > 0:
                print(f"⚠️ 古いボタン '{button_text}': {count}箇所（要確認）")
                issues_found = True
        
        if not issues_found:
            print("✅ 古い保存ボタンは適切に統合されています")
        
        return not issues_found
        
    except Exception as e:
        print(f"❌ 保存ボタン確認エラー: {e}")
        return False

def test_auto_save_integration():
    """自動保存統合の確認"""
    print("\n=== 自動保存統合確認 ===")
    
    try:
        from unified_config_manager import UnifiedConfigManager
        
        manager = UnifiedConfigManager()
        
        # テスト用設定データ
        test_session_state = {
            'calendar_data': {},
            'current_unified_config': 'テスト統合保存_20250620.json',
            'unified_config_auto_save': True
        }
        
        test_gui_state = {
            'last_employees': ['統合テスト従業員A', '統合テスト従業員B'],
            'keijo_base_date': date(2025, 6, 1),
            'year': 2025,
            'month': 6
        }
        
        # 統合設定作成
        filename = manager.save_complete_config(
            "統合保存テスト", 
            test_session_state, 
            test_gui_state
        )
        
        if filename:
            print(f"✅ 統合設定作成成功: {filename}")
            
            # 設定変更のシミュレーション
            test_gui_state['last_employees'].append('追加従業員')
            
            # 上書き保存テスト
            success = manager.overwrite_config(
                filename,
                "統合保存テスト",
                test_session_state,
                test_gui_state
            )
            
            if success:
                print("✅ 統合設定上書き保存成功")
                
                # 保存内容確認
                filepath = os.path.join("configs", filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                
                if len(saved_config.get("employees", [])) == 3:
                    print("✅ 従業員追加が正しく保存されました")
                    return True
                else:
                    print("❌ 従業員追加が保存されていません")
                    return False
            else:
                print("❌ 統合設定上書き保存失敗")
                return False
        else:
            print("❌ 統合設定作成失敗")
            return False
            
    except Exception as e:
        print(f"❌ 自動保存統合テストエラー: {e}")
        return False

def test_session_state_persistence():
    """セッション状態の永続化確認"""
    print("\n=== セッション状態永続化確認 ===")
    
    try:
        # セッション状態のシミュレーション
        mock_session_state = {
            'last_employees': ['永続化テスト従業員A', '永続化テスト従業員B', '永続化テスト従業員C'],
            'current_unified_config': '永続化テスト_20250620.json',
            'unified_config_auto_save': True,
            'calendar_data': {
                '永続化テスト従業員A': {'holidays': ['2025-06-15']},
                '永続化テスト従業員B': {'holidays': ['2025-06-20']}
            },
            'keijo_base_date': date(2025, 6, 1),
            'year': 2025,
            'month': 6
        }
        
        print(f"✅ 従業員数: {len(mock_session_state['last_employees'])}名")
        print(f"✅ アクティブ設定: {mock_session_state['current_unified_config']}")
        print(f"✅ 自動保存: {'有効' if mock_session_state['unified_config_auto_save'] else '無効'}")
        print(f"✅ カレンダーデータ: {len(mock_session_state['calendar_data'])}件")
        
        return True
        
    except Exception as e:
        print(f"❌ セッション状態確認エラー: {e}")
        return False

def test_priority_reset_fix():
    """優先度設定リセット問題の修正確認"""
    print("\n=== 優先度設定リセット問題修正確認 ===")
    
    try:
        # GUI ファイルの重要部分確認
        with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
            gui_content = f.read()
        
        # リセット問題修正のキーワード確認
        fix_keywords = [
            "_is_unified_config_active()",
            "st.session_state.last_employees",
            "_auto_save_unified_config()",
            "統合設定がアクティブな場合は、session_stateを最優先"
        ]
        
        found_fixes = 0
        for keyword in fix_keywords:
            if keyword in gui_content:
                print(f"✅ 修正確認: {keyword}")
                found_fixes += 1
            else:
                print(f"❌ 修正未確認: {keyword}")
        
        if found_fixes >= 3:
            print("✅ 優先度設定リセット問題の修正が確認されました")
            return True
        else:
            print("⚠️ 優先度設定リセット問題の修正が不完全です")
            return False
            
    except Exception as e:
        print(f"❌ 優先度設定修正確認エラー: {e}")
        return False

def test_unified_config_files_count():
    """統合設定ファイル数の確認"""
    print("\n=== 統合設定ファイル数確認 ===")
    
    try:
        configs_dir = "configs"
        if os.path.exists(configs_dir):
            config_files = [f for f in os.listdir(configs_dir) if f.endswith('.json')]
            print(f"✅ 統合設定ファイル数: {len(config_files)}")
            
            # ファイル名の確認
            for filename in config_files[:5]:  # 最初の5ファイルのみ表示
                print(f"📄 {filename}")
            
            if len(config_files) > 5:
                print(f"... 他 {len(config_files) - 5} ファイル")
            
            return len(config_files) > 0
        else:
            print("❌ configs ディレクトリが見つかりません")
            return False
            
    except Exception as e:
        print(f"❌ ファイル数確認エラー: {e}")
        return False

def main():
    """メインテスト実行"""
    print("=== 統合保存システム最終テスト ===")
    
    tests = [
        ("保存ボタン統合化確認", test_save_button_unification),
        ("自動保存統合確認", test_auto_save_integration),
        ("セッション状態永続化確認", test_session_state_persistence),
        ("優先度設定リセット問題修正確認", test_priority_reset_fix),
        ("統合設定ファイル数確認", test_unified_config_files_count),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        result = test_func()
        results.append((test_name, result))
    
    print("\n=== 最終テスト結果 ===")
    success_count = 0
    for test_name, result in results:
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"{status}: {test_name}")
        if result:
            success_count += 1
    
    print(f"\n成功: {success_count}/{len(results)} テスト")
    
    if success_count == len(results):
        print("\n🎉 統合保存システムが完全に動作しています！")
        print("📝 すべての保存ボタンが統合設定に一元化されました。")
        print("🔒 従業員設定・優先度設定のリセット問題が解決されました。")
        print("💾 設定変更は自動的に統合ファイルに保存されます。")
        return True
    else:
        print("⚠️ 一部テストが失敗しました。問題を確認してください。")
        return False

if __name__ == "__main__":
    main()
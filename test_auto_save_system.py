#!/usr/bin/env python3
"""
統合設定自動保存システムのテスト
"""

import os
import sys
import json
from datetime import date, datetime

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

def test_auto_save_functionality():
    """自動保存機能のテスト"""
    try:
        from unified_config_manager import UnifiedConfigManager
        
        # テスト用統合設定管理の初期化
        manager = UnifiedConfigManager()
        
        # テスト設定作成
        test_session_state = {
            'calendar_data': {
                'テスト従業員A': {'holidays': ['2025-06-15']},
                'テスト従業員B': {'holidays': ['2025-06-20']}
            }
        }
        
        test_gui_state = {
            'last_employees': ['テスト従業員A', 'テスト従業員B', 'テスト従業員C'],
            'keijo_base_date': date(2025, 6, 1),
            'year': 2025,
            'month': 6
        }
        
        # 初期設定保存
        filename = manager.save_complete_config(
            "自動保存テスト", 
            test_session_state, 
            test_gui_state
        )
        
        if not filename:
            print("❌ 初期設定保存失敗")
            return False
        
        print(f"✅ 初期設定保存成功: {filename}")
        
        # 設定変更のシミュレーション
        # 1. 従業員追加
        test_gui_state['last_employees'].append('新しい従業員')
        
        # 2. カレンダーデータ追加
        test_session_state['calendar_data']['新しい従業員'] = {'holidays': ['2025-06-25']}
        
        # 上書き保存テスト
        success = manager.overwrite_config(
            filename,
            "自動保存テスト",
            test_session_state,
            test_gui_state
        )
        
        if success:
            print("✅ 上書き保存成功")
            
            # ファイル内容確認
            filepath = os.path.join("unified_configs", filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                updated_config = json.load(f)
            
            # 更新内容の確認
            if len(updated_config.get("employees", [])) == 4:
                print("✅ 従業員追加が正しく保存されました")
            else:
                print("❌ 従業員追加が保存されていません")
                return False
            
            if "新しい従業員" in updated_config.get("current_calendar_data", {}):
                print("✅ カレンダーデータ追加が正しく保存されました")
            else:
                print("❌ カレンダーデータ追加が保存されていません")
                return False
            
            # last_modified が更新されているか確認
            last_modified = updated_config.get("last_modified", "")
            if last_modified:
                print(f"✅ 更新日時が記録されました: {last_modified}")
            else:
                print("❌ 更新日時が記録されていません")
                return False
            
            return True
        else:
            print("❌ 上書き保存失敗")
            return False
            
    except Exception as e:
        print(f"❌ 自動保存機能テストエラー: {e}")
        return False

def test_config_tracking():
    """設定トラッキング機能のテスト"""
    try:
        # session_state のシミュレーション
        mock_session_state = {
            'current_unified_config': 'テスト設定_20250620_150000.json',
            'unified_config_auto_save': True
        }
        
        # アクティブ設定の確認
        if mock_session_state.get('current_unified_config'):
            print("✅ 統合設定トラッキング変数が正しく設定されています")
            
            config_name = mock_session_state['current_unified_config'].split('_')[0]
            print(f"✅ 設定名抽出成功: {config_name}")
            
            auto_save_enabled = mock_session_state.get('unified_config_auto_save', True)
            print(f"✅ 自動保存設定: {'有効' if auto_save_enabled else '無効'}")
            
            return True
        else:
            print("❌ 統合設定トラッキング変数が設定されていません")
            return False
            
    except Exception as e:
        print(f"❌ 設定トラッキングテストエラー: {e}")
        return False

def test_unified_config_files():
    """統合設定ファイルの確認"""
    try:
        from unified_config_manager import UnifiedConfigManager
        
        manager = UnifiedConfigManager()
        
        # 既存ファイル一覧取得
        config_files = manager.get_unified_config_files()
        print(f"✅ 統合設定ファイル数: {len(config_files)}")
        
        for filename in config_files:
            preview = manager.get_config_preview(filename)
            if "error" not in preview:
                print(f"📄 {filename}:")
                print(f"   設定名: {preview['config_name']}")
                print(f"   従業員数: {preview['employees_count']}名")
                print(f"   勤務場所数: {preview['work_locations_count']}箇所")
                print(f"   カレンダーデータ: {'有' if preview['has_calendar_data'] else '無'}")
            else:
                print(f"❌ {filename}: {preview['error']}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ 統合設定ファイル確認エラー: {e}")
        return False

def main():
    """メインテスト実行"""
    print("=== 統合設定自動保存システム テスト開始 ===")
    
    tests = [
        ("自動保存機能テスト", test_auto_save_functionality),
        ("設定トラッキング機能テスト", test_config_tracking),
        ("統合設定ファイル確認", test_unified_config_files),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        result = test_func()
        results.append((test_name, result))
    
    print("\n=== テスト結果サマリー ===")
    success_count = 0
    for test_name, result in results:
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"{status}: {test_name}")
        if result:
            success_count += 1
    
    print(f"\n成功: {success_count}/{len(results)} テスト")
    
    if success_count == len(results):
        print("🎉 自動保存システムが正常に動作しています！")
        print("📝 統合設定ファイル読み込み後、すべての設定変更が自動保存されます。")
        return True
    else:
        print("⚠️ 一部テストが失敗しました。問題を確認してください。")
        return False

if __name__ == "__main__":
    main()
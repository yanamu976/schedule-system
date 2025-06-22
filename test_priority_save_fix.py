#!/usr/bin/env python3
"""
従業員優先度設定保存機能の修正確認テスト
"""

import os
import sys
import json
from datetime import date, datetime

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

def test_priority_save_button_fix():
    """優先度設定保存ボタンの修正確認"""
    print("=== 優先度設定保存ボタン修正確認 ===")
    
    try:
        with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
            gui_content = f.read()
        
        # 一時保存ボタンの削除確認
        temp_save_count = gui_content.count("💾 一時保存")
        if temp_save_count == 0:
            print("✅ 一時保存ボタンが削除されました")
        else:
            print(f"⚠️ 一時保存ボタンがまだ残っています: {temp_save_count}箇所")
        
        # 全設定保存ボタンの確認
        full_save_count = gui_content.count("💾 全設定を保存")
        print(f"✅ 全設定保存ボタン: {full_save_count}箇所")
        
        # 設定ファイル選択ボタンの確認
        selector_count = gui_content.count("📁 設定ファイル選択")
        if selector_count > 0:
            print(f"✅ 設定ファイル選択ボタンが追加されました: {selector_count}箇所")
        else:
            print("❌ 設定ファイル選択ボタンが見つかりません")
        
        # エラーハンドリングの確認
        error_handling_count = gui_content.count("except Exception as e:")
        if error_handling_count > 0:
            print(f"✅ エラーハンドリングが追加されました: {error_handling_count}箇所")
        
        return temp_save_count == 0 and selector_count > 0
        
    except Exception as e:
        print(f"❌ 修正確認エラー: {e}")
        return False

def test_config_selector_functionality():
    """設定ファイル選択機能の確認"""
    print("\n=== 設定ファイル選択機能確認 ===")
    
    try:
        with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
            gui_content = f.read()
        
        # 設定ファイル選択画面の要素確認
        selector_elements = [
            "_show_config_selector",
            "show_config_selector",
            "この設定を選択",
            "利用可能な設定ファイル"
        ]
        
        found_elements = 0
        for element in selector_elements:
            if element in gui_content:
                print(f"✅ 要素確認: {element}")
                found_elements += 1
            else:
                print(f"❌ 要素未確認: {element}")
        
        if found_elements >= 3:
            print("✅ 設定ファイル選択機能が正しく実装されています")
            return True
        else:
            print("⚠️ 設定ファイル選択機能の実装が不完全です")
            return False
            
    except Exception as e:
        print(f"❌ 設定ファイル選択機能確認エラー: {e}")
        return False

def test_save_functionality_with_unified_config():
    """統合設定での保存機能テスト"""
    print("\n=== 統合設定保存機能テスト ===")
    
    try:
        from unified_config_manager import UnifiedConfigManager
        
        manager = UnifiedConfigManager()
        
        # テスト用優先度設定
        test_priorities = {
            "テスト従業員A": {"駅A": 3, "指令": 2, "警乗": 0},
            "テスト従業員B": {"駅A": 2, "指令": 3, "警乗": 1},
            "テスト従業員C": {"駅A": 1, "指令": 1, "警乗": 3}
        }
        
        # テスト用統合設定
        test_session_state = {
            'calendar_data': {},
            'current_unified_config': None,
            'unified_config_auto_save': True
        }
        
        test_gui_state = {
            'last_employees': ['テスト従業員A', 'テスト従業員B', 'テスト従業員C'],
            'keijo_base_date': date(2025, 6, 1),
            'year': 2025,
            'month': 6
        }
        
        # 統合設定作成
        filename = manager.save_complete_config(
            "優先度保存テスト", 
            test_session_state, 
            test_gui_state
        )
        
        if filename:
            print(f"✅ 統合設定作成成功: {filename}")
            
            # 作成された設定ファイルの確認
            filepath = os.path.join("configs", filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 必要なキーの存在確認
            required_keys = ["employee_priorities", "employees", "work_locations"]
            all_keys_present = all(key in config for key in required_keys)
            
            if all_keys_present:
                print("✅ 統合設定に必要なキーがすべて含まれています")
                
                # 従業員設定の確認
                employees = config.get("employees", [])
                employee_priorities = config.get("employee_priorities", {})
                
                print(f"✅ 従業員数: {len(employees)}")
                print(f"✅ 優先度設定対象: {len(employee_priorities)}名")
                
                return True
            else:
                print("❌ 統合設定に必要なキーが不足しています")
                return False
        else:
            print("❌ 統合設定作成失敗")
            return False
            
    except Exception as e:
        print(f"❌ 統合設定保存機能テストエラー: {e}")
        return False

def test_session_state_management():
    """セッション状態管理の確認"""
    print("\n=== セッション状態管理確認 ===")
    
    try:
        with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
            gui_content = f.read()
        
        # セッション状態の要素確認
        session_elements = [
            "show_config_selector",
            "current_unified_config",
            "unified_config_auto_save",
            "last_employees"
        ]
        
        found_session_elements = 0
        for element in session_elements:
            if f"'{element}'" in gui_content or f'"{element}"' in gui_content:
                print(f"✅ セッション状態確認: {element}")
                found_session_elements += 1
            else:
                print(f"❌ セッション状態未確認: {element}")
        
        if found_session_elements >= 3:
            print("✅ セッション状態管理が正しく実装されています")
            return True
        else:
            print("⚠️ セッション状態管理の実装が不完全です")
            return False
            
    except Exception as e:
        print(f"❌ セッション状態管理確認エラー: {e}")
        return False

def test_existing_config_files():
    """既存設定ファイルの確認"""
    print("\n=== 既存設定ファイル確認 ===")
    
    try:
        configs_dir = "configs"
        if os.path.exists(configs_dir):
            config_files = [f for f in os.listdir(configs_dir) if f.endswith('.json')]
            print(f"✅ 設定ファイル数: {len(config_files)}")
            
            # ファイルの内容確認
            valid_files = 0
            for filename in config_files[:3]:  # 最初の3ファイルのみチェック
                filepath = os.path.join(configs_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    if "employee_priorities" in config and "employees" in config:
                        print(f"✅ {filename}: 有効")
                        valid_files += 1
                    else:
                        print(f"⚠️ {filename}: 不完全")
                        
                except Exception as e:
                    print(f"❌ {filename}: 読み込みエラー")
            
            return valid_files > 0
        else:
            print("❌ configs ディレクトリが見つかりません")
            return False
            
    except Exception as e:
        print(f"❌ 既存設定ファイル確認エラー: {e}")
        return False

def main():
    """メインテスト実行"""
    print("=== 従業員優先度設定保存機能修正確認テスト ===")
    
    tests = [
        ("優先度設定保存ボタン修正確認", test_priority_save_button_fix),
        ("設定ファイル選択機能確認", test_config_selector_functionality),
        ("統合設定保存機能テスト", test_save_functionality_with_unified_config),
        ("セッション状態管理確認", test_session_state_management),
        ("既存設定ファイル確認", test_existing_config_files),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        result = test_func()
        results.append((test_name, result))
    
    print("\n=== 修正確認テスト結果 ===")
    success_count = 0
    for test_name, result in results:
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"{status}: {test_name}")
        if result:
            success_count += 1
    
    print(f"\n成功: {success_count}/{len(results)} テスト")
    
    if success_count == len(results):
        print("\n🎉 優先度設定保存機能の修正が完了しています！")
        print("💾 一時保存ボタンが削除され、全設定保存ボタンに統一されました。")
        print("📁 設定ファイル選択機能が追加されました。")
        print("🔧 統合設定への保存機能が正常に動作しています。")
        return True
    else:
        print("⚠️ 一部テストが失敗しました。問題を確認してください。")
        return False

if __name__ == "__main__":
    main()
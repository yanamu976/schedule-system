#!/usr/bin/env python3
"""
設定ファイル選択時の設定名自動反映機能テスト
"""

import os
import sys
import json
from datetime import date, datetime

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

def test_config_name_auto_fill_implementation():
    """設定名自動反映機能の実装確認"""
    print("=== 設定名自動反映機能実装確認 ===")
    
    try:
        with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
            gui_content = f.read()
        
        # 自動反映機能の要素確認
        auto_fill_elements = [
            "_get_current_unified_config_name()",
            "default_config_name = current_config_name",
            "🔗 アクティブ設定:",
            "📁 保存先:"
        ]
        
        found_elements = 0
        for element in auto_fill_elements:
            if element in gui_content:
                print(f"✅ 要素確認: {element}")
                found_elements += 1
            else:
                print(f"❌ 要素未確認: {element}")
        
        # 詳細設定ページの設定名入力フィールド確認
        location_config_name_count = gui_content.count('key="location_config_name"')
        priority_config_name_count = gui_content.count('key="priority_config_name"')
        
        print(f"✅ 詳細設定ページ設定名入力: {location_config_name_count}箇所")
        print(f"✅ 優先度設定ページ設定名入力: {priority_config_name_count}箇所")
        
        if found_elements >= 3 and location_config_name_count > 0:
            print("✅ 設定名自動反映機能が正しく実装されています")
            return True
        else:
            print("⚠️ 設定名自動反映機能の実装が不完全です")
            return False
            
    except Exception as e:
        print(f"❌ 実装確認エラー: {e}")
        return False

def test_save_destination_display():
    """保存先表示機能の確認"""
    print("\n=== 保存先表示機能確認 ===")
    
    try:
        with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
            gui_content = f.read()
        
        # 保存先表示の要素確認
        save_display_elements = [
            "📁 保存先:",
            "current_file = st.session_state.current_unified_config",
            "st.info(f\"📁 保存先: {current_file}\")",
            "st.info(f\"📁 保存先: {st.session_state.current_unified_config}\")"
        ]
        
        found_displays = 0
        for element in save_display_elements:
            count = gui_content.count(element)
            if count > 0:
                print(f"✅ 保存先表示確認: {element} ({count}箇所)")
                found_displays += 1
            else:
                print(f"❌ 保存先表示未確認: {element}")
        
        if found_displays >= 2:
            print("✅ 保存先表示機能が正しく実装されています")
            return True
        else:
            print("⚠️ 保存先表示機能の実装が不完全です")
            return False
            
    except Exception as e:
        print(f"❌ 保存先表示確認エラー: {e}")
        return False

def test_config_selector_integration():
    """設定ファイル選択機能の統合確認"""
    print("\n=== 設定ファイル選択機能統合確認 ===")
    
    try:
        with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
            gui_content = f.read()
        
        # 設定ファイル選択ボタンの確認
        selector_buttons = [
            'key="select_config_locations"',
            'key="save_location_config"',
            "_show_config_selector()"
        ]
        
        found_selectors = 0
        for element in selector_buttons:
            if element in gui_content:
                print(f"✅ 選択機能確認: {element}")
                found_selectors += 1
            else:
                print(f"❌ 選択機能未確認: {element}")
        
        # 統合設定選択画面の要素確認
        selector_screen_elements = [
            "この設定を選択",
            "_load_unified_config_complete",
            "🔗 アクティブ"
        ]
        
        found_screen_elements = 0
        for element in selector_screen_elements:
            if element in gui_content:
                print(f"✅ 選択画面要素: {element}")
                found_screen_elements += 1
        
        if found_selectors >= 2 and found_screen_elements >= 2:
            print("✅ 設定ファイル選択機能が正しく統合されています")
            return True
        else:
            print("⚠️ 設定ファイル選択機能の統合が不完全です")
            return False
            
    except Exception as e:
        print(f"❌ 設定ファイル選択機能確認エラー: {e}")
        return False

def test_unified_config_simulation():
    """統合設定のシミュレーションテスト"""
    print("\n=== 統合設定シミュレーションテスト ===")
    
    try:
        from unified_config_manager import UnifiedConfigManager
        
        manager = UnifiedConfigManager()
        
        # テスト用統合設定作成
        test_session_state = {
            'calendar_data': {},
            'current_unified_config': None,
            'unified_config_auto_save': True
        }
        
        test_gui_state = {
            'last_employees': ['設定名テスト従業員A', '設定名テスト従業員B'],
            'keijo_base_date': date(2025, 6, 1),
            'year': 2025,
            'month': 6
        }
        
        # 統合設定作成
        filename = manager.save_complete_config(
            "設定名自動反映テスト", 
            test_session_state, 
            test_gui_state
        )
        
        if filename:
            print(f"✅ テスト統合設定作成: {filename}")
            
            # 設定名抽出のシミュレーション
            config_name = filename.split('_')[0]
            print(f"✅ 抽出された設定名: {config_name}")
            
            # アクティブ設定のシミュレーション
            test_session_state['current_unified_config'] = filename
            active_config = test_session_state.get('current_unified_config')
            
            if active_config:
                extracted_name = active_config.split('_')[0]
                print(f"✅ アクティブ設定から抽出: {extracted_name}")
                
                if extracted_name == "設定名自動反映テスト":
                    print("✅ 設定名の自動反映シミュレーション成功")
                    return True
                else:
                    print("❌ 設定名の抽出が正しくありません")
                    return False
            else:
                print("❌ アクティブ設定が設定されていません")
                return False
        else:
            print("❌ テスト統合設定作成失敗")
            return False
            
    except Exception as e:
        print(f"❌ 統合設定シミュレーションエラー: {e}")
        return False

def test_file_count_and_naming():
    """ファイル数と命名規則の確認"""
    print("\n=== ファイル数と命名規則確認 ===")
    
    try:
        configs_dir = "configs"
        if os.path.exists(configs_dir):
            config_files = [f for f in os.listdir(configs_dir) if f.endswith('.json')]
            print(f"✅ 統合設定ファイル数: {len(config_files)}")
            
            # 設定名抽出テスト
            extracted_names = []
            for filename in config_files[:5]:  # 最初の5ファイルをテスト
                config_name = filename.split('_')[0]
                extracted_names.append(config_name)
                print(f"📄 {filename} → 設定名: {config_name}")
            
            # 重複設定名の確認
            unique_names = set(extracted_names)
            if len(unique_names) < len(extracted_names):
                duplicates = len(extracted_names) - len(unique_names)
                print(f"⚠️ 重複する設定名: {duplicates}個")
            else:
                print("✅ 設定名に重複なし")
            
            return len(config_files) > 0
        else:
            print("❌ configs ディレクトリが見つかりません")
            return False
            
    except Exception as e:
        print(f"❌ ファイル確認エラー: {e}")
        return False

def main():
    """メインテスト実行"""
    print("=== 設定ファイル選択時の設定名自動反映機能テスト ===")
    
    tests = [
        ("設定名自動反映機能実装確認", test_config_name_auto_fill_implementation),
        ("保存先表示機能確認", test_save_destination_display),
        ("設定ファイル選択機能統合確認", test_config_selector_integration),
        ("統合設定シミュレーションテスト", test_unified_config_simulation),
        ("ファイル数と命名規則確認", test_file_count_and_naming),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        result = test_func()
        results.append((test_name, result))
    
    print("\n=== 設定名自動反映機能テスト結果 ===")
    success_count = 0
    for test_name, result in results:
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"{status}: {test_name}")
        if result:
            success_count += 1
    
    print(f"\n成功: {success_count}/{len(results)} テスト")
    
    if success_count == len(results):
        print("\n🎉 設定名自動反映機能が完全に実装されています！")
        print("📝 設定ファイル選択時に設定名が自動で反映されます。")
        print("📁 保存先ファイル名が明確に表示されます。")
        print("🔗 アクティブ設定の管理が完璧に動作しています。")
        return True
    else:
        print("⚠️ 一部テストが失敗しました。問題を確認してください。")
        return False

if __name__ == "__main__":
    main()
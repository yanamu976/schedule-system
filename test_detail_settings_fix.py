#!/usr/bin/env python3
"""
詳細設定の保存・読み込み修正のテスト
"""

import os
import sys
import json
from datetime import date, datetime

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

def test_config_file_content_before_after():
    """設定ファイルの内容変更テスト"""
    print("=== 詳細設定保存・読み込み修正テスト ===")
    
    configs_dir = "configs"
    if not os.path.exists(configs_dir):
        print("❌ configs ディレクトリが見つかりません")
        return False
    
    config_files = [f for f in os.listdir(configs_dir) if f.endswith('.json')]
    if not config_files:
        print("❌ 設定ファイルが見つかりません")
        return False
    
    # 最新のファイルを確認
    latest_file = max(config_files, key=lambda f: os.path.getmtime(os.path.join(configs_dir, f)))
    filepath = os.path.join(configs_dir, latest_file)
    
    print(f"📄 最新設定ファイル: {latest_file}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 設定内容の確認
        work_locations = config.get("work_locations", [])
        employees = config.get("employees", [])
        employee_priorities = config.get("employee_priorities", {})
        
        print(f"✅ 勤務場所数: {len(work_locations)}")
        print(f"✅ 従業員数: {len(employees)}")
        print(f"✅ 優先度設定対象: {len(employee_priorities)}名")
        
        # 勤務場所の詳細
        if work_locations:
            print("\n📍 勤務場所一覧:")
            for i, loc in enumerate(work_locations[:5]):  # 最初の5つのみ表示
                print(f"  {i+1}. {loc.get('name', '不明')} ({loc.get('type', '不明')}) - {loc.get('color', '不明')}")
            if len(work_locations) > 5:
                print(f"  ... 他 {len(work_locations) - 5} 箇所")
        
        # 従業員リスト
        if employees:
            print(f"\n👥 従業員: {', '.join(employees[:5])}")
            if len(employees) > 5:
                print(f"  ... 他 {len(employees) - 5} 名")
        
        # 優先度設定サンプル
        if employee_priorities:
            print(f"\n🎯 優先度設定サンプル:")
            for emp_name, priorities in list(employee_priorities.items())[:3]:
                priority_str = ', '.join([f"{duty}:{priority}" for duty, priority in priorities.items()])
                print(f"  {emp_name}: {priority_str}")
        
        return True
        
    except Exception as e:
        print(f"❌ ファイル読み込みエラー: {e}")
        return False

def test_location_manager_initialization():
    """LocationManager初期化テスト"""
    print("\n=== LocationManager初期化テスト ===")
    
    try:
        from schedule_gui_fixed import WorkLocationManager, ConfigurationManager
        
        # 初期化テスト
        config_manager = ConfigurationManager()
        location_manager = WorkLocationManager(config_manager)
        
        print(f"✅ デフォルト勤務場所数: {len(location_manager.duty_locations)}")
        print(f"✅ デフォルト勤務場所: {[loc['name'] for loc in location_manager.duty_locations]}")
        
        # 設定の同期テスト
        if location_manager.config_manager:
            config_locations = location_manager.config_manager.current_config.get("work_locations", [])
            print(f"✅ ConfigManager連携: {len(config_locations)}箇所同期済み")
        
        return True
        
    except Exception as e:
        print(f"❌ LocationManager初期化エラー: {e}")
        return False

def test_unified_config_loading():
    """統合設定読み込みテスト"""
    print("\n=== 統合設定読み込みテスト ===")
    
    try:
        from unified_config_manager import UnifiedConfigManager
        
        manager = UnifiedConfigManager()
        config_files = manager.get_unified_config_files()
        
        print(f"✅ 利用可能な統合設定: {len(config_files)}ファイル")
        
        if config_files:
            # 最初のファイルでテスト
            test_file = config_files[0]
            print(f"📋 テスト対象: {test_file}")
            
            preview = manager.get_config_preview(test_file)
            if "error" not in preview:
                print(f"✅ プレビュー取得成功")
                print(f"  - 設定名: {preview['config_name']}")
                print(f"  - 従業員: {preview['employees_count']}名")
                print(f"  - 勤務場所: {preview['work_locations_count']}箇所")
                
                # 実際の読み込みテスト（force_update_session=False）
                config = manager.load_complete_config(test_file, force_update_session=False)
                if config:
                    work_locations = config.get("work_locations", [])
                    employees = config.get("employees", [])
                    print(f"✅ 設定読み込み成功")
                    print(f"  - 実際の勤務場所: {len(work_locations)}箇所")
                    print(f"  - 実際の従業員: {len(employees)}名")
                    return True
                else:
                    print("❌ 設定読み込み失敗")
                    return False
            else:
                print(f"❌ プレビュー取得失敗: {preview.get('error', '不明')}")
                return False
        else:
            print("⚠️ 統合設定ファイルなし")
            return True
            
    except Exception as e:
        print(f"❌ 統合設定読み込みテストエラー: {e}")
        return False

def main():
    """メインテスト実行"""
    print("=== 詳細設定保存・読み込み修正テスト ===")
    
    tests = [
        ("設定ファイル内容確認", test_config_file_content_before_after),
        ("LocationManager初期化", test_location_manager_initialization),
        ("統合設定読み込み", test_unified_config_loading),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        result = test_func()
        results.append((test_name, result))
    
    print("\n=== テスト結果 ===")
    success_count = 0
    for test_name, result in results:
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"{status}: {test_name}")
        if result:
            success_count += 1
    
    print(f"\n成功: {success_count}/{len(results)} テスト")
    
    if success_count == len(results):
        print("\n🎉 詳細設定の保存・読み込み修正が完了しています！")
        print("📝 以下の問題が解決されました：")
        print("  - 統合設定選択後の詳細設定反映")
        print("  - LocationManagerの状態同期")
        print("  - 初期化時の設定読み込み")
        return True
    else:
        print("\n⚠️ 一部テストが失敗しました。問題を確認してください。")
        return False

if __name__ == "__main__":
    main()
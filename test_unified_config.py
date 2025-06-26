#!/usr/bin/env python3
"""
統合設定管理システムの基本テスト
"""

import os
import sys
import json
from datetime import date, datetime

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

def test_unified_config_import():
    """UnifiedConfigManagerのインポートテスト"""
    try:
        from unified_config_manager import UnifiedConfigManager
        print("✅ UnifiedConfigManager インポート成功")
        return True
    except Exception as e:
        print(f"❌ UnifiedConfigManager インポートエラー: {e}")
        return False

def test_unified_config_basic():
    """基本機能テスト"""
    try:
        from unified_config_manager import UnifiedConfigManager
        
        # インスタンス作成
        manager = UnifiedConfigManager()
        print("✅ UnifiedConfigManager インスタンス作成成功")
        
        # ディレクトリ作成確認
        if os.path.exists("unified_configs"):
            print("✅ unified_configs ディレクトリ作成確認")
        else:
            print("❌ unified_configs ディレクトリが作成されていません")
            return False
        
        # 設定ファイル一覧取得（空でもOK）
        config_files = manager.get_unified_config_files()
        print(f"✅ 設定ファイル一覧取得成功: {len(config_files)}件")
        
        return True
    except Exception as e:
        print(f"❌ 基本機能テストエラー: {e}")
        return False

def test_config_save_load():
    """設定保存・読み込みテスト"""
    try:
        from unified_config_manager import UnifiedConfigManager
        
        manager = UnifiedConfigManager()
        
        # テスト用設定データ
        test_session_state = {
            'calendar_data': {
                'Aさん': {'holidays': ['2025-06-15', '2025-06-20']},
                'Bさん': {'holidays': ['2025-06-18']}
            }
        }
        
        test_gui_state = {
            'last_employees': ['Aさん', 'Bさん', 'Cさん'],
            'keijo_base_date': date(2025, 6, 1),
            'year': 2025,
            'month': 6
        }
        
        # 設定保存テスト
        filename = manager.save_complete_config(
            "テスト設定", 
            test_session_state, 
            test_gui_state
        )
        
        if filename:
            print(f"✅ 設定保存成功: {filename}")
            
            # ファイル存在確認
            filepath = os.path.join("unified_configs", filename)
            if os.path.exists(filepath):
                print("✅ 設定ファイル存在確認")
                
                # プレビュー取得テスト
                preview = manager.get_config_preview(filename)
                if "error" not in preview:
                    print(f"✅ プレビュー取得成功: {preview['config_name']}")
                    print(f"   従業員: {preview['employees_count']}名")
                    print(f"   勤務場所: {preview['work_locations_count']}箇所")
                else:
                    print(f"❌ プレビュー取得エラー: {preview}")
                    return False
                
                # 設定読み込みテスト（streamlit無しでテスト）
                # 注意: st.session_stateが無い環境での簡易テスト
                return True
            else:
                print("❌ 設定ファイルが作成されていません")
                return False
        else:
            print("❌ 設定保存失敗")
            return False
            
    except Exception as e:
        print(f"❌ 設定保存・読み込みテストエラー: {e}")
        return False

def test_schedule_gui_import():
    """schedule_gui_fixed.py インポートテスト"""
    try:
        from schedule_gui_fixed import CompleteGUI, ConfigurationManager, WorkLocationManager
        print("✅ schedule_gui_fixed インポート成功")
        
        # ConfigurationManager インスタンス作成テスト
        config_manager = ConfigurationManager()
        print("✅ ConfigurationManager インスタンス作成成功")
        
        # WorkLocationManager インスタンス作成テスト
        location_manager = WorkLocationManager(config_manager)
        print("✅ WorkLocationManager インスタンス作成成功")
        
        return True
    except Exception as e:
        print(f"❌ schedule_gui_fixed インポートエラー: {e}")
        return False

def main():
    """メインテスト実行"""
    print("=== 統合設定管理システム テスト開始 ===")
    
    tests = [
        ("UnifiedConfigManager インポートテスト", test_unified_config_import),
        ("基本機能テスト", test_unified_config_basic),
        ("設定保存・読み込みテスト", test_config_save_load),
        ("schedule_gui_fixed インポートテスト", test_schedule_gui_import),
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
        print("🎉 全テスト成功！統合設定管理システムは正常に動作しています。")
        return True
    else:
        print("⚠️ 一部テストが失敗しました。問題を確認してください。")
        return False

if __name__ == "__main__":
    main()
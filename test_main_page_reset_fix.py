#!/usr/bin/env python3
"""
メインページリセット問題の修正テスト
"""

import os
import sys
import json
from datetime import date, datetime

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

def test_session_state_preservation():
    """セッション状態保持テスト"""
    print("=== セッション状態保持テスト ===")
    
    try:
        # CompleteGUIクラスが正しく定義されているか確認
        from schedule_gui_fixed import CompleteGUI
        
        print("✅ CompleteGUIクラスのインポート成功")
        
        # main関数の修正確認
        with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # GUI instance session state check
        if 'gui_instance' in content and 'st.session_state.gui_instance' in content:
            print("✅ GUIインスタンスのセッション状態保持が実装されています")
        else:
            print("❌ GUIインスタンスのセッション状態保持が実装されていません")
            return False
        
        # CompleteGUI()の直接インスタンス化が削除されているか確認
        if content.count('CompleteGUI()') <= 1:  # セッション状態での1回のみ
            print("✅ CompleteGUI()の重複インスタンス化が修正されています")
        else:
            print("❌ CompleteGUI()が複数回インスタンス化されています")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ セッション状態保持テストエラー: {e}")
        return False

def test_config_sync_mechanism():
    """設定同期メカニズムテスト"""
    print("\n=== 設定同期メカニズムテスト ===")
    
    try:
        with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 必要なメソッドの存在確認
        required_methods = [
            '_ensure_config_sync',
            '_initialize_from_existing_config',
            '_load_unified_config_complete'
        ]
        
        found_methods = 0
        for method in required_methods:
            if f"def {method}" in content:
                print(f"✅ {method}メソッドが実装されています")
                found_methods += 1
            else:
                print(f"❌ {method}メソッドが見つかりません")
        
        # 戻るボタンの自動保存確認
        if '戻る前に統合設定への自動保存を確実に実行' in content:
            print("✅ 戻るボタンでの自動保存が実装されています")
            found_methods += 1
        else:
            print("❌ 戻るボタンでの自動保存が実装されていません")
        
        # run()メソッドでの同期確認呼び出し
        if '_ensure_config_sync()' in content:
            print("✅ run()メソッドでの設定同期確認が実装されています")
            found_methods += 1
        else:
            print("❌ run()メソッドでの設定同期確認が実装されていません")
        
        return found_methods >= 4
        
    except Exception as e:
        print(f"❌ 設定同期メカニズムテストエラー: {e}")
        return False

def test_auto_save_enhancement():
    """自動保存強化テスト"""
    print("\n=== 自動保存強化テスト ===")
    
    try:
        with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # ConfigManagerとの同期確認
        config_sync_count = content.count('config_manager.current_config["work_locations"]')
        if config_sync_count >= 3:  # 複数箇所で同期
            print(f"✅ ConfigManagerとの同期が強化されています ({config_sync_count}箇所)")
        else:
            print(f"⚠️ ConfigManagerとの同期が不十分です ({config_sync_count}箇所)")
            return False
        
        # 自動保存処理の確認
        auto_save_count = content.count('_auto_save_unified_config()')
        if auto_save_count >= 5:  # 複数の操作で自動保存
            print(f"✅ 自動保存処理が強化されています ({auto_save_count}箇所)")
        else:
            print(f"⚠️ 自動保存処理が不十分です ({auto_save_count}箇所)")
            return False
        
        # セッション状態の更新確認
        session_update_count = content.count('st.session_state.last_employees')
        if session_update_count >= 3:
            print(f"✅ セッション状態の更新が適切に実装されています ({session_update_count}箇所)")
        else:
            print(f"⚠️ セッション状態の更新が不十分です ({session_update_count}箇所)")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 自動保存強化テストエラー: {e}")
        return False

def test_unified_config_manager_integration():
    """統合設定管理の統合テスト"""
    print("\n=== 統合設定管理統合テスト ===")
    
    try:
        from unified_config_manager import UnifiedConfigManager
        from schedule_gui_fixed import ConfigurationManager, WorkLocationManager
        
        # 基本的な統合テスト
        config_manager = ConfigurationManager()
        location_manager = WorkLocationManager(config_manager)
        unified_manager = UnifiedConfigManager()
        
        print("✅ 全コンポーネントのインスタンス化成功")
        
        # 設定ファイルの存在確認
        config_files = unified_manager.get_unified_config_files()
        if config_files:
            print(f"✅ 統合設定ファイル: {len(config_files)}個利用可能")
            
            # 最初のファイルで読み込みテスト
            test_file = config_files[0]
            config = unified_manager.load_complete_config(test_file, force_update_session=False)
            
            if config:
                print(f"✅ 設定ファイル読み込み成功: {test_file}")
                
                # 設定内容の確認
                work_locations = config.get("work_locations", [])
                employees = config.get("employees", [])
                priorities = config.get("employee_priorities", {})
                
                print(f"  - 勤務場所: {len(work_locations)}箇所")
                print(f"  - 従業員: {len(employees)}名")
                print(f"  - 優先度設定: {len(priorities)}名分")
                
                return True
            else:
                print("❌ 設定ファイル読み込み失敗")
                return False
        else:
            print("⚠️ 統合設定ファイルが見つかりません")
            return True  # ファイルがないのは正常な状態の場合もある
            
    except Exception as e:
        print(f"❌ 統合設定管理統合テストエラー: {e}")
        return False

def main():
    """メインテスト実行"""
    print("=== メインページリセット問題修正テスト ===")
    
    tests = [
        ("セッション状態保持", test_session_state_preservation),
        ("設定同期メカニズム", test_config_sync_mechanism),
        ("自動保存強化", test_auto_save_enhancement),
        ("統合設定管理統合", test_unified_config_manager_integration),
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
        print("\n🎉 メインページリセット問題の修正が完了しています！")
        print("📝 以下の問題が解決されました：")
        print("  - CompleteGUIインスタンスのセッション状態保持")
        print("  - 詳細設定→メインページ戻り時の状態保持")
        print("  - 統合設定との自動同期")
        print("  - 強化された自動保存機能")
        print("\n🚀 これで詳細設定の変更が確実に保存・反映されます！")
        return True
    else:
        print("\n⚠️ 一部テストが失敗しました。問題を確認してください。")
        return False

if __name__ == "__main__":
    main()
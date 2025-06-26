#!/usr/bin/env python3
"""
重複解消後の統合設定システム最終テスト
"""

import os
import sys
import json
from datetime import date, datetime

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

def test_directory_structure():
    """ディレクトリ構造の確認"""
    print("=== ディレクトリ構造確認 ===")
    
    # 必要なディレクトリの確認
    required_dirs = ["configs", "backup_configs"]
    
    for dir_name in required_dirs:
        if os.path.exists(dir_name):
            files = [f for f in os.listdir(dir_name) if f.endswith('.json')]
            print(f"✅ {dir_name}/: {len(files)}ファイル")
        else:
            print(f"❌ {dir_name}/: ディレクトリなし")
    
    # 重複チェック
    if not os.path.exists("unified_configs"):
        print("✅ unified_configs/: 削除済み（重複解消）")
    else:
        print("⚠️ unified_configs/: まだ存在（要確認）")
    
    return True

def test_unified_config_manager():
    """統合設定管理の動作確認"""
    print("\n=== 統合設定管理テスト ===")
    
    try:
        from unified_config_manager import UnifiedConfigManager
        
        manager = UnifiedConfigManager()
        print(f"✅ 設定ディレクトリ: {manager.configs_dir}")
        
        # ファイル一覧取得
        config_files = manager.get_unified_config_files()
        print(f"✅ 設定ファイル数: {len(config_files)}")
        
        for filename in config_files[:3]:  # 最初の3ファイルのみ表示
            preview = manager.get_config_preview(filename)
            if "error" not in preview:
                print(f"📄 {filename}: {preview['config_name']}")
            else:
                print(f"❌ {filename}: エラー")
        
        return True
        
    except Exception as e:
        print(f"❌ 統合設定管理テストエラー: {e}")
        return False

def test_config_content_validation():
    """設定ファイル内容の妥当性確認"""
    print("\n=== 設定ファイル内容確認 ===")
    
    configs_dir = "configs"
    if not os.path.exists(configs_dir):
        print("❌ configs ディレクトリが見つかりません")
        return False
    
    config_files = [f for f in os.listdir(configs_dir) if f.endswith('.json')]
    valid_count = 0
    
    for filename in config_files:
        filepath = os.path.join(configs_dir, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 必要なキーの確認
            required_keys = [
                "config_name", "employees", "work_locations", 
                "employee_priorities", "keijo_settings", 
                "current_calendar_data", "system_settings"
            ]
            
            missing_keys = [key for key in required_keys if key not in config]
            
            if not missing_keys:
                print(f"✅ {filename}: 完全")
                valid_count += 1
            else:
                print(f"⚠️ {filename}: 不足キー {missing_keys}")
                
        except Exception as e:
            print(f"❌ {filename}: 読み込みエラー {e}")
    
    print(f"📊 妥当性確認: {valid_count}/{len(config_files)} ファイル正常")
    return valid_count > 0

def test_no_duplication():
    """重複の完全解消確認"""
    print("\n=== 重複解消確認 ===")
    
    # backup_configs の確認
    if os.path.exists("backup_configs"):
        backup_files = [f for f in os.listdir("backup_configs") if f.endswith('.json')]
        print(f"✅ backup_configs/: {len(backup_files)}ファイル（バックアップ）")
    else:
        print("⚠️ backup_configs/: バックアップなし")
    
    # configs の確認（統合設定として）
    if os.path.exists("configs"):
        config_files = [f for f in os.listdir("configs") if f.endswith('.json')]
        print(f"✅ configs/: {len(config_files)}ファイル（統合設定）")
    else:
        print("❌ configs/: メイン設定ディレクトリなし")
    
    # unified_configs の削除確認
    if not os.path.exists("unified_configs"):
        print("✅ unified_configs/: 削除済み（重複解消完了）")
        return True
    else:
        print("⚠️ unified_configs/: まだ存在（重複リスク）")
        return False

def test_import_functionality():
    """インポート機能の動作確認"""
    print("\n=== インポート機能テスト ===")
    
    try:
        # 基本的なインポートテスト
        from unified_config_manager import UnifiedConfigManager
        from schedule_gui_fixed import CompleteGUI
        
        print("✅ UnifiedConfigManager: インポート成功")
        print("✅ CompleteGUI: インポート成功")
        
        # インスタンス作成テスト
        manager = UnifiedConfigManager()
        print("✅ UnifiedConfigManager: インスタンス作成成功")
        
        return True
        
    except Exception as e:
        print(f"❌ インポート機能テストエラー: {e}")
        return False

def main():
    """メインテスト実行"""
    print("=== 重複解消後の統合設定システム最終テスト ===")
    
    tests = [
        ("ディレクトリ構造確認", test_directory_structure),
        ("統合設定管理テスト", test_unified_config_manager),
        ("設定ファイル内容確認", test_config_content_validation),
        ("重複解消確認", test_no_duplication),
        ("インポート機能テスト", test_import_functionality),
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
        print("\n🎉 重複解消完了！統合設定システムが正常動作しています！")
        print("📝 以降は configs/ のみで設定管理を行ってください。")
        print("💾 backup_configs/ に従来設定が保存されています。")
        return True
    else:
        print("\n⚠️ 一部テストが失敗しました。問題を確認してください。")
        return False

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
既存設定ファイルを統合設定ファイルに移行し、重複を解消
"""

import os
import sys
import json
from datetime import datetime, date

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

def migrate_legacy_config_to_unified():
    """従来設定ファイルを統合設定ファイルに移行"""
    try:
        from unified_config_manager import UnifiedConfigManager
        
        manager = UnifiedConfigManager()
        configs_dir = "configs"
        
        if not os.path.exists(configs_dir):
            print("❌ configs/ ディレクトリが見つかりません")
            return False
        
        legacy_files = [f for f in os.listdir(configs_dir) if f.endswith('.json')]
        migrated_count = 0
        
        print(f"📁 従来設定ファイル数: {len(legacy_files)}")
        
        for filename in legacy_files:
            filepath = os.path.join(configs_dir, filename)
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    legacy_config = json.load(f)
                
                # 統合設定形式に変換
                config_name = legacy_config.get("config_name", filename.replace('.json', ''))
                
                # 統合設定を作成
                unified_config = {
                    "config_name": config_name,
                    "created_date": legacy_config.get("created_date", datetime.now().strftime("%Y-%m-%d")),
                    "last_modified": datetime.now().isoformat(),
                    
                    # 従来設定から移行
                    "employees": legacy_config.get("employees", ["Aさん", "Bさん", "Cさん", "助勤"]),
                    "work_locations": legacy_config.get("work_locations", []),
                    "employee_priorities": legacy_config.get("employee_priorities", {}),
                    
                    # 新規項目（デフォルト値）
                    "keijo_settings": {
                        "base_date": date(2025, 6, 1).isoformat(),
                        "enabled": True
                    },
                    "current_calendar_data": {},
                    "annual_leave_remaining": {},
                    "system_settings": {
                        "target_year": 2025,
                        "target_month": 6,
                        "priority_weights": legacy_config.get("priority_weights", {"0": 1000, "1": 10, "2": 5, "3": 0})
                    }
                }
                
                # 統合設定として保存
                unified_filename = f"{config_name}_migrated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                unified_filepath = os.path.join(manager.configs_dir, unified_filename)
                
                with open(unified_filepath, 'w', encoding='utf-8') as f:
                    json.dump(unified_config, f, ensure_ascii=False, indent=2, default=str)
                
                print(f"✅ 移行完了: {filename} → {unified_filename}")
                migrated_count += 1
                
            except Exception as e:
                print(f"❌ {filename} の移行失敗: {e}")
        
        print(f"\n📊 移行結果: {migrated_count}/{len(legacy_files)} ファイル移行完了")
        return migrated_count > 0
        
    except Exception as e:
        print(f"❌ 移行処理エラー: {e}")
        return False

def cleanup_duplicate_files():
    """重複ファイルのクリーンアップ推奨"""
    print("\n🧹 重複解消推奨事項:")
    print("1. 既存 configs/ は backup_configs/ にリネーム")
    print("2. unified_configs/ を configs/ にリネーム") 
    print("3. システムを unified_configs/ 一本化に移行")
    
    # バックアップ推奨
    import shutil
    
    if os.path.exists("configs") and not os.path.exists("backup_configs"):
        try:
            shutil.copytree("configs", "backup_configs")
            print("✅ configs/ を backup_configs/ にバックアップしました")
        except Exception as e:
            print(f"⚠️ バックアップ失敗: {e}")

def analyze_file_conflicts():
    """ファイル競合の分析"""
    print("\n🔍 ファイル競合分析:")
    
    configs_dir = "configs"
    unified_dir = "unified_configs"
    
    if os.path.exists(configs_dir):
        legacy_files = set(f.replace('.json', '') for f in os.listdir(configs_dir) if f.endswith('.json'))
        print(f"📁 従来設定: {len(legacy_files)}ファイル")
    
    if os.path.exists(unified_dir):
        unified_files = set(f.split('_')[0] for f in os.listdir(unified_dir) if f.endswith('.json'))
        print(f"📁 統合設定: {len(unified_files)}ファイル")
        
        # 名前の重複チェック
        if os.path.exists(configs_dir):
            conflicts = legacy_files.intersection(unified_files)
            if conflicts:
                print(f"⚠️ 名前重複: {conflicts}")
            else:
                print("✅ 名前重複なし")

def recommend_unified_approach():
    """統合アプローチの推奨"""
    print("\n💡 推奨解決策:")
    print("1. 【統合設定一本化】unified_configs/ のみ使用")
    print("2. 【GUI簡素化】従来設定選択UI を削除")
    print("3. 【移行支援】既存設定の一括変換機能")
    print("4. 【段階移行】既存ユーザーへの移行ガイド")
    
    print("\n🎯 理想的なファイル構成:")
    print("schedule-system-git/")
    print("├── unified_configs/          ← 統合設定のみ")
    print("├── backup_configs/           ← 従来設定のバックアップ")
    print("└── schedule_gui_fixed.py     ← 統合設定UIのみ")

def main():
    """メイン処理"""
    print("=== 設定ファイル重複解消ツール ===")
    
    # 現状分析
    analyze_file_conflicts()
    
    # 移行処理
    migrate_success = migrate_legacy_config_to_unified()
    
    # クリーンアップ推奨
    cleanup_duplicate_files()
    
    # 統合アプローチ推奨
    recommend_unified_approach()
    
    if migrate_success:
        print("\n✅ 移行処理完了！統合設定ファイルが準備されました。")
        print("🔄 次のステップ: GUIを統合設定専用に切り替えてください。")
    else:
        print("\n⚠️ 移行処理で問題が発生しました。")

if __name__ == "__main__":
    main()
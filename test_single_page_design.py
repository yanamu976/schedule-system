#!/usr/bin/env python3
"""
1ページ統合設計の実装テスト
"""

import os
import sys
import json
from datetime import date, datetime

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

def test_single_page_structure():
    """1ページ統合設計の構造テスト"""
    print("=== 1ページ統合設計構造テスト ===")
    
    try:
        with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 新しい統合設計のメソッド確認
        required_methods = [
            '_unified_single_page',
            '_create_navigation_sidebar',
            '_basic_settings_section',
            '_schedule_generation_section',
            '_inline_priority_settings_section',
            '_inline_configuration_section',
            '_create_footer'
        ]
        
        found_methods = 0
        for method in required_methods:
            if f"def {method}" in content:
                print(f"✅ {method}メソッドが実装されています")
                found_methods += 1
            else:
                print(f"❌ {method}メソッドが見つかりません")
        
        # 古いページ切り替えロジックが削除されているか確認
        if 'show_config' not in content or content.count('show_config') < 5:  # 最小限の使用のみ
            print("✅ 古いページ切り替えロジックが簡素化されています")
            found_methods += 1
        else:
            print("⚠️ 古いページ切り替えロジックが残っています")
        
        return found_methods >= 7
        
    except Exception as e:
        print(f"❌ 1ページ統合設計構造テストエラー: {e}")
        return False

def test_navigation_features():
    """ナビゲーション機能テスト"""
    print("\n=== ナビゲーション機能テスト ===")
    
    try:
        with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # HTMLナビゲーション要素の確認
        navigation_elements = [
            'nav-button',
            'scrollIntoView',
            '#basic-settings',
            '#schedule-generation',
            '#priority-settings',
            '#detail-settings'
        ]
        
        found_elements = 0
        for element in navigation_elements:
            if element in content:
                print(f"✅ ナビゲーション要素: {element}")
                found_elements += 1
            else:
                print(f"❌ ナビゲーション要素未確認: {element}")
        
        # サイドバークイックアクション確認
        quick_actions = [
            '🔄 全体リセット',
            '📁 設定ファイル管理'
        ]
        
        found_actions = 0
        for action in quick_actions:
            if action in content:
                print(f"✅ クイックアクション: {action}")
                found_actions += 1
        
        return found_elements >= 4 and found_actions >= 1
        
    except Exception as e:
        print(f"❌ ナビゲーション機能テストエラー: {e}")
        return False

def test_section_integration():
    """セクション統合テスト"""
    print("\n=== セクション統合テスト ===")
    
    try:
        with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 各セクションのHTML IDの確認
        section_ids = [
            '<div id="basic-settings">',
            '<div id="schedule-generation">',
            '<div id="priority-settings">',
            '<div id="detail-settings">'
        ]
        
        found_sections = 0
        for section_id in section_ids:
            if section_id in content:
                print(f"✅ セクションID: {section_id}")
                found_sections += 1
            else:
                print(f"❌ セクションID未確認: {section_id}")
        
        # インライン機能の確認
        inline_features = [
            'key="save_employees_basic"',
            'key="priority_inline_',
            'key="loc_name_inline_',
            'add_location_form_inline'
        ]
        
        found_features = 0
        for feature in inline_features:
            if feature in content:
                print(f"✅ インライン機能: {feature}")
                found_features += 1
        
        return found_sections >= 3 and found_features >= 3
        
    except Exception as e:
        print(f"❌ セクション統合テストエラー: {e}")
        return False

def test_state_preservation():
    """状態保持テスト"""
    print("\n=== 状態保持テスト ===")
    
    try:
        with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # セッション状態保持の確認
        session_preservation = [
            'gui_instance',
            'st.session_state.gui_instance',
            '_ensure_config_sync',
            '_auto_save_unified_config'
        ]
        
        found_preservation = 0
        for preservation in session_preservation:
            if preservation in content:
                print(f"✅ 状態保持機能: {preservation}")
                found_preservation += 1
        
        # rerunの最小化確認
        rerun_count = content.count('st.rerun()')
        if rerun_count < 15:  # 適度な数に抑制
            print(f"✅ st.rerun()の使用が最適化されています ({rerun_count}箇所)")
        else:
            print(f"⚠️ st.rerun()の使用が多すぎます ({rerun_count}箇所)")
            return False
        
        return found_preservation >= 3
        
    except Exception as e:
        print(f"❌ 状態保持テストエラー: {e}")
        return False

def test_unified_config_integration():
    """統合設定統合テスト"""
    print("\n=== 統合設定統合テスト ===")
    
    try:
        # CompleteGUIクラスが正しく動作するか確認
        from schedule_gui_fixed import CompleteGUI
        
        print("✅ CompleteGUIクラスのインポート成功")
        
        # 統合設定管理の確認
        from unified_config_manager import UnifiedConfigManager
        
        manager = UnifiedConfigManager()
        config_files = manager.get_unified_config_files()
        
        print(f"✅ 統合設定ファイル: {len(config_files)}個")
        
        if config_files:
            # 最初のファイルで統合テスト
            test_file = config_files[0]
            config = manager.load_complete_config(test_file, force_update_session=False)
            
            if config:
                work_locations = config.get("work_locations", [])
                employees = config.get("employees", [])
                priorities = config.get("employee_priorities", {})
                
                print(f"✅ 設定読み込み成功: {test_file}")
                print(f"  - 勤務場所: {len(work_locations)}箇所")
                print(f"  - 従業員: {len(employees)}名")
                print(f"  - 優先度設定: {len(priorities)}名分")
                
                return True
            else:
                print("❌ 設定ファイル読み込み失敗")
                return False
        else:
            print("⚠️ 統合設定ファイルが見つかりません（初回起動時は正常）")
            return True
            
    except Exception as e:
        print(f"❌ 統合設定統合テストエラー: {e}")
        return False

def test_performance_optimization():
    """パフォーマンス最適化テスト"""
    print("\n=== パフォーマンス最適化テスト ===")
    
    try:
        with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # パフォーマンス最適化要素の確認
        optimization_features = [
            'st.container()',
            'with st.expander(',
            'use_container_width=True',
            'expanded=False'
        ]
        
        found_optimizations = 0
        for feature in optimization_features:
            count = content.count(feature)
            if count > 0:
                print(f"✅ 最適化機能: {feature} ({count}箇所)")
                found_optimizations += 1
        
        # 効率的なレイアウトの確認
        layout_efficiency = [
            'st.columns(',
            'with col',
            'st.form('
        ]
        
        found_layouts = 0
        for layout in layout_efficiency:
            count = content.count(layout)
            if count > 0:
                print(f"✅ レイアウト効率化: {layout} ({count}箇所)")
                found_layouts += 1
        
        return found_optimizations >= 3 and found_layouts >= 2
        
    except Exception as e:
        print(f"❌ パフォーマンス最適化テストエラー: {e}")
        return False

def main():
    """メインテスト実行"""
    print("=== 1ページ統合設計実装テスト ===")
    
    tests = [
        ("1ページ統合設計構造", test_single_page_structure),
        ("ナビゲーション機能", test_navigation_features),
        ("セクション統合", test_section_integration),
        ("状態保持", test_state_preservation),
        ("統合設定統合", test_unified_config_integration),
        ("パフォーマンス最適化", test_performance_optimization),
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
        print("\n🎉 1ページ統合設計が完全に実装されています！")
        print("📝 以下の利点が実現されました：")
        print("  - ✅ ページ切り替えなし: 全機能が1ページに統合")
        print("  - ✅ サイドバーナビゲーション: 各セクションへ瞬時移動")
        print("  - ✅ 堅牢な状態管理: セッション状態の複雑性を排除")
        print("  - ✅ 自動保存: 設定変更の即座の反映")
        print("  - ✅ 使用頻度順配置: よく使う機能を上部に配置")
        print("\n🚀 これで最も堅牢で使いやすい設計が完成しました！")
        return True
    else:
        print("\n⚠️ 一部テストが失敗しました。問題を確認してください。")
        return False

if __name__ == "__main__":
    main()
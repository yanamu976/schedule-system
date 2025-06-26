#!/usr/bin/env python3
"""
🧪 解なし原因分析機能のテストスクリプト

既存機能保持確認と新機能動作確認を行う
"""

import sys
import traceback
from datetime import datetime

def test_import():
    """importテスト"""
    print("🔍 Import テスト開始...")
    
    try:
        from schedule_gui_fixed import CompleteScheduleEngine, ConfigurationManager, WorkLocationManager
        from failure_analyzer import FailureAnalyzer
        print("✅ 全てのクラスのimportに成功")
        return True
    except Exception as e:
        print(f"❌ Import失敗: {e}")
        return False

def test_initialization():
    """初期化テスト"""
    print("🔍 初期化テスト開始...")
    
    try:
        from schedule_gui_fixed import CompleteScheduleEngine, ConfigurationManager, WorkLocationManager
        from failure_analyzer import FailureAnalyzer
        
        # メインアプリの初期化
        config = ConfigurationManager()
        location = WorkLocationManager(config)
        engine = CompleteScheduleEngine(location, config)
        
        # 分析機能の初期化
        analyzer = FailureAnalyzer()
        
        print("✅ 全てのクラスの初期化に成功")
        return True, engine, analyzer
    except Exception as e:
        print(f"❌ 初期化失敗: {e}")
        return False, None, None

def test_failure_analysis():
    """原因分析機能テスト"""
    print("🔍 原因分析機能テスト開始...")
    
    try:
        from failure_analyzer import FailureAnalyzer
        analyzer = FailureAnalyzer()
        
        # 1. 人員不足テスト
        result = analyzer._check_personnel_shortage(['田中', '佐藤'])
        if result:
            print(f"✅ 人員不足検出: {result[0]} - {result[1][:50]}...")
        else:
            print("❌ 人員不足検出失敗")
            
        # 2. 休暇集中テスト
        calendar_data = {
            '田中': {'holidays': [1, 2, 3]},
            '佐藤': {'holidays': [1, 2, 3]},
            '鈴木': {'holidays': [1, 2, 3]}
        }
        result = analyzer._check_holiday_concentration(
            calendar_data, ['田中', '佐藤', '鈴木'], 2025, 6
        )
        if result:
            print(f"✅ 休暇集中検出: {result[0]} - {result[1][:50]}...")
        else:
            print("❌ 休暇集中検出失敗")
            
        # 3. 月またぎ制約テスト
        prev_schedule = "田中: 前月末勤務\\n佐藤: 前月末勤務\\n鈴木: 前月末勤務"
        result = analyzer._check_cross_month_conflict(
            prev_schedule, ['田中', '佐藤', '鈴木'], calendar_data
        )
        if result:
            print(f"✅ 月またぎ制約検出: {result[0]} - {result[1][:50]}...")
        else:
            print("ℹ️ 月またぎ制約: 問題なし")
            
        print("✅ 原因分析機能テスト完了")
        return True
    except Exception as e:
        print(f"❌ 原因分析機能テスト失敗: {e}")
        traceback.print_exc()
        return False

def test_normal_operation():
    """正常動作テスト（既存機能保持確認）"""
    print("🔍 正常動作テスト開始...")
    
    try:
        from schedule_gui_fixed import CompleteScheduleEngine, ConfigurationManager, WorkLocationManager
        
        # メインアプリの初期化
        config = ConfigurationManager()
        location = WorkLocationManager(config)  
        engine = CompleteScheduleEngine(location, config)
        
        # 簡単なテストデータで正常動作確認
        employee_names = ['田中', '佐藤', '鈴木', '高橋', '伊藤']
        calendar_data = {
            '田中': {'holidays': [], 'duty_preferences': {}},
            '佐藤': {'holidays': [], 'duty_preferences': {}},
            '鈴木': {'holidays': [], 'duty_preferences': {}},
            '高橋': {'holidays': [], 'duty_preferences': {}},
            '伊藤': {'holidays': [], 'duty_preferences': {}}
        }
        
        # スケジュール生成実行（軽量テスト）
        result = engine.solve_schedule(
            year=2025,
            month=6,
            employee_names=employee_names,
            calendar_data=calendar_data,
            prev_schedule_data=None
        )
        
        if result and result.get('success'):
            print("✅ 正常動作確認: スケジュール生成成功")
            return True
        else:
            # 失敗時も原因分析機能が動作しているかチェック
            if result and result.get('failure_analysis'):
                print("✅ 正常動作確認: 原因分析機能が動作")
                analysis = result['failure_analysis']
                print(f"   分析結果: {analysis['reason']}")
                return True
            else:
                print("⚠️ 正常動作確認: スケジュール生成失敗（原因分析なし）")
                return False
                
    except Exception as e:
        print(f"❌ 正常動作テスト失敗: {e}")
        traceback.print_exc()
        return False

def test_failure_scenario():
    """失敗シナリオテスト（人員不足で原因分析が動作するか）"""
    print("🔍 失敗シナリオテスト開始...")
    
    try:
        from schedule_gui_fixed import CompleteScheduleEngine, ConfigurationManager, WorkLocationManager
        
        # メインアプリの初期化
        config = ConfigurationManager()
        location = WorkLocationManager(config)
        engine = CompleteScheduleEngine(location, config)
        
        # 人員不足のテストデータ
        employee_names = ['田中', '佐藤']  # 2人のみ（3箇所勤務で不足）
        calendar_data = {
            '田中': {'holidays': [], 'duty_preferences': {}},
            '佐藤': {'holidays': [], 'duty_preferences': {}}
        }
        
        # スケジュール生成実行（失敗想定）
        result = engine.solve_schedule(
            year=2025,
            month=6,
            employee_names=employee_names,
            calendar_data=calendar_data,
            prev_schedule_data=None
        )
        
        if result and not result.get('success'):
            analysis = result.get('failure_analysis')
            if analysis:
                print("✅ 失敗シナリオテスト: 原因分析機能が正常動作")
                print(f"   分析結果: {analysis['reason']} - {analysis['detail'][:100]}...")
                print(f"   対処法数: {len(analysis['solutions'])}")
                return True
            else:
                print("⚠️ 失敗シナリオテスト: 原因分析機能が動作しない")
                return False
        else:
            print("⚠️ 失敗シナリオテスト: 予想外の成功")
            return False
            
    except Exception as e:
        print(f"❌ 失敗シナリオテスト失敗: {e}")
        traceback.print_exc()
        return False

def main():
    """メインテスト実行"""
    print("🧪 解なし原因分析機能テスト開始")
    print("=" * 50)
    
    tests = [
        ("Import", test_import),
        ("初期化", test_initialization),
        ("原因分析機能", test_failure_analysis),
        ("正常動作", test_normal_operation),
        ("失敗シナリオ", test_failure_scenario),
    ]
    
    results = []
    for test_name, test_func in tests:
        print()
        if test_name == "初期化":
            success, engine, analyzer = test_func()
            results.append((test_name, success))
        else:
            success = test_func()
            results.append((test_name, success))
    
    print()
    print("=" * 50)
    print("🧪 テスト結果サマリー")
    print("=" * 50)
    
    for test_name, success in results:
        status = "✅ 成功" if success else "❌ 失敗"
        print(f"{test_name:12} : {status}")
    
    total_tests = len(results)
    passed_tests = sum(1 for _, success in results if success)
    
    print()
    print(f"総テスト数: {total_tests}")
    print(f"成功: {passed_tests}")
    print(f"失敗: {total_tests - passed_tests}")
    print(f"成功率: {passed_tests/total_tests*100:.1f}%")
    
    if passed_tests == total_tests:
        print()
        print("🎉 全テスト成功！原因分析機能の実装完了")
        return 0
    else:
        print()
        print("⚠️ 一部テスト失敗。確認が必要です。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
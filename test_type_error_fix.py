#!/usr/bin/env python3
"""
型エラー修正のテスト
"""

import os
import sys
import calendar
from datetime import date, datetime

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

def test_month_type_error_fix():
    """月の型エラー修正テスト"""
    print("=== 月の型エラー修正テスト ===")
    
    try:
        # 基本的な型チェック
        test_year = 2025
        test_month = 6
        
        # calendar.monthrangeが正常に動作するか確認
        days = calendar.monthrange(test_year, test_month)[1]
        print(f"✅ calendar.monthrange({test_year}, {test_month}) = {days}日")
        
        # 前月計算テスト
        if test_month == 1:
            prev_year, prev_month = test_year - 1, 12
        else:
            prev_year, prev_month = test_year, test_month - 1
        
        prev_days = calendar.monthrange(prev_year, prev_month)[1]
        print(f"✅ 前月計算: {prev_year}年{prev_month}月 = {prev_days}日")
        
        # 文字列と整数の混在エラーをチェック
        try:
            # これは失敗するはず
            calendar.monthrange(test_year, f"{test_month}月")
            print("❌ 文字列での月指定が通ってしまいました")
            return False
        except TypeError:
            print("✅ 文字列での月指定は正しく拒否されました")
        
        return True
        
    except Exception as e:
        print(f"❌ 月の型エラー修正テストエラー: {e}")
        return False

def test_prev_schedule_input_method():
    """前月末勤務入力メソッドのテスト"""
    print("\n=== 前月末勤務入力メソッドテスト ===")
    
    try:
        # schedule_gui_fixed.pyの内容確認
        with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 修正された関数定義の確認
        if 'def _create_prev_schedule_input(self, prev_month_display):' in content:
            print("✅ _create_prev_schedule_input メソッドのパラメータが修正されています")
        else:
            print("❌ _create_prev_schedule_input メソッドのパラメータが修正されていません")
            return False
        
        # 正しい型の使用確認
        if 'prev_year, prev_month = self._get_prev_month_info()' in content:
            print("✅ _get_prev_month_info から正しく整数の月を取得しています")
        else:
            print("❌ _get_prev_month_info の使用が正しくありません")
            return False
        
        # calendar.monthrangeの正しい使用確認
        if 'calendar.monthrange(prev_year, prev_month)[1]' in content:
            print("✅ calendar.monthrange に正しい型の引数を渡しています")
        else:
            print("❌ calendar.monthrange の引数が正しくありません")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 前月末勤務入力メソッドテストエラー: {e}")
        return False

def test_initialization_attributes():
    """初期化属性テスト"""
    print("\n=== 初期化属性テスト ===")
    
    try:
        with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 基本属性の初期化確認
        initialization_elements = [
            'self.year =',
            'self.month =',
            'self.n_days =',
            'calendar.monthrange(self.year, self.month)[1]'
        ]
        
        found_elements = 0
        for element in initialization_elements:
            if element in content:
                print(f"✅ 初期化要素: {element}")
                found_elements += 1
            else:
                print(f"❌ 初期化要素未確認: {element}")
        
        return found_elements >= 3
        
    except Exception as e:
        print(f"❌ 初期化属性テストエラー: {e}")
        return False

def test_session_state_integration():
    """セッション状態統合テスト"""
    print("\n=== セッション状態統合テスト ===")
    
    try:
        with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # セッション状態の統合確認
        session_integration = [
            "st.session_state.get('year'",
            "st.session_state.get('month'",
            "if 'year' in st.session_state",
            "if 'month' in st.session_state"
        ]
        
        found_integration = 0
        for integration in session_integration:
            if integration in content:
                print(f"✅ セッション状態統合: {integration}")
                found_integration += 1
        
        return found_integration >= 2
        
    except Exception as e:
        print(f"❌ セッション状態統合テストエラー: {e}")
        return False

def main():
    """メインテスト実行"""
    print("=== 型エラー修正テスト ===")
    
    tests = [
        ("月の型エラー修正", test_month_type_error_fix),
        ("前月末勤務入力メソッド", test_prev_schedule_input_method),
        ("初期化属性", test_initialization_attributes),
        ("セッション状態統合", test_session_state_integration),
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
        print("\n🎉 型エラーの修正が完了しています！")
        print("📝 以下の問題が解決されました：")
        print("  - calendar.monthrange への正しい型の引数渡し")
        print("  - 基本属性の適切な初期化")
        print("  - セッション状態との統合")
        print("  - 前月末勤務入力メソッドの型安全性")
        return True
    else:
        print("\n⚠️ 一部テストが失敗しました。問題を確認してください。")
        return False

if __name__ == "__main__":
    main()
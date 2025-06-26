#!/usr/bin/env python3
"""
制約緩和レベル0で警乗隔日制約ありテスト
"""

from schedule_gui_fixed import CompleteScheduleEngine, WorkLocationManager, ConfigurationManager
from datetime import datetime
import calendar

def test_level0_with_keijo():
    print('🔍 制約緩和レベル0で警乗隔日制約ありテスト')
    
    # 初期化
    config_manager = ConfigurationManager()
    location_manager = WorkLocationManager(config_manager)
    engine = CompleteScheduleEngine(location_manager, config_manager)
    
    # テスト設定
    year, month = 2025, 6
    employees = ['Aさん', 'Bさん', 'Cさん', 'Dさん', 'Eさん', 'Fさん', 'Gさん', '助勤']
    calendar_data = {}
    keijo_base_date = datetime(2025, 6, 1)
    n_days = calendar.monthrange(year, month)[1]
    
    print(f'従業員数: {len(employees)}名')
    print(f'警乗基準日: {keijo_base_date.strftime("%Y-%m-%d")}')
    
    # システム設定
    engine.year = year
    engine.month = month
    engine.setup_system(employees)
    
    # 要求解析
    ng_constraints, preferences, holidays, debug_info = engine.parse_requirements([], n_days)
    
    print(f'解析結果: NG制約={len(ng_constraints)}, 希望={len(preferences)}, 有休={len(holidays)}')
    
    # 制約緩和レベル0で警乗隔日制約を一時的に有効化
    # まず、制約緩和レベルの条件を変更
    original_line = '        if relax_level >= 1:'
    temp_line = '        if relax_level >= 999:  # 一時的に無効化'
    
    # ファイルを読み込み
    with open('schedule_gui_fixed.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 一時的な修正
    modified_content = content.replace(original_line, temp_line)
    
    # 一時ファイルに書き込み
    with open('schedule_gui_fixed_temp.py', 'w', encoding='utf-8') as f:
        f.write(modified_content)
    
    # モジュールを再インポート
    import importlib
    import sys
    
    # 一時ファイルをインポート
    sys.path.insert(0, '.')
    import schedule_gui_fixed_temp
    importlib.reload(schedule_gui_fixed_temp)
    
    # 一時エンジンで再初期化
    temp_config_manager = schedule_gui_fixed_temp.ConfigurationManager()
    temp_location_manager = schedule_gui_fixed_temp.WorkLocationManager(temp_config_manager)
    temp_engine = schedule_gui_fixed_temp.CompleteScheduleEngine(temp_location_manager, temp_config_manager)
    
    relax_level = 0
    try:
        print(f'\\n🔄 制約緩和レベル {relax_level} テスト中（警乗隔日制約あり）...')
        
        # システム設定
        temp_engine.year = year
        temp_engine.month = month
        temp_engine.setup_system(employees)
        
        # モデル構築（警乗隔日制約あり）
        model, w, nitetu_counts, cross_const = temp_engine.build_optimization_model(
            n_days, ng_constraints, preferences, holidays, relax_level, None, keijo_base_date
        )
        
        print(f'制約情報: {cross_const[:3]}...')  # 最初の3件のみ表示
        
        # 求解
        from ortools.sat.python import cp_model
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60  # 少し長めに
        status = solver.Solve(model)
        
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            print(f'✅ レベル{relax_level}: 解が見つかりました ({solver.StatusName(status)})')
            print(f'   目的関数値: {solver.ObjectiveValue()}')
            
            # 警乗配置確認
            keijo_shift_id = temp_engine._get_keijo_shift_id()
            violations = 0
            
            print(f'\\n🚁 警乗隔日制約チェック（最初10日）:')
            for day in range(min(10, n_days)):
                assigned_emp = None
                for emp_id in range(len(employees)):
                    if solver.Value(w[emp_id, day, keijo_shift_id]):
                        assigned_emp = employees[emp_id]
                        break
                
                days_offset = (datetime(year, month, 1) - keijo_base_date).days
                total_days = days_offset + day
                expected = '勤務' if total_days % 2 == 0 else '休止'
                
                if (expected == '勤務' and assigned_emp) or (expected == '休止' and not assigned_emp):
                    status_symbol = '✅'
                else:
                    status_symbol = '❌'
                    violations += 1
                
                actual = assigned_emp if assigned_emp else '休止'
                print(f'   {day+1}日: {status_symbol} 予想={expected}, 実際={actual}')
            
            print(f'\\n警乗制約違反: {violations}件')
            return True  # 成功
        else:
            print(f'❌ レベル{relax_level}: 解なし ({solver.StatusName(status)})')
            
    except Exception as e:
        print(f'❌ レベル{relax_level}: エラー - {e}')
        import traceback
        traceback.print_exc()
    finally:
        # 一時ファイルを削除
        import os
        if os.path.exists('schedule_gui_fixed_temp.py'):
            os.remove('schedule_gui_fixed_temp.py')
        if os.path.exists('__pycache__/schedule_gui_fixed_temp.cpython-39.pyc'):
            os.remove('__pycache__/schedule_gui_fixed_temp.cpython-39.pyc')
    
    return False  # 失敗

if __name__ == "__main__":
    success = test_level0_with_keijo()
    print(f'\\n🔍 制約緩和レベル0で警乗隔日制約ありテスト完了 - {"成功" if success else "失敗"}')
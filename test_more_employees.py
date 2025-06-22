#!/usr/bin/env python3
"""
従業員数を増やしてテスト
"""

from schedule_gui_fixed import CompleteScheduleEngine, WorkLocationManager, ConfigurationManager
from datetime import datetime
import calendar

def test_with_more_employees():
    print('🔍 従業員数を増やしてテスト')
    
    # 初期化
    config_manager = ConfigurationManager()
    location_manager = WorkLocationManager(config_manager)
    engine = CompleteScheduleEngine(location_manager, config_manager)
    
    # テスト設定（従業員数を8名に増加）
    year, month = 2025, 6
    employees = ['Aさん', 'Bさん', 'Cさん', 'Dさん', 'Eさん', 'Fさん', 'Gさん', '助勤']
    calendar_data = {}
    keijo_base_date = datetime(2025, 6, 1)
    n_days = calendar.monthrange(year, month)[1]
    
    print(f'従業員数: {len(employees)}名 - {employees}')
    
    # システム設定
    engine.year = year
    engine.month = month
    engine.setup_system(employees)
    
    # 要求解析
    ng_constraints, preferences, holidays, debug_info = engine.parse_requirements([], n_days)
    
    print(f'解析結果: NG制約={len(ng_constraints)}, 希望={len(preferences)}, 有休={len(holidays)}')
    
    # 警乗制約ありでテスト
    for relax_level in range(4):
        try:
            print(f'\n🔄 制約緩和レベル {relax_level} テスト中...')
            
            # モデル構築（警乗制約あり）
            model, w, nitetu_counts, cross_const = engine.build_optimization_model(
                n_days, ng_constraints, preferences, holidays, relax_level, None, keijo_base_date
            )
            
            # 求解
            from ortools.sat.python import cp_model
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 30  # 少し長めに
            status = solver.Solve(model)
            
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                print(f'✅ レベル{relax_level}: 解が見つかりました ({solver.StatusName(status)})')
                print(f'   目的関数値: {solver.ObjectiveValue()}')
                
                # 警乗配置確認
                keijo_shift_id = engine._get_keijo_shift_id()
                violations = 0
                
                print(f'\\n🚁 警乗配置確認（最初10日）:')
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
                
                # 各勤務場所の配置状況
                print(f'\\n📊 勤務場所配置状況（最初5日）:')
                for day in range(min(5, n_days)):
                    day_assignments = []
                    for duty_id in range(len(engine.duty_names)):
                        for emp_id in range(len(employees)):
                            if solver.Value(w[emp_id, day, duty_id]):
                                duty_name = engine.duty_names[duty_id]
                                emp_name = employees[emp_id]
                                day_assignments.append(f'{duty_name}:{emp_name}')
                    
                    print(f'   {day+1}日: {", ".join(day_assignments)}')
                
                return True  # 成功
            else:
                print(f'❌ レベル{relax_level}: 解なし ({solver.StatusName(status)})')
                
        except Exception as e:
            print(f'❌ レベル{relax_level}: エラー - {e}')
    
    return False  # 失敗

if __name__ == "__main__":
    success = test_with_more_employees()
    print(f'\n🔍 従業員数増加テスト完了 - {"成功" if success else "失敗"}')
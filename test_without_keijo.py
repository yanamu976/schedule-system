#!/usr/bin/env python3
"""
警乗隔日制約なしでテストして基本システムの動作確認
"""

from schedule_gui_fixed import CompleteScheduleEngine, WorkLocationManager, ConfigurationManager
from datetime import datetime
import calendar

def test_without_keijo_constraint():
    print('🔍 警乗隔日制約なしテスト')
    
    # 初期化
    config_manager = ConfigurationManager()
    location_manager = WorkLocationManager(config_manager)
    engine = CompleteScheduleEngine(location_manager, config_manager)
    
    # テスト設定
    year, month = 2025, 6
    employees = ['Aさん', 'Bさん', 'Cさん', 'Dさん', 'Eさん', '助勤']
    calendar_data = {}
    n_days = calendar.monthrange(year, month)[1]
    
    # システム設定
    engine.year = year
    engine.month = month
    engine.setup_system(employees)
    
    # 要求解析
    ng_constraints, preferences, holidays, debug_info = engine.parse_requirements([], n_days)
    
    print(f'解析結果: NG制約={len(ng_constraints)}, 希望={len(preferences)}, 有休={len(holidays)}')
    
    # 各制約緩和レベルでテスト（警乗制約なし）
    for relax_level in range(4):
        try:
            print(f'\n🔄 制約緩和レベル {relax_level} テスト中...')
            
            # モデル構築（keijo_base_date=Noneで警乗制約を無効化）
            model, w, nitetu_counts, cross_const = engine.build_optimization_model(
                n_days, ng_constraints, preferences, holidays, relax_level, None, None
            )
            
            # 求解
            from ortools.sat.python import cp_model
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 10
            status = solver.Solve(model)
            
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                print(f'✅ レベル{relax_level}: 解が見つかりました ({solver.StatusName(status)})')
                print(f'   目的関数値: {solver.ObjectiveValue()}')
                
                # 勤務配置確認（最初5日）
                keijo_shift_id = engine._get_keijo_shift_id()
                
                for day in range(min(5, n_days)):
                    day_assignments = []
                    for duty_id in range(len(engine.duty_names)):
                        for emp_id in range(len(employees)):
                            if solver.Value(w[emp_id, day, duty_id]):
                                duty_name = engine.duty_names[duty_id]
                                emp_name = employees[emp_id]
                                day_assignments.append(f'{duty_name}:{emp_name}')
                    
                    print(f'   {day+1}日目: {", ".join(day_assignments)}')
                
                return True  # 成功
            else:
                print(f'❌ レベル{relax_level}: 解なし ({solver.StatusName(status)})')
                
        except Exception as e:
            print(f'❌ レベル{relax_level}: エラー - {e}')
            import traceback
            traceback.print_exc()
    
    return False  # 失敗

if __name__ == "__main__":
    success = test_without_keijo_constraint()
    print(f'\n🔍 警乗隔日制約なしテスト完了 - {"成功" if success else "失敗"}')
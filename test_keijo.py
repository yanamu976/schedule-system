#!/usr/bin/env python3
"""
警乗隔日制約のテストスクリプト
"""

from schedule_gui_fixed import CompleteScheduleEngine, WorkLocationManager, ConfigurationManager
from datetime import datetime
import calendar

def test_keijo_constraint():
    print('🔍 制約緩和レベル別テスト')
    
    # 初期化
    config_manager = ConfigurationManager()
    location_manager = WorkLocationManager(config_manager)
    engine = CompleteScheduleEngine(location_manager, config_manager)
    
    # テスト設定
    year, month = 2025, 6
    employees = ['Aさん', 'Bさん', 'Cさん', 'Dさん', 'Eさん', '助勤']
    calendar_data = {}
    keijo_base_date = datetime(2025, 6, 1)
    n_days = calendar.monthrange(year, month)[1]
    
    # システム設定
    engine.year = year
    engine.month = month
    engine.setup_system(employees)
    
    # 要求解析
    ng_constraints, preferences, holidays, debug_info = engine.parse_requirements([], n_days)
    
    print(f'解析結果: NG制約={len(ng_constraints)}, 希望={len(preferences)}, 有休={len(holidays)}')
    
    # 各制約緩和レベルでテスト
    for relax_level in range(4):
        try:
            print(f'\n🔄 制約緩和レベル {relax_level} テスト中...')
            
            # モデル構築
            model, w, nitetu_counts, cross_const = engine.build_optimization_model(
                n_days, ng_constraints, preferences, holidays, relax_level, None, keijo_base_date
            )
            
            # 求解
            from ortools.sat.python import cp_model
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 10  # 短時間で試す
            status = solver.Solve(model)
            
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                print(f'✅ レベル{relax_level}: 解が見つかりました ({solver.StatusName(status)})')
                print(f'   目的関数値: {solver.ObjectiveValue()}')
                
                # 警乗配置確認
                keijo_shift_id = engine._get_keijo_shift_id()
                violations = 0
                
                for day in range(min(5, n_days)):
                    assigned_count = sum(solver.Value(w[emp_id, day, keijo_shift_id]) for emp_id in range(len(employees)))
                    days_offset = (datetime(year, month, 1) - keijo_base_date).days
                    total_days = days_offset + day
                    expected_count = 1 if total_days % 2 == 0 else 0
                    
                    if assigned_count != expected_count:
                        violations += 1
                        
                print(f'   警乗制約違反: {violations}件（最初5日チェック）')
                return True  # 成功
            else:
                print(f'❌ レベル{relax_level}: 解なし ({solver.StatusName(status)})')
                
        except Exception as e:
            print(f'❌ レベル{relax_level}: エラー - {e}')
    
    return False  # 失敗

if __name__ == "__main__":
    success = test_keijo_constraint()
    print(f'\n🔍 制約緩和レベル別テスト完了 - {"成功" if success else "失敗"}')
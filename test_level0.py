#!/usr/bin/env python3
"""
制約緩和レベル0でテスト（警乗隔日制約なし）
"""

from schedule_gui_fixed import CompleteScheduleEngine, WorkLocationManager, ConfigurationManager
from datetime import datetime
import calendar

def test_level0():
    print('🔍 制約緩和レベル0テスト（警乗隔日制約なし）')
    
    # 初期化
    config_manager = ConfigurationManager()
    location_manager = WorkLocationManager(config_manager)
    engine = CompleteScheduleEngine(location_manager, config_manager)
    
    # テスト設定
    year, month = 2025, 6
    employees = ['Aさん', 'Bさん', 'Cさん', 'Dさん', 'Eさん', 'Fさん', 'Gさん', '助勤']
    calendar_data = {}
    n_days = calendar.monthrange(year, month)[1]
    
    print(f'従業員数: {len(employees)}名')
    
    # システム設定
    engine.year = year
    engine.month = month
    engine.setup_system(employees)
    
    # 要求解析
    ng_constraints, preferences, holidays, debug_info = engine.parse_requirements([], n_days)
    
    print(f'解析結果: NG制約={len(ng_constraints)}, 希望={len(preferences)}, 有休={len(holidays)}')
    
    # 制約緩和レベル0でテスト（警乗基準日を設定しない＝警乗隔日制約なし）
    relax_level = 0
    try:
        print(f'\\n🔄 制約緩和レベル {relax_level} テスト中...')
        
        # モデル構築（keijo_base_date=Noneで警乗隔日制約なし）
        model, w, nitetu_counts, cross_const = engine.build_optimization_model(
            n_days, ng_constraints, preferences, holidays, relax_level, None, None
        )
        
        print(f'制約情報: {cross_const}')
        
        # 求解
        from ortools.sat.python import cp_model
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30
        status = solver.Solve(model)
        
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            print(f'✅ レベル{relax_level}: 解が見つかりました ({solver.StatusName(status)})')
            print(f'   目的関数値: {solver.ObjectiveValue()}')
            
            # 警乗配置確認（隔日制約なしで自由配置）
            keijo_shift_id = engine._get_keijo_shift_id()
            print(f'\\n🚁 警乗配置確認（自由配置、最初10日）:')
            for day in range(min(10, n_days)):
                assigned_emp = None
                for emp_id in range(len(employees)):
                    if solver.Value(w[emp_id, day, keijo_shift_id]):
                        assigned_emp = employees[emp_id]
                        break
                
                print(f'   {day+1}日: {assigned_emp}')
            
            return True  # 成功
        else:
            print(f'❌ レベル{relax_level}: 解なし ({solver.StatusName(status)})')
            
    except Exception as e:
        print(f'❌ レベル{relax_level}: エラー - {e}')
        import traceback
        traceback.print_exc()
    
    return False  # 失敗

if __name__ == "__main__":
    success = test_level0()
    print(f'\\n🔍 制約緩和レベル0テスト完了 - {"成功" if success else "失敗"}')
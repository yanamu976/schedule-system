#!/usr/bin/env python3
"""
ハード制約として実装された警乗隔日制約のテスト
"""

from schedule_gui_fixed import CompleteScheduleEngine, WorkLocationManager, ConfigurationManager
from datetime import datetime
import calendar

def test_hard_keijo_constraint():
    print('🔍 ハード制約警乗隔日制約テスト')
    
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
    
    # 各制約緩和レベルでテスト
    for relax_level in [0, 1, 2]:
        print(f'\\n=== 制約緩和レベル {relax_level} ===')
        
        try:
            # モデル構築（ハード制約）
            model, w, nitetu_counts, cross_const = engine.build_optimization_model(
                n_days, ng_constraints, preferences, holidays, relax_level, None, keijo_base_date
            )
            
            print(f'制約情報:')
            for info in cross_const[:3]:  # 最初の3件表示
                print(f'  {info}')
            
            # 求解
            from ortools.sat.python import cp_model
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 60
            status = solver.Solve(model)
            
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                print(f'✅ 解が見つかりました ({solver.StatusName(status)})')
                print(f'   目的関数値: {solver.ObjectiveValue()}')
                
                # 警乗配置の詳細確認
                keijo_shift_id = engine._get_keijo_shift_id()
                print(f'\\n🚁 警乗隔日パターン確認（全30日）:')
                
                days_offset = (datetime(year, month, 1) - keijo_base_date).days
                perfect_matches = 0
                violations = 0
                
                for day in range(n_days):
                    assigned_count = sum(solver.Value(w[emp_id, day, keijo_shift_id]) for emp_id in range(len(employees)))
                    assigned_emp = None
                    for emp_id in range(len(employees)):
                        if solver.Value(w[emp_id, day, keijo_shift_id]):
                            assigned_emp = employees[emp_id]
                            break
                    
                    total_days = days_offset + day
                    expected_pattern = '勤務' if total_days % 2 == 0 else '休止'
                    expected_count = 1 if total_days % 2 == 0 else 0
                    
                    if assigned_count == expected_count:
                        status_symbol = '✅'
                        perfect_matches += 1
                    else:
                        status_symbol = '❌'
                        violations += 1
                    
                    actual = f'{assigned_emp}({assigned_count}人)' if assigned_emp else f'休止({assigned_count}人)'
                    
                    # 最初の10日と最後の5日のみ表示
                    if day < 10 or day >= n_days - 5:
                        print(f'  {day+1:2d}日: {status_symbol} 期待={expected_pattern}({expected_count}人), 実際={actual}')
                    elif day == 10:
                        print('  ...')
                
                accuracy = (perfect_matches / n_days) * 100
                print(f'\\n📊 隔日パターン精度: {perfect_matches}/{n_days} = {accuracy:.1f}%')
                
                if accuracy == 100:
                    print(f'🎉 完璧！警乗隔日制約が100%実現されています！')
                    return True
                elif accuracy >= 90:
                    print(f'✅ 優秀！隔日パターンがほぼ完璧に実現されています')
                elif accuracy >= 70:
                    print(f'⚠️ 良好。隔日パターンがかなり実現されています')
                else:
                    print(f'❌ 不良。隔日パターンが十分に実現されていません')
                    
            else:
                print(f'❌ 解なし: {solver.StatusName(status)}')
                
        except Exception as e:
            print(f'❌ エラー: {e}')
            import traceback
            traceback.print_exc()
    
    return False

if __name__ == "__main__":
    success = test_hard_keijo_constraint()
    print(f'\\n🔍 ハード制約テスト完了 - {"成功" if success else "失敗"}')
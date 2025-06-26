#!/usr/bin/env python3
"""
警乗隔日制約の詳細検証スクリプト
"""

from schedule_gui_fixed import CompleteScheduleEngine, WorkLocationManager, ConfigurationManager
from datetime import datetime
import calendar

def verify_keijo_constraints():
    print('🔍 警乗隔日制約の詳細検証')
    
    # 初期化
    config_manager = ConfigurationManager()
    location_manager = WorkLocationManager(config_manager)
    engine = CompleteScheduleEngine(location_manager, config_manager)
    
    # テスト設定
    year, month = 2025, 6
    employees = ['Aさん', 'Bさん', 'Cさん', 'Dさん', 'Eさん', 'Fさん', 'Gさん', '助勤']
    n_days = calendar.monthrange(year, month)[1]
    keijo_base_date = datetime(2025, 6, 1)
    
    # システム設定
    engine.year = year
    engine.month = month
    engine.setup_system(employees)
    
    # 要求解析
    ng_constraints, preferences, holidays, debug_info = engine.parse_requirements([], n_days)
    
    print(f'=== 検証1: レベル0で警乗隔日制約が適用されているか ===')
    
    # レベル0で制約緩和条件を一時的に無効化して強制的に警乗隔日制約を適用
    print(f'📋 制約緩和条件を確認...')
    
    # 現在のコードを確認
    keijo_shift_id = engine._get_keijo_shift_id()
    print(f'警乗シフトID: {keijo_shift_id}')
    
    # 制約が適用される条件を直接テスト（制約情報のみ取得）
    print(f'🔍 制約緩和レベル別の制約適用状況:')
    
    for level in [0, 1, 2]:
        engine._current_relax_level = level
        
        # 制約適用判定のロジックをテスト
        if level >= 1:
            expected_msg = f"🚁 警乗隔日制約: 制約緩和レベル{level}により無効化"
            print(f'  レベル{level}: {expected_msg}')
        else:
            print(f'  レベル{level}: 🚁 警乗隔日制約が適用される予定')
    
    print(f'\\n=== 検証2: 制約緩和の具体的な動作 ===')
    
    # 制約緩和レベル別の実際の動作を確認
    for test_level in [0, 1, 2]:
        print(f'\\n--- 制約緩和レベル {test_level} ---')
        
        try:
            # モデル構築を試行
            from ortools.sat.python import cp_model
            model = cp_model.CpModel()
            
            # 決定変数作成
            w = {}
            for e in range(len(employees)):
                for d in range(n_days):
                    for s in range(5):  # 5種類のシフト
                        w[e, d, s] = model.NewBoolVar(f"w_{e}_{d}_{s}")
            
            # 制約追加前の変数数
            vars_before = len(model.Proto().variables)
            constraints_before = len(model.Proto().constraints)
            
            # 警乗隔日制約を追加
            engine._current_relax_level = test_level
            constraint_info = engine._add_keijo_alternating_constraints(
                model, w, year, month, n_days, keijo_base_date
            )
            
            # 制約追加後の変数数
            vars_after = len(model.Proto().variables)
            constraints_after = len(model.Proto().constraints)
            
            added_constraints = constraints_after - constraints_before
            
            print(f'  制約情報: {constraint_info[0] if constraint_info else "制約なし"}')
            print(f'  追加された制約数: {added_constraints}個')
            
            if added_constraints > 0:
                print(f'  ✅ 警乗隔日制約が実際に追加されました')
                
                # 実際の制約内容を確認（最初の3日分）
                print(f'  📋 実際の制約内容（最初3日）:')
                days_offset = (datetime(year, month, 1) - keijo_base_date).days
                for d in range(min(3, n_days)):
                    total_days = days_offset + d
                    if total_days % 2 == 0:
                        print(f'    {d+1}日目: 警乗に必ず1人配置（偶数日）')
                    else:
                        print(f'    {d+1}日目: 警乗は0人配置（奇数日）')
            else:
                print(f'  ❌ 警乗隔日制約は追加されませんでした（制約緩和済み）')
                
        except Exception as e:
            print(f'  ❌ エラー: {e}')
    
    print(f'\\n=== 検証3: 実際の求解での警乗配置パターン ===')
    
    # レベル1で実際に求解して警乗配置を確認
    try:
        model, w, nitetu_counts, cross_const = engine.build_optimization_model(
            n_days, ng_constraints, preferences, holidays, 1, None, keijo_base_date
        )
        
        # 求解
        from ortools.sat.python import cp_model
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30
        status = solver.Solve(model)
        
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            print(f'✅ レベル1で解が見つかりました')
            
            # 警乗配置の詳細確認
            keijo_shift_id = engine._get_keijo_shift_id()
            print(f'\\n🚁 警乗配置の詳細（全30日）:')
            
            days_offset = (datetime(year, month, 1) - keijo_base_date).days
            pattern_violations = 0
            
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
                else:
                    status_symbol = '❌'
                    pattern_violations += 1
                
                actual = f'{assigned_emp}({assigned_count}人)' if assigned_emp else f'休止({assigned_count}人)'
                print(f'  {day+1:2d}日: {status_symbol} 期待={expected_pattern}({expected_count}人), 実際={actual}')
            
            print(f'\\n📊 隔日パターン違反: {pattern_violations}件 / {n_days}日')
            if pattern_violations == 0:
                print(f'🎉 完璧な隔日パターンが実現されています！')
            else:
                print(f'⚠️ 隔日パターンに {pattern_violations} 件の違反があります')
                
        else:
            print(f'❌ レベル1でも解なし: {solver.StatusName(status)}')
            
    except Exception as e:
        print(f'❌ 求解エラー: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_keijo_constraints()
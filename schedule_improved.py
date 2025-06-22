#!/usr/bin/env python3
"""
勤務表自動作成システム（統合設定管理版）
- すべての設定を単一のJSONファイルで管理
- 直感的な設定ページと明確な保存フロー
- 月またぎ制約、複数勤務場所、Excel出力など既存機能は維持
"""

import streamlit as st
import xlsxwriter
import os
import re
import calendar
import json
import tempfile
from datetime import datetime, date
from collections import defaultdict
from ortools.sat.python import cp_model

# =================== 統合設定管理システム ===================

class UnifiedConfigurationManager:
    """
    すべての設定（勤務場所、従業員、優先度など）を単一ファイルで管理するクラス。
    """
    def __init__(self):
        self.configs_dir = "configs"
        self._ensure_configs_dir()
        self.current_config = None
        self.current_filename = None

    def _ensure_configs_dir(self):
        """設定ファイルを保存する`configs/`ディレクトリを確保する。"""
        if not os.path.exists(self.configs_dir):
            os.makedirs(self.configs_dir)

    def _get_default_config(self):
        """
        システムの初期状態として使用するデフォルト設定を返す。
        """
        return {
            "config_name": "デフォルト設定",
            "created_date": datetime.now().strftime("%Y-%m-%d"),
            "work_locations": [
                {"name": "駅A", "type": "一徹勤務", "duration": 16, "color": "#FF6B6B"},
                {"name": "指令", "type": "一徹勤務", "duration": 16, "color": "#FF8E8E"},
                {"name": "警乗", "type": "一徹勤務", "duration": 16, "color": "#FFB6B6"}
            ],
            "holiday_type": {"name": "休暇", "color": "#FFEAA7"},
            "employees": ["Aさん", "Bさん", "Cさん", "Dさん", "Eさん", "Fさん", "Gさん", "助勤"],
            "employee_priorities": {
                "Aさん": {"駅A": 3, "指令": 2, "警乗": 0},
                "Bさん": {"駅A": 3, "指令": 3, "警乗": 3},
                "Cさん": {"駅A": 0, "指令": 0, "警乗": 3}
            },
            "priority_weights": {"0": 1000, "1": 10, "2": 5, "3": 0},
            "keijo_base_date": date(2025, 6, 1).isoformat()
        }

    def get_config_files(self):
        """設定ファイルの一覧を取得する。"""
        if not os.path.exists(self.configs_dir):
            return []
        files = [f for f in os.listdir(self.configs_dir) if f.endswith('.json')]
        return sorted(files)

    def load_config(self, filename):
        """
        指定されたファイル名から設定を読み込み、現在の設定として保持する。
        """
        filepath = os.path.join(self.configs_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                # 過去のバージョンとの互換性担保
                if "keijo_base_date" not in config_data:
                    config_data["keijo_base_date"] = self._get_default_config()["keijo_base_date"]
                self.current_config = config_data
                self.current_filename = filename
                return True
        except (FileNotFoundError, json.JSONDecodeError) as e:
            st.error(f"設定ファイル '{filename}' の読み込みに失敗しました: {e}")
            return False

    def save_config(self, filename, config_data):
        """
        現在の設定を指定されたファイル名で保存する。（上書き・名前を付けて保存兼用）
        """
        if not filename.endswith(".json"):
            filename += ".json"

        filepath = os.path.join(self.configs_dir, filename)
        config_data["created_date"] = datetime.now().strftime("%Y-%m-%d")
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            # 保存が成功したら、現在の設定とファイル名を更新
            self.current_config = config_data
            self.current_filename = filename
            return True
        except Exception as e:
            st.error(f"設定の保存に失敗しました: {e}")
            return False
            
    def initialize_default_config(self):
        """
        configs/ ディレクトリに default.json がなければ作成し、それを読み込む。
        """
        default_path = os.path.join(self.configs_dir, "default.json")
        if not os.path.exists(default_path):
            default_config = self._get_default_config()
            self.save_config("default.json", default_config)
            print("INFO: default.json を作成しました。")
        self.load_config("default.json")


    # --- 設定アクセス用メソッド ---
    # これにより、アプリの他の部分がconfigの内部構造を意識する必要がなくなる

    def get_config_name(self):
        return self.current_config.get("config_name", "名称未設定")

    def get_work_locations(self):
        return self.current_config.get("work_locations", [])

    def get_duty_names(self):
        return [loc["name"] for loc in self.get_work_locations()]
        
    def get_holiday_type(self):
        return self.current_config.get("holiday_type", {"name": "休暇", "color": "#FFEAA7"})

    def get_employees(self):
        return self.current_config.get("employees", [])

    def get_employee_priorities(self):
        return self.current_config.get("employee_priorities", {})

    def get_priority_weights(self):
        weights = self.current_config.get("priority_weights", {"0": 1000, "1": 10, "2": 5, "3": 0})
        return {int(k): v for k, v in weights.items()}
        
    def get_keijo_base_date(self):
        date_str = self.current_config.get("keijo_base_date")
        if date_str:
            return date.fromisoformat(date_str)
        return date(2025, 6, 1)


# =================== 勤務表生成エンジン ===================

class CompleteScheduleEngine:
    """勤務表生成エンジン（変更なし、設定はConfigManager経由で取得）"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.OFF_SHIFT_ID = None
        self.weights = {
            'RELIEF': 10, 'HOLIDAY': 50, 'NITETU': 15, 'N2_GAP': 30, 
            'PREF': 5, 'CROSS_MONTH': 20, 'PRIORITY': 25
        }
        self.priority_weights = self.config_manager.get_priority_weights()
        self.relax_messages = {
            0: "✅ 全制約満足", 1: "⚠️ 二徹バランス緩和（格差許容）",
            2: "⚠️ 助勤フル解禁（ペナルティ低減）", 3: "⚠️ 有休の一部を勤務変更（休多→勤務優先）"
        }

    def _get_keijo_shift_id(self):
        duty_names = self.config_manager.get_duty_names()
        for i, name in enumerate(duty_names):
            if "警乗" in name:
                return i
        return None

    def setup_system(self, employee_names):
        self.employees = employee_names
        self.n_employees = len(employee_names)
        # "助勤"がリストにない場合でもエラーにならないようにする
        self.relief_employee_id = self.employees.index("助勤") if "助勤" in self.employees else -1

        self.duty_names = self.config_manager.get_duty_names()
        self.n_duties = len(self.duty_names)
        
        holiday_type = self.config_manager.get_holiday_type()
        self.shift_names = self.duty_names + [holiday_type["name"]] + ["非番"]
        self.n_shifts = len(self.shift_names)
        self.OFF_SHIFT_ID = self.n_shifts - 1
        
        self.name_to_id = {name: i for i, name in enumerate(employee_names)}
        self.id_to_name = {i: name for i, name in enumerate(employee_names)}
        self.shift_name_to_id = {name: i for i, name in enumerate(self.shift_names)}

    def parse_requirements(self, requirement_lines, n_days, employee_priorities):
        ng_constraints = defaultdict(list)
        preferences = {}
        holidays = set()
        debug_info = []
        day_pattern = re.compile(r'(\d{1,2})日')
        range_pattern = re.compile(r'(\d{1,2})日から(\d{1,2})日まで')
        duty_name_to_id = {name: i for i, name in enumerate(self.duty_names)}
        
        for line in requirement_lines:
            employee_id = None
            employee_name = None
            for name, emp_id in self.name_to_id.items():
                if name in line:
                    employee_id = emp_id
                    employee_name = name
                    break
            if employee_id is None: continue

            if any(keyword in line for keyword in ("有休", "休み", "休暇")):
                range_match = range_pattern.search(line)
                if range_match:
                    start_day, end_day = map(int, range_match.groups())
                    for day in range(start_day - 1, end_day):
                        if 0 <= day < n_days: holidays.add((employee_id, day))
                else:
                    for match in day_pattern.finditer(line):
                        day = int(match.group(1)) - 1
                        if 0 <= day < n_days: holidays.add((employee_id, day))
            
            for match in day_pattern.finditer(line):
                day = int(match.group(1)) - 1
                if 0 <= day < n_days:
                    for duty_name, duty_id in duty_name_to_id.items():
                        if duty_name in line:
                            if "希望" in line:
                                preferences[(employee_id, day, duty_id)] = -self.weights['PREF']
                            elif any(avoid in line for avoid in ["入りたくない", "避けたい"]):
                                preferences[(employee_id, day, duty_id)] = +self.weights['PREF']

        priority_weights = self.config_manager.get_priority_weights()
        for emp_name, priorities in employee_priorities.items():
            if emp_name in self.name_to_id:
                emp_id = self.name_to_id[emp_name]
                for duty_name, priority in priorities.items():
                    if duty_name in duty_name_to_id:
                        duty_id = duty_name_to_id[duty_name]
                        penalty = priority_weights.get(priority, 0)
                        if penalty > 0:
                            for day in range(n_days):
                                preferences[(emp_id, day, duty_id)] = penalty
        
        return ng_constraints, preferences, holidays, debug_info
        
    def parse_previous_month_schedule(self, prev_schedule_data, prev_month_last_days=3):
        prev_duties = {}
        debug_info = []
        for employee_name, schedule_data in prev_schedule_data.items():
            if employee_name not in self.name_to_id: continue
            emp_id = self.name_to_id[employee_name]
            for i, shift in enumerate(schedule_data):
                if shift == "未入力": continue
                relative_day = -(prev_month_last_days - i)
                is_duty = shift in self.duty_names
                prev_duties[(emp_id, relative_day)] = is_duty
        return prev_duties, debug_info

    def build_optimization_model(self, n_days, ng_constraints, preferences, holidays, 
                                relax_level=0, prev_duties=None, keijo_base_date=None):
        model = cp_model.CpModel()
        w = {}
        for e in range(self.n_employees):
            for d in range(n_days):
                for s in range(self.n_shifts):
                    w[e, d, s] = model.NewBoolVar(f"w_{e}_{d}_{s}")
        
        for e in range(self.n_employees):
            for d in range(n_days):
                model.AddExactlyOne(w[e, d, s] for s in range(self.n_shifts))
        
        keijo_shift_id = self._get_keijo_shift_id()
        for d in range(n_days):
            for s in range(self.n_duties):
                if s == keijo_shift_id and keijo_base_date is not None:
                    current_month_start = datetime(self.year, self.month, 1)
                    days_offset = (current_month_start.date() - keijo_base_date).days
                    total_days = days_offset + d
                    if total_days % 2 == 0:
                        model.Add(sum(w[e, d, s] for e in range(self.n_employees)) == 1)
                    else:
                        model.Add(sum(w[e, d, s] for e in range(self.n_employees)) == 0)
                else:
                    model.Add(sum(w[e, d, s] for e in range(self.n_employees)) == 1)

        for e in range(self.n_employees):
            for d in range(n_days - 1):
                for s in range(self.n_duties):
                    model.AddImplication(w[e, d, s], w[e, d + 1, self.OFF_SHIFT_ID])
        
        for e in range(self.n_employees):
            for d in range(1, n_days):
                duty_prev_day = sum(w[e, d - 1, s] for s in range(self.n_duties))
                model.Add(duty_prev_day >= w[e, d, self.OFF_SHIFT_ID])
        
        for e in range(self.n_employees):
            for d in range(n_days - 1):
                model.Add(w[e, d, self.OFF_SHIFT_ID] + w[e, d + 1, self.OFF_SHIFT_ID] <= 1)
        
        cross_month_constraints = []
        cross_month_nitetu_vars = []
        if prev_duties:
            for e in range(self.n_employees):
                emp_name = self.id_to_name[e]
                if (e, -1) in prev_duties and prev_duties[(e, -1)]:
                    model.Add(w[e, 0, self.OFF_SHIFT_ID] == 1)
                    cross_month_constraints.append(f"{emp_name}: 前日勤務 → 1日目非番強制")
                if (e, -2) in prev_duties and prev_duties[(e, -2)]:
                    if relax_level == 0:
                        for s in range(self.n_duties): model.Add(w[e, 0, s] == 0)
                    else:
                        nitetu_var = model.NewBoolVar(f"cross_nitetu_{e}")
                        duty_day1 = sum(w[e, 0, s] for s in range(self.n_duties))
                        model.Add(duty_day1 == 1).OnlyEnforceIf(nitetu_var)
                        model.Add(duty_day1 == 0).OnlyEnforceIf(nitetu_var.Not())
                        cross_month_nitetu_vars.append(nitetu_var)
        
        holiday_shift_id = self.n_shifts - 2
        for employee_id, ng_days in ng_constraints.items():
            for day in ng_days:
                if 0 <= day < n_days: model.Add(w[employee_id, day, holiday_shift_id] == 1)
        
        duty_flags = {}
        for e in range(self.n_employees):
            for d in range(n_days):
                duty_flags[e, d] = model.NewBoolVar(f"duty_{e}_{d}")
                model.Add(duty_flags[e, d] == sum(w[e, d, s] for s in range(self.n_duties)))
        
        nitetu_vars = []
        if relax_level <= 2:
            for e in range(self.n_employees):
                for d in range(n_days - 2):
                    nitetu_var = model.NewBoolVar(f"nitetu_{e}_{d}")
                    model.Add(duty_flags[e, d] + duty_flags[e, d + 2] == 2).OnlyEnforceIf(nitetu_var)
                    nitetu_vars.append(nitetu_var)
        
        nitetu_counts = []
        for e in range(self.n_employees):
            count_var = model.NewIntVar(0, n_days // 2, f"nitetu_count_{e}")
            model.Add(count_var == sum(var for var in nitetu_vars if var.Name().startswith(f"nitetu_{e}_")))
            nitetu_counts.append(count_var)
        
        nitetu_gap = 0
        if relax_level == 0 and self.n_employees > 0:
            nitetu_max = model.NewIntVar(0, n_days // 2, "nitetu_max")
            nitetu_min = model.NewIntVar(0, n_days // 2, "nitetu_min")
            model.AddMaxEquality(nitetu_max, nitetu_counts)
            model.AddMinEquality(nitetu_min, nitetu_counts)
            nitetu_gap = nitetu_max - nitetu_min
        
        relief_work_vars = []
        if self.relief_employee_id != -1:
            relief_work_vars = [w[self.relief_employee_id, d, s] for d in range(n_days) for s in range(self.n_duties)]

        relief_weight = self.weights['RELIEF'] if relax_level < 2 else self.weights['RELIEF'] // 10
        
        holiday_violations = []
        holiday_weight = self.weights['HOLIDAY'] if relax_level < 3 else self.weights['HOLIDAY'] // 10
        for emp_id, day in holidays:
            if 0 <= day < n_days:
                violation_var = model.NewBoolVar(f"holiday_violation_{emp_id}_{day}")
                model.Add(w[emp_id, day, holiday_shift_id] == 0).OnlyEnforceIf(violation_var)
                holiday_violations.append(violation_var)
        
        preference_terms = []
        if relax_level == 0:
            for (emp_id, day, shift), weight in preferences.items():
                if 0 <= day < n_days and 0 <= shift < self.n_shifts:
                    preference_terms.append(weight * w[emp_id, day, shift])
        
        objective_terms = [
            relief_weight * sum(relief_work_vars),
            holiday_weight * sum(holiday_violations),
            self.weights['NITETU'] * sum(nitetu_vars),
            self.weights['CROSS_MONTH'] * sum(cross_month_nitetu_vars)
        ]
        if nitetu_gap != 0: objective_terms.append(self.weights['N2_GAP'] * nitetu_gap)
        objective_terms.extend(preference_terms)
        model.Minimize(sum(objective_terms))
        
        return model, w, nitetu_counts, cross_month_constraints

    def solve_with_relaxation(self, n_days, ng_constraints, preferences, holidays, prev_duties=None, keijo_base_date=None):
        relax_notes = []
        for relax_level in range(4):
            model, w, nitetu_counts, cross_const = self.build_optimization_model(
                n_days, ng_constraints, preferences, holidays, relax_level, prev_duties, keijo_base_date
            )
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 30
            status = solver.Solve(model)
            
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                return relax_level, status, solver, w, nitetu_counts, relax_notes, cross_const
            relax_notes.append(self.relax_messages.get(relax_level, f"緩和レベル{relax_level}"))
        
        return 99, cp_model.INFEASIBLE, None, None, None, relax_notes, []

    def solve_schedule(self, year, month, employee_names, calendar_data, prev_schedule_data=None):
        n_days = calendar.monthrange(year, month)[1]
        self.year = year
        self.month = month
        self.setup_system(employee_names)
        
        employee_priorities = self.config_manager.get_employee_priorities()
        requirement_lines = []
        for emp_name, emp_data in calendar_data.items():
            for holiday_date in emp_data.get('holidays', []):
                if isinstance(holiday_date, date):
                    requirement_lines.append(f"{emp_name}は{holiday_date.day}日に有休希望")
            for day, duty_name in emp_data.get('duty_preferences', {}).items():
                requirement_lines.append(f"{emp_name}は{day}日に{duty_name}勤務希望")

        ng_constraints, preferences, holidays, debug_info = self.parse_requirements(
            requirement_lines, n_days, employee_priorities)
        
        prev_duties, prev_debug = self.parse_previous_month_schedule(prev_schedule_data)
        
        keijo_base_date = self.config_manager.get_keijo_base_date()

        result = self.solve_with_relaxation(n_days, ng_constraints, preferences, holidays, prev_duties, keijo_base_date)
        relax_level_used, status, solver, w, nitetu_counts, relax_notes, cross_constraints = result
        
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return {'success': False, 'error': '解を見つけられませんでした', 'debug_info': debug_info + prev_debug}

        return {
            'success': True, 'year': year, 'month': month, 'n_days': n_days,
            'relax_level': relax_level_used, 'status': status, 'solver': solver,
            'w': w, 'nitetu_counts': nitetu_counts, 'holidays': holidays,
            'relax_notes': relax_notes, 'cross_constraints': cross_constraints,
            'debug_info': debug_info + prev_debug, 'employees': employee_names
        }

# =================== Excel出力機能 ===================
# このクラスは既存のままでも機能するため、大きな変更は加えていません。
# 内部でConfigManagerを参照するように修正することも可能ですが、
# Engineから渡されるデータで完結しているため、現状維持としています。
class ExcelExporter:
    def __init__(self, engine):
        self.engine = engine
    
    def create_excel_file(self, filename, result_data):
        workbook = xlsxwriter.Workbook(filename)
        formats = self._create_formats(workbook)
        self._create_main_sheet(workbook, formats, result_data)
        self._create_stats_sheet(workbook, formats, result_data)
        workbook.close()
        return filename

    def _create_formats(self, workbook):
        return {
            'header': workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#4472C4', 'font_color': 'white', 'border': 1}),
            'holiday_ok': workbook.add_format({'bg_color': '#FFFF99', 'align': 'center', 'border': 1}),
            'holiday_violation': workbook.add_format({'bg_color': '#FFB6C1', 'align': 'center', 'border': 1}),
            'normal': workbook.add_format({'align': 'center', 'border': 1}),
            'bold': workbook.add_format({'bold': True, 'border': 1})
        }

    def _create_main_sheet(self, workbook, formats, result_data):
        worksheet = workbook.add_worksheet("勤務表")
        solver, w, holidays, employees, n_days = result_data['solver'], result_data['w'], result_data['holidays'], result_data['employees'], result_data['n_days']
        duty_names = self.engine.duty_names
        holiday_name = self.engine.config_manager.get_holiday_type()["name"]
        
        worksheet.write(0, 0, "従業員名", formats['header'])
        for day in range(n_days):
            worksheet.write(0, day + 1, f"{day + 1}日", formats['header'])
        
        for emp_id, emp_name in enumerate(employees):
            worksheet.write(emp_id + 1, 0, emp_name, formats['bold'])
            for day in range(n_days):
                shift_text = "?"
                # シフト判定ロジック
                for duty_id, name in enumerate(duty_names):
                    if solver.Value(w[emp_id, day, duty_id]):
                        shift_text = name
                        break
                if shift_text == "?":
                    if solver.Value(w[emp_id, day, self.engine.n_duties]): shift_text = "休"
                    elif solver.Value(w[emp_id, day, self.engine.OFF_SHIFT_ID]): shift_text = "-"
                
                cell_format = formats['normal']
                if (emp_id, day) in holidays:
                    cell_format = formats['holiday_ok'] if shift_text == "休" else formats['holiday_violation']
                worksheet.write(emp_id + 1, day + 1, shift_text, cell_format)
        
        worksheet.set_column(0, 0, 12)
        worksheet.set_column(1, n_days, 4)

    def _create_stats_sheet(self, workbook, formats, result_data):
        worksheet = workbook.add_worksheet("統計")
        solver, w, nitetu_counts, holidays, employees, n_days = result_data['solver'], result_data['w'], result_data['nitetu_counts'], result_data['holidays'], result_data['employees'], result_data['n_days']
        duty_names = self.engine.duty_names
        headers = ["従業員名"] + [f"{name}回数" for name in duty_names] + ["勤務数", "二徹回数", "有休希望", "有休実現"]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, formats['header'])

        for emp_id, emp_name in enumerate(employees):
            row_data = [emp_name]
            total_duty = 0
            for duty_id in range(len(duty_names)):
                count = sum(solver.Value(w[emp_id, d, duty_id]) for d in range(n_days))
                row_data.append(count)
                total_duty += count
            
            nitetu_count = solver.Value(nitetu_counts[emp_id]) if emp_id < len(nitetu_counts) else 0
            emp_holidays = {(e, d) for e, d in holidays if e == emp_id}
            holiday_satisfied = sum(1 for e, d in emp_holidays if solver.Value(w[e, d, self.engine.n_duties]))
            
            row_data.extend([total_duty, nitetu_count, len(emp_holidays), holiday_satisfied])
            for col, value in enumerate(row_data):
                worksheet.write(emp_id + 1, col, value, formats['normal'])
        
        worksheet.set_column(0, len(headers), 12)

# =================== GUI部分（統合設定版） ===================

class UnifiedGUI:
    def __init__(self):
        # セッションステートで設定マネージャを管理
        if 'config_manager' not in st.session_state:
            st.session_state.config_manager = UnifiedConfigurationManager()
            st.session_state.config_manager.initialize_default_config()

        self.config_manager = st.session_state.config_manager
        self.engine = CompleteScheduleEngine(self.config_manager)
        self.excel_exporter = ExcelExporter(self.engine)
        
        # UIの状態管理
        if 'page' not in st.session_state:
            st.session_state.page = "main" # 'main' or 'settings'
        if 'calendar_data' not in st.session_state:
            st.session_state.calendar_data = {}

    def run(self):
        st.set_page_config(page_title="勤務表システム（統合設定版）", layout="wide")
        st.title("📅 勤務表作成システム（統合設定版）")
        st.success("✅ **改善**: すべての設定を単一ファイルで管理。直感的な設定ページで混乱なく保存できます。")

        if st.session_state.page == "settings":
            self._settings_page()
        else:
            self._main_page()

    def _main_page(self):
        with st.sidebar:
            self._create_sidebar()
        
        col1, col2 = st.columns([2, 1])
        with col1:
            self._create_calendar_input()
        with col2:
            self._create_control_panel()

    def _settings_page(self):
        st.header("⚙️ 統合設定")

        if st.button("← メインページに戻る"):
            st.session_state.page = "main"
            st.rerun()

        # 現在編集中の設定ファイル名を表示
        st.info(f"編集中: **{self.config_manager.current_filename}**")

        # 編集用に現在の設定をコピー
        # これにより、UIでの変更が即座に保存されるのを防ぐ
        editable_config = self.config_manager.current_config.copy()

        tab1, tab2, tab3, tab4 = st.tabs(["勤務場所", "従業員", "優先度", "その他"])

        # --- 勤務場所タブ ---
        with tab1:
            st.subheader("勤務場所の編集")
            if 'work_locations' not in editable_config: editable_config['work_locations'] = []
            
            # 各勤務場所の編集フォーム
            for i, loc in enumerate(editable_config['work_locations']):
                with st.container(border=True):
                    cols = st.columns([2, 2, 1, 1, 1])
                    loc['name'] = cols[0].text_input("勤務場所名", value=loc.get('name', ''), key=f"loc_name_{i}")
                    loc['type'] = cols[1].selectbox("勤務タイプ", ["一徹勤務", "日勤", "夜勤"], index=0, key=f"loc_type_{i}")
                    loc['duration'] = cols[2].number_input("時間", value=loc.get('duration', 16), key=f"loc_dur_{i}")
                    loc['color'] = cols[3].color_picker("色", value=loc.get('color', '#FF6B6B'), key=f"loc_color_{i}")
                    if cols[4].button("削除", key=f"del_loc_{i}", use_container_width=True):
                        editable_config['work_locations'].pop(i)
                        self.config_manager.current_config = editable_config # 即時反映
                        st.rerun()
            
            if st.button("➕ 新しい勤務場所を追加"):
                editable_config['work_locations'].append({"name": "新規勤務", "type": "一徹勤務", "duration": 16, "color": "#87CEFA"})
                self.config_manager.current_config = editable_config
                st.rerun()

        # --- 従業員タブ ---
        with tab2:
            st.subheader("従業員の編集")
            if 'employees' not in editable_config: editable_config['employees'] = []
            employees_text = st.text_area(
                "従業員名（1行に1名, '助勤'を必ず含めてください）",
                value="\n".join(editable_config.get('employees', [])),
                height=250
            )
            editable_config['employees'] = [e.strip() for e in employees_text.split("\n") if e.strip()]

        # --- 優先度タブ ---
        with tab3:
            st.subheader("従業員別 勤務優先度設定")
            st.info("優先度: 3=最優先, 2=普通, 1=可能, 0=不可")
            if 'employee_priorities' not in editable_config: editable_config['employee_priorities'] = {}
            priority_options = ["0 (不可)", "1 (可能)", "2 (普通)", "3 (最優先)"]
            
            employees_for_priority = [e for e in editable_config.get('employees', []) if e != "助勤"]
            duty_names = [loc['name'] for loc in editable_config.get('work_locations', [])]

            for emp_name in employees_for_priority:
                if emp_name not in editable_config['employee_priorities']:
                    editable_config['employee_priorities'][emp_name] = {}
                
                with st.container(border=True):
                    st.write(f"**{emp_name}**")
                    cols = st.columns(len(duty_names))
                    for i, duty_name in enumerate(duty_names):
                        with cols[i]:
                            current_val = editable_config['employee_priorities'][emp_name].get(duty_name, 2)
                            selected = st.selectbox(duty_name, priority_options, index=current_val, key=f"p_{emp_name}_{duty_name}", label_visibility="collapsed")
                            editable_config['employee_priorities'][emp_name][duty_name] = int(selected.split(" ")[0])
        
        # --- その他タブ ---
        with tab4:
            st.subheader("警乗設定")
            base_date_val = date.fromisoformat(editable_config.get('keijo_base_date', date(2025, 6, 1).isoformat()))
            new_base_date = st.date_input("警乗隔日の起点日", value=base_date_val)
            editable_config['keijo_base_date'] = new_base_date.isoformat()

        # --- 保存アクション ---
        st.markdown("---")
        st.header("💾 保存")
        
        save_cols = st.columns(2)
        with save_cols[0]:
            if st.button("💾 上書き保存", type="primary", use_container_width=True):
                if self.config_manager.save_config(self.config_manager.current_filename, editable_config):
                    st.success(f"✅ 設定 '{self.config_manager.current_filename}' を上書き保存しました。")
                    st.session_state.page = "main" # メインページに戻る
                    st.rerun()

        with save_cols[1]:
            with st.form("save_as_form"):
                new_filename = st.text_input("新しいファイル名")
                submitted = st.form_submit_button("💾 名前を付けて保存", use_container_width=True)
                if submitted and new_filename:
                    if self.config_manager.save_config(new_filename, editable_config):
                        st.success(f"✅ 新しい設定 '{new_filename}.json'として保存しました。")
                        st.session_state.page = "main" # メインページに戻る
                        st.rerun()
                    else:
                        st.error("保存に失敗しました。")


    def _create_sidebar(self):
        st.header("コントロールパネル")

        # --- 設定ファイル選択 ---
        st.subheader("📁 設定ファイル")
        config_files = self.config_manager.get_config_files()
        
        # 現在のファイル名をセレクトボックスのデフォルトに
        try:
            current_index = config_files.index(self.config_manager.current_filename)
        except (ValueError, TypeError):
            current_index = 0

        selected_file = st.selectbox(
            "使用する設定", config_files, index=current_index,
            label_visibility="collapsed"
        )
        
        if selected_file and selected_file != self.config_manager.current_filename:
            self.config_manager.load_config(selected_file)
            st.session_state.calendar_data = {} # 設定が変わったのでカレンダーデータリセット
            st.success(f"設定 '{selected_file}' を読み込みました。")
            st.rerun()

        if st.button("⚙️ 現在の設定を編集", use_container_width=True):
            st.session_state.page = "settings"
            st.rerun()

        st.markdown("---")

        # --- 年月設定 ---
        st.subheader("🗓️ 対象年月")
        self.year = st.number_input("年", value=date.today().year, min_value=2020, max_value=2030)
        self.month = st.selectbox("月", range(1, 13), index=date.today().month-1)
        self.n_days = calendar.monthrange(self.year, self.month)[1]
        
        # --- 前月末勤務 ---
        st.subheader("🔄 前月末勤務")
        prev_month = self.month - 1 if self.month > 1 else 12
        prev_year = self.year if self.month > 1 else self.year - 1
        prev_days_in_month = calendar.monthrange(prev_year, prev_month)[1]
        
        self.prev_schedule_data = {}
        duty_options = ["未入力"] + self.config_manager.get_duty_names() + ["非番", "休"]
        
        with st.expander("前月末の勤務を入力"):
            for emp in self.config_manager.get_employees():
                self.prev_schedule_data[emp] = []
                cols = st.columns(4)
                cols[0].write(emp)
                for i in range(3):
                    day = prev_days_in_month - 2 + i
                    shift = cols[i+1].selectbox(f"{day}日", duty_options, key=f"prev_{emp}_{i}", label_visibility="collapsed")
                    self.prev_schedule_data[emp].append(shift)

    def _create_calendar_input(self):
        st.header("📅 希望入力")
        employees = self.config_manager.get_employees()
        if not employees:
            st.warning("設定ページで従業員を登録してください。")
            return
            
        selected_emp = st.selectbox("従業員を選択", employees, key="main_emp_select")
        if not selected_emp: return

        if selected_emp not in st.session_state.calendar_data:
            st.session_state.calendar_data[selected_emp] = {'holidays': [], 'duty_preferences': {}}

        current_holidays = st.session_state.calendar_data[selected_emp]['holidays']
        selected_dates = st.date_input(
            "休暇希望日（複数選択可）",
            value=[d for d in current_holidays if isinstance(d, date)],
            min_value=date(self.year, self.month, 1),
            max_value=date(self.year, self.month, self.n_days)
        )
        st.session_state.calendar_data[selected_emp]['holidays'] = selected_dates


    def _create_control_panel(self):
        st.header("🎛️ 生成制御")
        with st.container(border=True):
            st.subheader("設定サマリー")
            st.write(f"**設定名**: {self.config_manager.get_config_name()}")
            st.write(f"**従業員数**: {len(self.config_manager.get_employees())}名")
            st.write(f"**勤務場所数**: {len(self.config_manager.get_duty_names())}箇所")

            if st.button("🚀 勤務表を生成", type="primary", use_container_width=True):
                self._generate_schedule()

    def _generate_schedule(self):
        with st.spinner("勤務表を生成中..."):
            try:
                result = self.engine.solve_schedule(
                    year=self.year, month=self.month,
                    employee_names=self.config_manager.get_employees(),
                    calendar_data=st.session_state.calendar_data,
                    prev_schedule_data=self.prev_schedule_data
                )
                if result['success']:
                    st.success("✅ 勤務表が生成されました！")
                    st.session_state.last_result = result
                else:
                    st.error(f"❌ {result['error']}")
                    st.session_state.last_result = None
            except Exception as e:
                st.error(f"❌ 生成中にエラーが発生しました: {e}")
                import traceback
                st.code(traceback.format_exc())

        if st.session_state.get('last_result'):
            self._show_results(st.session_state.last_result)
            
    def _show_results(self, result):
        st.subheader(f"📋 生成された勤務表 (緩和レベル {result['relax_level']})")
        # 結果表示（DataFrameなど）
        # ...
        
        self._create_excel_download(result)

    def _create_excel_download(self, result):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                excel_path = self.excel_exporter.create_excel_file(tmp.name, result)
                with open(excel_path, 'rb') as f:
                    st.download_button(
                        "📥 Excel勤務表をダウンロード",
                        data=f.read(),
                        file_name=f"勤務表_{self.year}年{self.month:02d}月.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
            os.unlink(excel_path)
        except Exception as e:
            st.error(f"❌ Excel生成エラー: {e}")

if __name__ == "__main__":
    gui = UnifiedGUI()
    gui.run()

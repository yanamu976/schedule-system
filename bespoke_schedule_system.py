#!/usr/bin/env python3
"""
📅 としかず隊専用勤務表システム（ビスポーク版）
- 8名3勤務場所完全固定（A、D、警乗）
- 5段階優先度システム（0=不可, 1=可, 2=普通, 3=やや優先, 4=優先, 5=最優先）
- 月またぎ制約完全対応（前月末勤務処理）
- 警乗隔日制約
- Excel色分け出力
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


# =================== としかず隊専用固定設定 ===================

# 従業員（8名固定 + 助勤1名）
EMPLOYEES = ["中谷", "宮崎", "木村", "田中", "谷村", "新蔵", "川口", "杉本", "助勤"]

# 勤務場所（3箇所固定）
WORK_LOCATIONS = [
    {"name": "A", "type": "一徹勤務", "duration": 16, "color": "#FF6B6B"},
    {"name": "D", "type": "一徹勤務", "duration": 16, "color": "#FF8E8E"},  
    {"name": "警乗", "type": "一徹勤務", "duration": 16, "color": "#FFB6B6"}
]

# 優先度マトリックス（5段階）- としかず隊指定値
# 0=不可, 1=可, 2=普通, 3=やや優先, 4=優先, 5=最優先
PRIORITY_MATRIX = {
    "中谷": {"A": 2, "D": 5, "警乗": 0},  # A普通, D最優先, 警乗不可
    "宮崎": {"A": 0, "D": 0, "警乗": 5},  # A不可, D不可, 警乗最優先
    "木村": {"A": 0, "D": 5, "警乗": 0},  # A不可, D最優先, 警乗不可
    "田中": {"A": 1, "D": 4, "警乗": 0},  # A可, D優先, 警乗不可
    "谷村": {"A": 2, "D": 2, "警乗": 2},  # A普通, D普通, 警乗普通
    "新蔵": {"A": 2, "D": 1, "警乗": 2},  # A普通, D可, 警乗普通
    "川口": {"A": 2, "D": 0, "警乗": 2},  # A普通, D不可, 警乗普通
    "杉本": {"A": 5, "D": 0, "警乗": 0},  # A最優先, D不可, 警乗不可
    "助勤": {"A": 3, "D": 0, "警乗": 0}   # A対応可能, D/警乗不可（最終手段要員）
}

# 警乗隔日設定
KEIJO_BASE_DATE = date(2025, 6, 1)  # 固定起点日

# 優先度重み（5段階対応）
PRIORITY_WEIGHTS = {
    0: 1000,    # 不可（高ペナルティ）
    1: 50,      # 可
    2: 25,      # 普通
    3: 10,      # やや優先
    4: 5,       # 優先
    5: 0        # 最優先（ペナルティなし）
}

# =================== 設定管理システム（Phase 1） ===================

class ConfigurationManager:
    """Phase 1: 最小限設定管理クラス"""
    
    def __init__(self):
        self.configs_dir = "configs"
        self.ensure_configs_dir()
        
        # としかず隊専用固定設定
        self.default_config = {
            "config_name": "としかず隊専用設定",
            "created_date": datetime.now().strftime("%Y-%m-%d"),
            "work_locations": WORK_LOCATIONS,
            "holiday_type": {"name": "休暇", "color": "#FFEAA7"},
            "employees": EMPLOYEES,
            "employee_priorities": PRIORITY_MATRIX,
            "priority_weights": {str(k): v for k, v in PRIORITY_WEIGHTS.items()}
        }
        
        # 現在の設定
        self.current_config = self.default_config.copy()
    
    def ensure_configs_dir(self):
        """configs/ディレクトリの確保"""
        if not os.path.exists(self.configs_dir):
            os.makedirs(self.configs_dir)
    
    def get_config_files(self):
        """設定ファイル一覧取得"""
        if not os.path.exists(self.configs_dir):
            return []
        files = [f for f in os.listdir(self.configs_dir) if f.endswith('.json')]
        return sorted(files)
    
    def load_config(self, filename=None):
        """設定読み込み"""
        if filename is None:
            return False
        
        filepath = os.path.join(self.configs_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.current_config = config
                return True
        except Exception as e:
            print(f"設定読み込みエラー: {e}")
            return False
    
    def save_config(self, config_name, custom_priorities=None):
        """設定保存"""
        # ファイル名生成（日本語対応）
        date_str = datetime.now().strftime("%Y%m%d")
        safe_name = config_name.replace(" ", "_").replace("/", "_")
        filename = f"{safe_name}_{date_str}.json"
        filepath = os.path.join(self.configs_dir, filename)
        
        # 設定データ作成
        config_data = self.current_config.copy()
        config_data["config_name"] = config_name
        config_data["created_date"] = datetime.now().strftime("%Y-%m-%d")
        
        if custom_priorities:
            config_data["employee_priorities"] = custom_priorities
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            return filename
        except Exception as e:
            print(f"設定保存エラー: {e}")
            return None
    
    def get_work_locations(self):
        """勤務場所一覧取得"""
        return self.current_config.get("work_locations", self.default_config["work_locations"])
    
    def get_duty_names(self):
        """勤務場所名一覧"""
        locations = self.get_work_locations()
        return [loc["name"] for loc in locations]
    
    def get_employee_priorities(self):
        """従業員優先度設定取得"""
        return self.current_config.get("employee_priorities", self.default_config["employee_priorities"])
    
    def get_priority_weights(self):
        """優先度重み取得（5段階対応）"""
        return PRIORITY_WEIGHTS
    
    def update_employee_priorities(self, priorities):
        """従業員優先度更新"""
        self.current_config["employee_priorities"] = priorities
    
    def get_employees(self):
        """従業員リスト取得"""
        return EMPLOYEES
    
    def update_employees(self, employees):
        """従業員リスト更新"""
        self.current_config["employees"] = employees


class WorkLocationManager:
    """勤務場所管理クラス（既存互換性維持）"""
    
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        
        # デフォルト設定（既存互換性）
        self.default_config = {
            "duty_locations": [
                {"name": "駅A", "type": "一徹勤務", "duration": 16, "color": "#FF6B6B"},
                {"name": "指令", "type": "一徹勤務", "duration": 16, "color": "#FF8E8E"},
                {"name": "警乗", "type": "一徹勤務", "duration": 16, "color": "#FFB6B6"},
            ],
            "holiday_type": {"name": "休暇", "color": "#FFEAA7"}
        }
        
        # 設定初期化
        if self.config_manager:
            work_locations = self.config_manager.get_work_locations()
            self.duty_locations = work_locations.copy()  # コピーを作成
            self.holiday_type = self.config_manager.current_config.get("holiday_type", self.default_config["holiday_type"])
        else:
            # ファイルから直接読み込み試行
            if os.path.exists("work_locations.json"):
                self.load_config()
            else:
                self.duty_locations = self.default_config["duty_locations"].copy()
                self.holiday_type = self.default_config["holiday_type"].copy()
    
    def get_duty_locations(self):
        """勤務場所一覧取得"""
        if self.config_manager:
            return self.config_manager.get_work_locations()
        return self.duty_locations
    
    def get_duty_names(self):
        """勤務場所名一覧"""
        if self.config_manager:
            return self.config_manager.get_duty_names()
        return [loc["name"] for loc in self.duty_locations]
    
    def add_duty_location(self, name, duty_type, duration, color):
        """勤務場所追加"""
        new_location = {
            "name": name,
            "type": duty_type,
            "duration": duration,
            "color": color
        }
        self.duty_locations.append(new_location)
        
        # Config Managerにも反映
        if self.config_manager:
            self.config_manager.current_config["work_locations"] = self.duty_locations.copy()
    
    def remove_duty_location(self, index):
        """勤務場所削除"""
        if 0 <= index < len(self.duty_locations):
            del self.duty_locations[index]
            
            # Config Managerにも反映
            if self.config_manager:
                self.config_manager.current_config["work_locations"] = self.duty_locations.copy()
    
    def update_duty_location(self, index, name, duty_type, duration, color):
        """勤務場所更新"""
        if 0 <= index < len(self.duty_locations):
            self.duty_locations[index] = {
                "name": name,
                "type": duty_type,
                "duration": duration,
                "color": color
            }
            
            # Config Managerにも反映
            if self.config_manager:
                self.config_manager.current_config["work_locations"] = self.duty_locations.copy()
    
    def reset_to_default(self):
        """デフォルト設定に戻す"""
        self.duty_locations = self.default_config["duty_locations"].copy()
        self.holiday_type = self.default_config["holiday_type"].copy()
    
    def save_config(self, filename="work_locations.json"):
        """設定保存（最大15勤務対応）"""
        config = {
            "duty_locations": self.duty_locations[:15],  # 最大15勤務まで
            "holiday_type": self.holiday_type
        }
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"✅ 設定を {filename} に保存しました")
            return True
        except Exception as e:
            print(f"❌ 設定保存エラー: {e}")
            return False
    
    def load_config(self, filename="work_locations.json"):
        """設定読み込み"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 重複を削除して読み込み
                duty_locations = config.get("duty_locations", self.default_config["duty_locations"])
                self.duty_locations = self._remove_duplicates(duty_locations)
                self.holiday_type = config.get("holiday_type", self.default_config["holiday_type"])
                
                # Config Managerにも反映
                if self.config_manager:
                    self.config_manager.current_config["work_locations"] = self.duty_locations.copy()
                
                return True
        except Exception as e:
            print(f"設定読み込みエラー: {e}")
            return False
    
    def _remove_duplicates(self, duty_locations):
        """重複する勤務場所を削除"""
        seen_names = set()
        unique_locations = []
        for location in duty_locations:
            name = location.get("name", "")
            if name and name not in seen_names:
                seen_names.add(name)
                unique_locations.append(location)
        return unique_locations


# =================== 完全版エンジン ===================

class CompleteScheduleEngine:
    """完全版勤務表生成エンジン（Phase 1: 優先度対応）"""
    
    def __init__(self, location_manager, config_manager=None):
        self.location_manager = location_manager
        self.config_manager = config_manager
        
        # 非番シフトID（動的に設定）
        self.OFF_SHIFT_ID = None
        
        # 重み設定
        self.weights = {
            'RELIEF': 10,      # 助勤使用ペナルティ
            'HOLIDAY': 50,     # 有休違反ペナルティ  
            'NITETU': 15,      # 二徹ペナルティ
            'N2_GAP': 30,      # 二徹格差ペナルティ
            'PREF': 5,         # 希望違反ペナルティ
            'CROSS_MONTH': 20, # 月またぎ二徹ペナルティ
            'PRIORITY': 25     # 優先度違反ペナルティ（Phase 1新機能）
        }
        
        # 優先度重み（Phase 1）
        self.priority_weights = {0: 1000, 1: 10, 2: 5, 3: 0}  # デフォルト
        
        # 制約緩和メッセージ
        self.relax_messages = {
            0: "✅ 全制約満足",
            1: "⚠️ 助勤要員解禁（最終手段として駅Aに配置）",
            2: "⚠️ 二徹バランス緩和 + 助勤フル活用", 
            3: "⚠️ 有休の一部を勤務変更（休多→勤務優先）"
        }
    
    def update_weights(self, new_weights):
        """重みパラメータを更新"""
        self.weights.update(new_weights)
    
    def _get_keijo_shift_id(self):
        """警乗のシフトIDを取得"""
        duty_names = self.location_manager.get_duty_names()
        for i, name in enumerate(duty_names):
            if "警乗" in name:
                return i
        return None  # 警乗勤務場所が見つからない場合
    
    def _add_keijo_alternating_constraints(self, model, w, year, month, n_days, keijo_base_date=None):
        """警乗隔日制約をソフト制約（ペナルティ方式）として追加"""
        keijo_shift_id = self._get_keijo_shift_id()
        if keijo_shift_id is None:
            return [], []  # 警乗勤務場所がない場合はスキップ
        
        # デフォルト基準日（2025年6月1日）
        if keijo_base_date is None:
            return [f"🚁 警乗隔日制約: 基準日未設定のためスキップ"], []
        
        # 基準日からの日数計算
        current_month_start = datetime(year, month, 1)
        days_offset = (current_month_start - keijo_base_date).days
        
        constraint_info = []
        keijo_work_days = []
        keijo_rest_days = []
        penalty_vars = []
        
        # 制約緩和レベルに応じたペナルティ重み（大幅強化）
        relax_level = getattr(self, '_current_relax_level', 0)
        if relax_level == 0:
            penalty_weight = 10000  # 超高ペナルティ（ほぼハード制約）
        elif relax_level == 1:
            penalty_weight = 5000   # 高ペナルティ
        elif relax_level == 2:
            penalty_weight = 1000   # 中程度のペナルティ
        else:
            penalty_weight = 100    # 低ペナルティ
        
        for d in range(n_days):
            total_days = days_offset + d
            
            if total_days % 2 == 0:
                # 偶数日：警乗勤務日（1人配置が理想）
                keijo_work_days.append(d + 1)
                
                # ペナルティ変数：配置人数が1人でない場合のペナルティ
                penalty_var = model.NewIntVar(0, self.n_employees, f"keijo_penalty_work_{d}")
                keijo_count = sum(w[e, d, keijo_shift_id] for e in range(self.n_employees))
                
                # |keijo_count - 1| のペナルティを計算
                model.AddAbsEquality(penalty_var, keijo_count - 1)
                penalty_vars.append((penalty_var, penalty_weight))
                
            else:
                # 奇数日：警乗休止日（0人配置が理想）
                keijo_rest_days.append(d + 1)
                
                # ペナルティ変数：配置人数が0人でない場合のペナルティ
                penalty_var = model.NewIntVar(0, self.n_employees, f"keijo_penalty_rest_{d}")
                keijo_count = sum(w[e, d, keijo_shift_id] for e in range(self.n_employees))
                
                # keijo_count のペナルティ（0人以外の場合）
                model.Add(penalty_var == keijo_count)
                penalty_vars.append((penalty_var, penalty_weight))
        
        constraint_info.append(f"🚁 警乗隔日ソフト制約適用: 基準日{keijo_base_date.strftime('%Y-%m-%d')}")
        constraint_info.append(f"  ペナルティ重み: {penalty_weight} (制約緩和レベル{relax_level})")
        constraint_info.append(f"  警乗勤務日: {keijo_work_days[:5]}{'...' if len(keijo_work_days) > 5 else ''}")
        constraint_info.append(f"  警乗休止日: {keijo_rest_days[:5]}{'...' if len(keijo_rest_days) > 5 else ''}")
        
        return constraint_info, penalty_vars
    
    def setup_system(self, employee_names):
        """システム設定"""
        self.employees = employee_names
        self.n_employees = len(employee_names)
        self.relief_employee_id = self.n_employees - 1
        
        # 勤務場所設定
        duty_locations = self.location_manager.get_duty_locations()
        self.duty_names = [loc["name"] for loc in duty_locations]
        self.n_duties = len(self.duty_names)
        
        # シフト定義: 各勤務場所 + 休暇 + 非番
        # 非番は自動生成されるが、制約処理のために明示的なシフトとして扱う
        self.shift_names = self.duty_names + [self.location_manager.holiday_type["name"]] + ["非番"]
        self.n_shifts = len(self.shift_names)
        self.OFF_SHIFT_ID = self.n_shifts - 1  # 最後が非番
        
        # ID変換
        self.name_to_id = {name: i for i, name in enumerate(employee_names)}
        self.id_to_name = {i: name for i, name in enumerate(employee_names)}
        self.shift_name_to_id = {name: i for i, name in enumerate(self.shift_names)}
        
        print(f"🔧 システム設定:")
        print(f"  従業員: {self.n_employees}名")
        print(f"  勤務場所: {self.n_duties}箇所 - {self.duty_names}")
        print(f"  総シフト: {self.n_shifts}種類")
        print(f"  非番ID: {self.OFF_SHIFT_ID}")
    
    def parse_requirements(self, requirement_lines, n_days, employee_priorities=None):
        """要求文の解析（Phase 1: 優先度対応）"""
        ng_constraints = defaultdict(list)
        preferences = {}
        holidays = set()
        priority_violations = []  # Phase 1: 優先度違反
        debug_info = []
        
        day_pattern = re.compile(r'(\d{1,2})日')
        range_pattern = re.compile(r'(\d{1,2})日から(\d{1,2})日まで')
        
        # 勤務場所名を動的にマッピング
        duty_name_to_id = {name: i for i, name in enumerate(self.duty_names)}
        
        for line in requirement_lines:
            # 従業員特定
            employee_id = None
            employee_name = None
            for name, emp_id in self.name_to_id.items():
                if name in line:
                    employee_id = emp_id
                    employee_name = name
                    break
            
            if employee_id is None:
                debug_info.append(f"❌ 従業員名が見つかりません: {line}")
                continue
            
            # 有休・休み希望の処理
            if any(keyword in line for keyword in ("有休", "休み", "休暇")):
                # 範囲指定の処理
                range_match = range_pattern.search(line)
                if range_match:
                    start_day, end_day = map(int, range_match.groups())
                    for day in range(start_day - 1, end_day):  # 0-indexed
                        if 0 <= day < n_days:
                            holidays.add((employee_id, day))
                            debug_info.append(f"✅ {employee_name}: {day+1}日に有休追加")
                else:
                    # 個別日付の処理
                    for match in day_pattern.finditer(line):
                        day = int(match.group(1)) - 1  # 0-indexed
                        if 0 <= day < n_days:
                            holidays.add((employee_id, day))
                            debug_info.append(f"✅ {employee_name}: {day+1}日に有休追加")
            
            # 勤務場所希望の処理
            for match in day_pattern.finditer(line):
                day = int(match.group(1)) - 1  # 0-indexed
                if 0 <= day < n_days:
                    for duty_name, duty_id in duty_name_to_id.items():
                        if duty_name in line:
                            if "希望" in line:
                                preferences[(employee_id, day, duty_id)] = -self.weights['PREF']
                                debug_info.append(f"✅ {employee_name}: {day+1}日に{duty_name}勤務希望追加")
                            elif any(avoid in line for avoid in ["入りたくない", "避けたい"]):
                                preferences[(employee_id, day, duty_id)] = +self.weights['PREF']
                                debug_info.append(f"✅ {employee_name}: {day+1}日の{duty_name}勤務回避追加")
        
        # Phase 1: 優先度ペナルティ処理
        if employee_priorities and self.config_manager:
            priority_weights = self.config_manager.get_priority_weights()
            debug_info.append(f"🎯 Phase 1: 優先度重み適用 {priority_weights}")
            
            for emp_name, priorities in employee_priorities.items():
                if emp_name in self.name_to_id:
                    emp_id = self.name_to_id[emp_name]
                    for duty_name, priority in priorities.items():
                        if duty_name in [loc['name'] for loc in self.location_manager.get_duty_locations()]:
                            duty_id = [i for i, loc in enumerate(self.location_manager.get_duty_locations()) 
                                     if loc['name'] == duty_name][0]
                            penalty = priority_weights.get(priority, 0)
                            
                            # 優先度に基づいたペナルティ設定（修正版）
                            for day in range(n_days):
                                # 全ての優先度レベルを適用（0=高ペナルティ、3=低ペナルティ/報酬）
                                # 5段階優先度システム（ビスポーク版完全対応）
                                if priority == 0:  # 不可 - 高ペナルティ
                                    preferences[(emp_id, day, duty_id)] = penalty  # 1000
                                elif priority == 1:  # 可 - 中ペナルティ
                                    preferences[(emp_id, day, duty_id)] = penalty  # 50
                                elif priority == 2:  # 普通 - 小ペナルティ
                                    preferences[(emp_id, day, duty_id)] = penalty  # 25
                                elif priority == 3:  # やや優先 - 軽い報酬
                                    preferences[(emp_id, day, duty_id)] = -50  # 軽い報酬でやや優先配置
                                elif priority == 4:  # 優先 - 強い報酬
                                    preferences[(emp_id, day, duty_id)] = -200  # 強い報酬で優先配置
                                elif priority == 5:  # 最優先 - 強力な報酬
                                    preferences[(emp_id, day, duty_id)] = -500  # 超強力な報酬で絶対優先配置
                                    
                            # デバッグ情報強化
                            if priority >= 4:  # 優先・最優先のみログ
                                reward_penalty = preferences[(emp_id, day, duty_id)]
                                debug_info.append(f"🎯 {emp_name}:{duty_name}優先度{priority}(報酬{reward_penalty})強力適用")
        
        return ng_constraints, preferences, holidays, debug_info
    
    def parse_previous_month_schedule(self, prev_schedule_data, prev_month_last_days=3):
        """
        前月末勤務情報の解析（完全修正版）
        
        Args:
            prev_schedule_data: {従業員名: [シフト情報]} の辞書
            prev_month_last_days: 前月末何日分を考慮するか（デフォルト3日）
        
        Returns:
            prev_duties: {(emp_id, relative_day): is_duty} の辞書
            debug_info: デバッグ情報のリスト
        """
        prev_duties = {}
        debug_info = []
        
        debug_info.append(f"🔍 前月末勤務解析開始（{prev_month_last_days}日分）")
        
        for employee_name, schedule_data in prev_schedule_data.items():
            if employee_name not in self.name_to_id:
                debug_info.append(f"❌ 未知の従業員: {employee_name}")
                continue
            
            emp_id = self.name_to_id[employee_name]
            debug_info.append(f"🔍 {employee_name}(ID:{emp_id})の前月末勤務: {schedule_data}")
            
            for i, shift in enumerate(schedule_data):
                if shift == "未入力":
                    continue  # 未入力は無視
                
                # 🔥 修正: 正しい相対日計算
                # i=0 → -3日前、i=1 → -2日前、i=2 → -1日前（前日）
                relative_day = -(prev_month_last_days - i)
                
                # 勤務判定（勤務場所名または旧形式A/B/Cを考慮）
                is_duty = shift in self.duty_names or shift in ['A', 'B', 'C']
                
                prev_duties[(emp_id, relative_day)] = is_duty
                
                day_label = f"前月末{abs(relative_day)}日前"
                duty_status = "勤務" if is_duty else "非勤務"
                debug_info.append(f"  {day_label}({shift}) → relative_day={relative_day}, {duty_status}")
                
                # 🔥 重要: 前日勤務チェック
                if relative_day == -1 and is_duty:
                    debug_info.append(f"⚠️ {employee_name}は前日({shift})勤務 → {self.month}月1日は非番必須")
        
        debug_info.append(f"📊 前月末勤務データ: {len(prev_duties)}件")
        return prev_duties, debug_info
    
    def build_optimization_model(self, n_days, ng_constraints, preferences, holidays, 
                                relax_level=0, prev_duties=None, keijo_base_date=None):
        """最適化モデル構築（月またぎ制約修正版）"""
        model = cp_model.CpModel()
        
        # 決定変数: w[employee, day, shift]
        w = {}
        for e in range(self.n_employees):
            for d in range(n_days):
                for s in range(self.n_shifts):
                    w[e, d, s] = model.NewBoolVar(f"w_{e}_{d}_{s}")
        
        # 基本制約1: 各従業員は1日1シフト
        for e in range(self.n_employees):
            for d in range(n_days):
                model.AddExactlyOne(w[e, d, s] for s in range(self.n_shifts))
        
        # 基本制約2: 各勤務場所は1日1人（警乗隔日制約を考慮）
        keijo_shift_id = self._get_keijo_shift_id()
        for d in range(n_days):
            for s in range(self.n_duties):
                if s == keijo_shift_id and keijo_base_date is not None:
                    # 警乗の場合は隔日制約により0人または1人
                    current_month_start = datetime(self.year, self.month, 1)
                    days_offset = (current_month_start - keijo_base_date).days
                    total_days = days_offset + d
                    
                    if total_days % 2 == 0:
                        # 偶数日：警乗勤務日（必ず1人）
                        model.Add(sum(w[e, d, s] for e in range(self.n_employees)) == 1)
                    else:
                        # 奇数日：警乗休止日（必ず0人）
                        model.Add(sum(w[e, d, s] for e in range(self.n_employees)) == 0)
                else:
                    # 警乗以外または警乗隔日制約なしの場合は通常通り1人
                    model.Add(sum(w[e, d, s] for e in range(self.n_employees)) == 1)
        
        # 基本制約3: 勤務後は翌日非番
        for e in range(self.n_employees):
            for d in range(n_days - 1):
                for s in range(self.n_duties):  # 各勤務場所について
                    model.AddImplication(w[e, d, s], w[e, d + 1, self.OFF_SHIFT_ID])
        
        # 基本制約4: 非番の前日は勤務
        for e in range(self.n_employees):
            for d in range(1, n_days):
                duty_prev_day = sum(w[e, d - 1, s] for s in range(self.n_duties))
                model.Add(duty_prev_day >= w[e, d, self.OFF_SHIFT_ID])
        
        # 基本制約5: 連続非番禁止
        for e in range(self.n_employees):
            for d in range(n_days - 1):
                model.Add(w[e, d, self.OFF_SHIFT_ID] + w[e, d + 1, self.OFF_SHIFT_ID] <= 1)
        
        # 🆕 警乗隔日制約情報の取得（基本制約2で実装済み）
        if keijo_base_date is not None:
            current_month_start = datetime(self.year, self.month, 1)
            days_offset = (current_month_start - keijo_base_date).days
            keijo_work_days = [d+1 for d in range(n_days) if (days_offset + d) % 2 == 0]
            keijo_rest_days = [d+1 for d in range(n_days) if (days_offset + d) % 2 == 1]
            
            keijo_constraint_info = [
                f"🚁 警乗隔日制約適用: 基準日{keijo_base_date.strftime('%Y-%m-%d')}",
                f"  警乗勤務日: {keijo_work_days[:5]}{'...' if len(keijo_work_days) > 5 else ''}",
                f"  警乗休止日: {keijo_rest_days[:5]}{'...' if len(keijo_rest_days) > 5 else ''}"
            ]
            keijo_penalty_vars = []  # ハード制約なのでペナルティなし
        else:
            keijo_constraint_info = ["🚁 警乗隔日制約: 基準日未設定のためスキップ"]
            keijo_penalty_vars = []
        
        # 🔥 月またぎ制約（完全修正版）
        cross_month_constraints = []
        cross_month_nitetu_vars = []
        
        if prev_duties:
            for e in range(self.n_employees):
                emp_name = self.id_to_name[e]
                
                # 制約1: 前日勤務なら1日目は必ず非番
                if (e, -1) in prev_duties and prev_duties[(e, -1)]:
                    model.Add(w[e, 0, self.OFF_SHIFT_ID] == 1)
                    cross_month_constraints.append(f"⚠️ {emp_name}: 前日勤務 → 1日目強制非番（配置機会減少）")
                
                # 制約2: 月またぎ二徹制約
                if (e, -2) in prev_duties and prev_duties[(e, -2)]:
                    if relax_level == 0:
                        # 厳格モード: 前々日勤務なら1日目勤務禁止
                        for s in range(self.n_duties):
                            model.Add(w[e, 0, s] == 0)
                        cross_month_constraints.append(f"{emp_name}: 前々日勤務 → 1日目勤務禁止（厳格）")
                    else:
                        # 緩和モード: ペナルティとして扱う
                        nitetu_var = model.NewBoolVar(f"cross_nitetu_{e}")
                        duty_day1 = sum(w[e, 0, s] for s in range(self.n_duties))
                        model.Add(duty_day1 == 1).OnlyEnforceIf(nitetu_var)
                        model.Add(duty_day1 == 0).OnlyEnforceIf(nitetu_var.Not())
                        cross_month_nitetu_vars.append(nitetu_var)
                        cross_month_constraints.append(f"{emp_name}: 前々日勤務 → 1日目勤務ペナルティ（緩和）")
                
                # 制約3: 三徹絶対禁止
                if ((e, -3) in prev_duties and prev_duties[(e, -3)] and
                    (e, -1) in prev_duties and prev_duties[(e, -1)]):
                    for s in range(self.n_duties):
                        model.Add(w[e, 0, s] == 0)
                    cross_month_constraints.append(f"{emp_name}: 三徹防止 → 1日目勤務絶対禁止")
        
        # 優先度0（不可）の絶対制約 - ビスポーク版追加
        priority_constraints = []
        for emp_name, priorities in PRIORITY_MATRIX.items():
            if emp_name in self.employees:
                emp_id = self.employees.index(emp_name)
                for duty_name, priority in priorities.items():
                    if priority == 0:  # 不可の場合
                        duty_names = [loc["name"] for loc in WORK_LOCATIONS]
                        if duty_name in duty_names:
                            duty_id = duty_names.index(duty_name)
                            # 該当勤務への配置を絶対禁止
                            for day in range(n_days):
                                model.Add(w[emp_id, day, duty_id] == 0)
                            priority_constraints.append(f"🚫 {emp_name}:{duty_name}絶対禁止制約適用")
        
        # NG制約（絶対制約）
        holiday_shift_id = self.n_shifts - 2  # 休暇シフトID（非番の前）
        for employee_id, ng_days in ng_constraints.items():
            for day in ng_days:
                if 0 <= day < n_days:
                    model.Add(w[employee_id, day, holiday_shift_id] == 1)
        
        # 勤務フラグ変数
        duty_flags = {}
        for e in range(self.n_employees):
            for d in range(n_days):
                duty_flags[e, d] = model.NewBoolVar(f"duty_{e}_{d}")
                duty_sum = sum(w[e, d, s] for s in range(self.n_duties))
                model.Add(duty_flags[e, d] == duty_sum)
        
        # 月内二徹制約
        nitetu_vars = []
        if relax_level <= 2:
            for e in range(self.n_employees):
                for d in range(n_days - 2):
                    nitetu_var = model.NewBoolVar(f"nitetu_{e}_{d}")
                    model.Add(duty_flags[e, d] + duty_flags[e, d + 2] == 2).OnlyEnforceIf(nitetu_var)
                    model.Add(duty_flags[e, d] + duty_flags[e, d + 2] <= 1).OnlyEnforceIf(nitetu_var.Not())
                    nitetu_vars.append(nitetu_var)
                
                # 四徹以上の防止
                if relax_level == 0:
                    for d in range(n_days - 4):
                        model.Add(duty_flags[e, d] + duty_flags[e, d + 2] + duty_flags[e, d + 4] <= 2)
        
        # 二徹カウント変数
        nitetu_counts = []
        for e in range(self.n_employees):
            count_var = model.NewIntVar(0, n_days // 2, f"nitetu_count_{e}")
            employee_nitetu = [var for var in nitetu_vars if var.Name().startswith(f"nitetu_{e}_")]
            employee_cross_nitetu = [var for var in cross_month_nitetu_vars if var.Name().startswith(f"cross_nitetu_{e}")]
            all_nitetu = employee_nitetu + employee_cross_nitetu
            
            if all_nitetu:
                model.Add(count_var == sum(all_nitetu))
            else:
                model.Add(count_var == 0)
            nitetu_counts.append(count_var)
        
        # 二徹格差制約
        nitetu_gap = 0
        if relax_level == 0:
            nitetu_max = model.NewIntVar(0, n_days // 2, "nitetu_max")
            nitetu_min = model.NewIntVar(0, n_days // 2, "nitetu_min")
            model.AddMaxEquality(nitetu_max, nitetu_counts)
            model.AddMinEquality(nitetu_min, nitetu_counts)
            nitetu_gap = nitetu_max - nitetu_min
        
        # 助勤制約
        relief_work_vars = [w[self.relief_employee_id, d, s] 
                           for d in range(n_days) for s in range(self.n_duties)]
        # ビスポーク版：助勤要員をより積極的に活用
        if relax_level == 0:
            relief_weight = self.weights['RELIEF'] * 5  # レベル0では高ペナルティ（使用回避）
        elif relax_level == 1:
            relief_weight = self.weights['RELIEF'] // 2  # レベル1で助勤解禁（ペナルティ半減）
        else:
            relief_weight = 1  # レベル2以降は最低ペナルティ（積極活用）
        
        # 有休制約
        holiday_violations = []
        holiday_weight = self.weights['HOLIDAY'] if relax_level < 3 else self.weights['HOLIDAY'] // 10
        for emp_id, day in holidays:
            if 0 <= day < n_days:
                violation_var = model.NewBoolVar(f"holiday_violation_{emp_id}_{day}")
                model.Add(w[emp_id, day, holiday_shift_id] == 0).OnlyEnforceIf(violation_var)
                model.Add(w[emp_id, day, holiday_shift_id] == 1).OnlyEnforceIf(violation_var.Not())
                holiday_violations.append(violation_var)
        
        # 希望制約
        preference_terms = []
        if relax_level == 0:
            for (emp_id, day, shift), weight in preferences.items():
                if 0 <= day < n_days and 0 <= shift < self.n_shifts:
                    preference_terms.append(weight * w[emp_id, day, shift])
        
        # 警乗隔日ペナルティ項
        keijo_penalty_terms = []
        for penalty_var, weight in keijo_penalty_vars:
            keijo_penalty_terms.append(weight * penalty_var)
        
        # 目的関数
        objective_terms = [
            relief_weight * sum(relief_work_vars),
            holiday_weight * sum(holiday_violations),
            self.weights['NITETU'] * sum(nitetu_vars),
            self.weights['CROSS_MONTH'] * sum(cross_month_nitetu_vars)
        ]
        
        if nitetu_gap != 0:
            objective_terms.append(self.weights['N2_GAP'] * nitetu_gap)
        
        # 警乗隔日ペナルティを追加
        objective_terms.extend(keijo_penalty_terms)
        objective_terms.extend(preference_terms)
        model.Minimize(sum(objective_terms))
        
        # 制約情報に警乗制約を追加
        all_constraints = cross_month_constraints + keijo_constraint_info
        
        return model, w, nitetu_counts, all_constraints
    
    def solve_with_relaxation(self, n_days, ng_constraints, preferences, holidays, prev_duties=None, keijo_base_date=None):
        """段階的制約緩和による求解"""
        relax_notes = []
        cross_constraints = []
        
        for relax_level in range(4):
            # レベル3では有休を削減
            holidays_to_use = holidays
            if relax_level == 3:
                holidays_to_use, reduction_note = self.reduce_holidays(holidays)
                if reduction_note:
                    relax_notes.append(reduction_note)
            
            # モデル構築
            model, w, nitetu_counts, cross_const = self.build_optimization_model(
                n_days, ng_constraints, preferences, holidays_to_use, relax_level, prev_duties, keijo_base_date
            )
            cross_constraints = cross_const
            
            # 求解
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 30
            status = solver.Solve(model)
            
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                return relax_level, status, solver, w, nitetu_counts, relax_notes, cross_constraints
            
            relax_notes.append(self.relax_messages[relax_level])
        
        # すべてのレベルで解けない場合
        return 99, cp_model.INFEASIBLE, None, None, None, relax_notes, cross_constraints
    
    def reduce_holidays(self, holidays, max_remove=2):
        """有休削減（最も多い人から削減）"""
        holiday_by_employee = defaultdict(list)
        for emp_id, day in holidays:
            holiday_by_employee[emp_id].append(day)
        
        if not holiday_by_employee:
            return holidays, ""
        
        # 最も有休が多い従業員
        max_employee = max(holiday_by_employee, key=lambda e: len(holiday_by_employee[e]))
        removed_holidays = set()
        
        # 最大max_remove件まで削除
        for day in sorted(holiday_by_employee[max_employee])[:max_remove]:
            removed_holidays.add((max_employee, day))
        
        reduced_holidays = set((e, d) for (e, d) in holidays if (e, d) not in removed_holidays)
        
        emp_name = self.id_to_name[max_employee]
        removed_days = [d + 1 for d in sorted(holiday_by_employee[max_employee])[:max_remove]]
        note = f"有休削減: {emp_name}の有休{removed_days}を勤務化"
        
        return reduced_holidays, note
    
    def analyze_cross_month_constraints(self, prev_duties, solver, w, n_days):
        """月またぎ制約の分析（簡略表記版）"""
        results = []
        
        for emp_id in range(self.n_employees):
            emp_name = self.id_to_name[emp_id]
            
            # 前月末情報
            prev_info = []
            for day in [-3, -2, -1]:
                if (emp_id, day) in prev_duties:
                    status = "勤務" if prev_duties[(emp_id, day)] else "非勤務"
                    date_label = f"前月末{abs(day)}日前"
                    prev_info.append(f"{date_label}: {status}")
                else:
                    prev_info.append(f"前月末{abs(day)}日前: データなし")
            
            # 当月初情報（簡略表記）
            current_info = []
            for day in range(min(3, n_days)):
                shift = "?"
                for s in range(self.n_duties):
                    if solver.Value(w[emp_id, day, s]):
                        shift = self.duty_names[s]
                        break
                if shift == "?" and solver.Value(w[emp_id, day, self.OFF_SHIFT_ID]):
                    shift = "-"  # 簡略表記
                elif shift == "?" and solver.Value(w[emp_id, day, self.n_shifts - 2]):
                    shift = "休"  # 簡略表記
                current_info.append(f"{day+1}日: {shift}")
            
            # 制約違反チェック
            violations = []
            constraints_applied = []
            
            # 前日勤務→1日目非番チェック
            if (emp_id, -1) in prev_duties and prev_duties[(emp_id, -1)]:
                if solver.Value(w[emp_id, 0, self.OFF_SHIFT_ID]):
                    constraints_applied.append("✅ 前日勤務→1日目非番 (正常)")
                else:
                    violations.append("❌ 前日勤務なのに1日目が非番でない")
            
            # 月またぎ二徹チェック
            if (emp_id, -2) in prev_duties and prev_duties[(emp_id, -2)]:
                duty_day1 = any(solver.Value(w[emp_id, 0, s]) for s in range(self.n_duties))
                if duty_day1:
                    violations.append("⚠️ 前々日勤務+1日目勤務=月またぎ二徹")
                else:
                    constraints_applied.append("✅ 前々日勤務だが1日目非勤務 (二徹回避)")
            
            # 三徹チェック
            if ((emp_id, -3) in prev_duties and prev_duties[(emp_id, -3)] and
                (emp_id, -1) in prev_duties and prev_duties[(emp_id, -1)]):
                duty_day1 = any(solver.Value(w[emp_id, 0, s]) for s in range(self.n_duties))
                if duty_day1:
                    violations.append("❌ 三徹発生（3日前+前日+1日目勤務）")
                else:
                    constraints_applied.append("✅ 三徹防止制約適用")
            
            # デフォルト値
            if not violations:
                violations.append("制約違反なし")
            if not constraints_applied:
                constraints_applied.append("特別制約なし")
            
            results.append({
                'name': emp_name,
                'prev_month': prev_info,
                'current_month': current_info,
                'violations': violations,
                'constraints_applied': constraints_applied
            })
        
        return results
    
    def solve_schedule(self, year, month, employee_names, calendar_data, prev_schedule_data=None, keijo_base_date=None):
        """スケジュール求解（Phase 1: 優先度対応版）"""
        n_days = calendar.monthrange(year, month)[1]
        self.year = year
        self.month = month
        self.setup_system(employee_names)
        
        # 分析機能のためにカレンダーデータを保存
        self._last_calendar_data = calendar_data
        
        # Phase 1: 従業員優先度取得
        employee_priorities = None
        if self.config_manager:
            employee_priorities = self.config_manager.get_employee_priorities()
            self.priority_weights = self.config_manager.get_priority_weights()
        
        # カレンダーデータから要求文生成
        requirement_lines = []
        for emp_name, emp_data in calendar_data.items():
            # 休暇希望
            for holiday_date in emp_data.get('holidays', []):
                if isinstance(holiday_date, date):
                    day = holiday_date.day
                    requirement_lines.append(f"{emp_name}は{day}日に有休希望")
            
            # 勤務場所希望
            for day, duty_name in emp_data.get('duty_preferences', {}).items():
                requirement_lines.append(f"{emp_name}は{day}日に{duty_name}勤務希望")
        
        # データ解析（Phase 1: 優先度適用）
        ng_constraints, preferences, holidays, debug_info = self.parse_requirements(
            requirement_lines, n_days, employee_priorities)
        
        # 前月末勤務解析
        prev_duties = None
        prev_debug = []
        if prev_schedule_data:
            prev_duties, prev_debug = self.parse_previous_month_schedule(prev_schedule_data)
        
        # 最適化実行
        result = self.solve_with_relaxation(n_days, ng_constraints, preferences, holidays, prev_duties, keijo_base_date)
        relax_level_used, status, solver, w, nitetu_counts, relax_notes, cross_constraints = result
        
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            # 原因分析機能（後付け分析方式）
            try:
                from failure_analyzer import FailureAnalyzer
                analyzer = FailureAnalyzer()
                
                # 分析に必要なデータを収集
                # 実際の勤務場所数を取得（全勤務場所）
                work_locations = self.location_manager.get_duty_locations()
                work_locations_count = len(work_locations)
                
                constraints_data = {'work_locations_count': work_locations_count}
                
                analysis_reason, analysis_detail, analysis_solutions = analyzer.analyze_failure_reason(
                    debug_info=debug_info + prev_debug,
                    constraints_data=constraints_data,
                    year=year,
                    month=month,
                    employee_names=employee_names,
                    calendar_data=calendar_data,
                    prev_schedule_data=prev_schedule_data
                )
                
                return {
                    'success': False,
                    'error': '解を見つけられませんでした',
                    'debug_info': debug_info + prev_debug,
                    'failure_analysis': {
                        'reason': analysis_reason,
                        'detail': analysis_detail,
                        'solutions': analysis_solutions
                    }
                }
            except Exception as analyzer_error:
                # 分析機能でエラーが発生しても既存の動作を保持
                return {
                    'success': False,
                    'error': '解を見つけられませんでした',
                    'debug_info': debug_info + prev_debug
                }
        
        # 月またぎ制約分析
        cross_analysis = []
        if prev_duties:
            cross_analysis = self.analyze_cross_month_constraints(prev_duties, solver, w, n_days)
        
        # 成功結果
        return {
            'success': True,
            'year': year,
            'month': month,
            'n_days': n_days,
            'relax_level': relax_level_used,
            'status': status,
            'solver': solver,
            'w': w,
            'nitetu_counts': nitetu_counts,
            'holidays': holidays,
            'preferences': preferences,
            'prev_duties': prev_duties,
            'relax_notes': relax_notes,
            'cross_constraints': cross_constraints,
            'cross_analysis': cross_analysis,
            'debug_info': debug_info + prev_debug,
            'employees': employee_names,
            'location_manager': self.location_manager
        }


# =================== Excel出力機能 ===================

class ExcelExporter:
    """Excel出力機能"""
    
    def __init__(self, engine):
        self.engine = engine
    
    def create_excel_file(self, filename, result_data):
        """完全なExcelファイル生成"""
        workbook = xlsxwriter.Workbook(filename)
        
        # フォーマット定義
        formats = self._create_formats(workbook)
        
        # メインシート作成
        self._create_main_sheet(workbook, formats, result_data)
        
        # 統計シート作成
        self._create_stats_sheet(workbook, formats, result_data)
        
        # 月またぎ分析シート作成
        if result_data.get('prev_duties'):
            self._create_cross_month_sheet(workbook, formats, result_data)
        
        # 制約緩和レポートシート作成
        self._create_relaxation_sheet(workbook, formats, result_data)
        
        workbook.close()
        return filename
    
    def _create_formats(self, workbook):
        """Excelフォーマット定義"""
        return {
            'header': workbook.add_format({
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1
            }),
            'holiday_ok': workbook.add_format({
                'bg_color': '#FFFF99',  # 黄色：有休実現
                'align': 'center',
                'border': 1
            }),
            'holiday_violation': workbook.add_format({
                'bg_color': '#FFB6C1',  # ピンク：有休希望なのに勤務
                'align': 'center',
                'border': 1
            }),
            'relief_work': workbook.add_format({
                'bg_color': '#99CCFF',  # 青：助勤勤務
                'align': 'center',
                'border': 1
            }),
            'preference_miss': workbook.add_format({
                'bg_color': '#FFE4B5',  # オレンジ：希望未実現
                'align': 'center',
                'border': 1
            }),
            'cross_month_constraint': workbook.add_format({
                'bg_color': '#E6E6FA',  # 紫：月またぎ制約
                'align': 'center',
                'border': 1
            }),
            'normal': workbook.add_format({
                'align': 'center',
                'border': 1
            }),
            'bold': workbook.add_format({
                'bold': True,
                'border': 1
            })
        }
    
    def _create_main_sheet(self, workbook, formats, result_data):
        """メインの勤務表シート"""
        worksheet = workbook.add_worksheet("勤務表")
        
        solver = result_data['solver']
        w = result_data['w']
        holidays = result_data['holidays']
        preferences = result_data['preferences']
        prev_duties = result_data.get('prev_duties', {})
        cross_constraints = result_data.get('cross_constraints', [])
        employees = result_data['employees']
        n_days = result_data['n_days']
        location_manager = result_data['location_manager']
        
        duty_names = location_manager.get_duty_names()
        holiday_name = location_manager.holiday_type["name"]
        
        # ヘッダー行
        worksheet.write(0, 0, "従業員名", formats['header'])
        for day in range(n_days):
            worksheet.write(0, day + 1, f"{day + 1}日", formats['header'])
        
        # 各従業員の勤務表
        for emp_id, emp_name in enumerate(employees):
            worksheet.write(emp_id + 1, 0, emp_name, formats['bold'])
            
            for day in range(n_days):
                # シフト値取得
                shift_value, shift_text = self._get_shift_value_and_text(solver, w, emp_id, day, duty_names, holiday_name)
                
                # 色分け判定
                cell_format = self._determine_cell_format(
                    formats, emp_id, day, shift_value, shift_text,
                    holidays, preferences, prev_duties, cross_constraints,
                    employees, solver, w, duty_names
                )
                
                worksheet.write(emp_id + 1, day + 1, shift_text, cell_format)
        
        # 列幅調整
        worksheet.set_column(0, 0, 12)  # 従業員名列
        worksheet.set_column(1, n_days, 4)  # 日付列
    
    def _get_shift_value_and_text(self, solver, w, emp_id, day, duty_names, holiday_name):
        """シフト値とテキストを取得（簡略表記版）"""
        # 勤務場所をチェック
        for duty_id, duty_name in enumerate(duty_names):
            if solver.Value(w[emp_id, day, duty_id]):
                return duty_id, duty_name
        
        # 休暇をチェック
        holiday_shift_id = len(duty_names)
        if solver.Value(w[emp_id, day, holiday_shift_id]):
            return holiday_shift_id, "休"  # 簡略表記
        
        # 非番をチェック
        off_shift_id = self.engine.OFF_SHIFT_ID
        if solver.Value(w[emp_id, day, off_shift_id]):
            return off_shift_id, "-"  # 簡略表記
        
        return -1, "?"
    
    def _determine_cell_format(self, formats, emp_id, day, shift_value, shift_text,
                              holidays, preferences, prev_duties, cross_constraints,
                              employees, solver, w, duty_names):
        """セルの色分け判定（簡略表記対応）"""
        
        # 1. 有休関連の色分け（最優先）
        if (emp_id, day) in holidays:
            if shift_text == "休":  # 簡略表記
                return formats['holiday_ok']  # 黄色：有休実現
            else:
                return formats['holiday_violation']  # ピンク：有休希望なのに勤務
        
        # 2. 助勤勤務（青色）
        if emp_id == len(employees) - 1 and shift_text in duty_names:
            return formats['relief_work']
        
        # 3. 月またぎ制約による配置（紫色）
        if prev_duties and day <= 2:
            emp_name = employees[emp_id]
            # 前日勤務→1日目非番の場合
            if ((emp_id, -1) in prev_duties and prev_duties[(emp_id, -1)] and 
                day == 0 and shift_text == "-"):  # 簡略表記
                return formats['cross_month_constraint']
            # その他の月またぎ制約
            elif (day == 0 and cross_constraints and 
                  any(constraint.startswith(emp_name) for constraint in cross_constraints)):
                return formats['cross_month_constraint']
        
        # 4. シフト希望未実現（オレンジ色）
        for duty_id in range(len(duty_names)):
            if ((emp_id, day, duty_id) in preferences and 
                preferences[(emp_id, day, duty_id)] < 0 and  # 希望
                not solver.Value(w[emp_id, day, duty_id])):  # 実現されていない
                return formats['preference_miss']
        
        # 5. 通常フォーマット
        return formats['normal']
    
    def _create_stats_sheet(self, workbook, formats, result_data):
        """統計シート作成"""
        worksheet = workbook.add_worksheet("統計")
        
        solver = result_data['solver']
        w = result_data['w']
        nitetu_counts = result_data['nitetu_counts']
        holidays = result_data['holidays']
        preferences = result_data['preferences']
        employees = result_data['employees']
        n_days = result_data['n_days']
        relax_level = result_data['relax_level']
        status = result_data['status']
        location_manager = result_data['location_manager']
        
        duty_names = location_manager.get_duty_names()
        
        # ヘッダー
        headers = ["従業員名"] + [f"{name}回数" for name in duty_names] + [
            "勤務数", "二徹回数", "有休希望", "有休実現", "有休実現率%", "シフト希望", "シフト実現", "解の品質"]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, formats['header'])
        
        # 各従業員の統計
        for emp_id, emp_name in enumerate(employees):
            # 各勤務場所回数
            duty_counts = []
            total_duty_count = 0
            for duty_id in range(len(duty_names)):
                count = sum(solver.Value(w[emp_id, day, duty_id]) for day in range(n_days))
                duty_counts.append(count)
                total_duty_count += count
            
            # 二徹回数
            nitetu_count = solver.Value(nitetu_counts[emp_id]) if emp_id < len(nitetu_counts) else 0
            
            # 有休統計
            emp_holidays = [(e, d) for (e, d) in holidays if e == emp_id]
            holiday_shift_id = len(duty_names)
            holiday_satisfied = sum(1 for (e, d) in emp_holidays 
                                  if solver.Value(w[e, d, holiday_shift_id]))
            holiday_rate = (holiday_satisfied / len(emp_holidays) * 100) if emp_holidays else 100
            
            # シフト希望統計
            emp_shift_prefs = [(e, d, s) for (e, d, s) in preferences.keys() 
                              if e == emp_id and preferences[(e, d, s)] < 0]
            shift_satisfied = sum(1 for (e, d, s) in emp_shift_prefs 
                                if solver.Value(w[e, d, s]))
            
            # 解の品質
            quality = f"Lv{relax_level} - {solver.StatusName(status)}"
            
            # データ書き込み
            row_data = [emp_name] + duty_counts + [
                total_duty_count, nitetu_count, len(emp_holidays), holiday_satisfied, 
                f"{holiday_rate:.1f}%", len(emp_shift_prefs), shift_satisfied, quality]
            
            for col, value in enumerate(row_data):
                worksheet.write(emp_id + 1, col, value, formats['normal'])
        
        # 列幅調整
        worksheet.set_column(0, 0, 12)
        worksheet.set_column(1, len(headers) - 1, 10)
    
    def _create_cross_month_sheet(self, workbook, formats, result_data):
        """月またぎ制約分析シート"""
        worksheet = workbook.add_worksheet("月またぎ制約分析")
        
        cross_analysis = result_data.get('cross_analysis', [])
        cross_constraints = result_data.get('cross_constraints', [])
        
        # タイトル
        worksheet.write(0, 0, "月またぎ制約分析レポート", formats['header'])
        
        # 分析テーブルヘッダー
        headers = ["従業員", "前月末状況", "当月初状況", "制約違反", "適用制約"]
        for col, header in enumerate(headers):
            worksheet.write(2, col, header, formats['header'])
        
        # 分析データ
        for row, analysis in enumerate(cross_analysis):
            worksheet.write(row + 3, 0, analysis['name'], formats['normal'])
            worksheet.write(row + 3, 1, "; ".join(analysis['prev_month']), formats['normal'])
            worksheet.write(row + 3, 2, "; ".join(analysis['current_month']), formats['normal'])
            worksheet.write(row + 3, 3, "; ".join(analysis['violations']), formats['normal'])
            worksheet.write(row + 3, 4, "; ".join(analysis['constraints_applied']), formats['normal'])
        
        # 制約サマリー
        summary_row = len(cross_analysis) + 5
        worksheet.write(summary_row, 0, "適用制約サマリー", formats['header'])
        
        if cross_constraints:
            for i, constraint in enumerate(cross_constraints):
                worksheet.write(summary_row + 1 + i, 0, constraint, formats['normal'])
        else:
            worksheet.write(summary_row + 1, 0, "月またぎ制約なし", formats['normal'])
        
        # 列幅調整
        worksheet.set_column(0, 0, 12)
        worksheet.set_column(1, 4, 25)
    
    def _create_relaxation_sheet(self, workbook, formats, result_data):
        """制約緩和レポートシート"""
        worksheet = workbook.add_worksheet("制約緩和レポート")
        
        relax_notes = result_data.get('relax_notes', [])
        debug_info = result_data.get('debug_info', [])
        
        # タイトル
        worksheet.write(0, 0, "制約緩和レポート", formats['header'])
        
        # 緩和メッセージ
        if relax_notes:
            worksheet.write(2, 0, "制約緩和内容:", formats['bold'])
            for i, note in enumerate(relax_notes):
                worksheet.write(3 + i, 0, note, formats['normal'])
        else:
            worksheet.write(2, 0, "制約緩和なし", formats['normal'])
        
        # デバッグ情報
        debug_start_row = len(relax_notes) + 5
        worksheet.write(debug_start_row, 0, "詳細デバッグ情報:", formats['bold'])
        
        for i, info in enumerate(debug_info):
            worksheet.write(debug_start_row + 1 + i, 0, info, formats['normal'])
        
        # 列幅調整
        worksheet.set_column(0, 0, 80)


# =================== GUI部分（完全版） ===================

class CompleteGUI:
    """完全版GUI（Phase 1: 設定管理対応）"""
    
    def __init__(self):
        # Phase 1: 設定管理系初期化
        self.config_manager = ConfigurationManager()
        self.location_manager = WorkLocationManager(self.config_manager)
        
        # 🆕 統合設定管理システム初期化
        try:
            from unified_config_manager import UnifiedConfigManager
            self.unified_config = UnifiedConfigManager()
        except ImportError as e:
            st.error(f"統合設定管理システムの読み込みエラー: {e}")
            self.unified_config = None
        
        self.engine = CompleteScheduleEngine(self.location_manager, self.config_manager)
        self.excel_exporter = ExcelExporter(self.engine)
        
        # 🔧 基本属性の初期化（セッション状態優先）
        self.year = st.session_state.get('year', 2025) if 'year' in st.session_state else 2025
        self.month = st.session_state.get('month', 6) if 'month' in st.session_state else 6
        self.n_days = calendar.monthrange(self.year, self.month)[1]
        
        # 🔧 初期化時に既存の統合設定があれば読み込み
        self._initialize_from_existing_config()
        
        # セッション状態初期化
        if 'calendar_data' not in st.session_state:
            st.session_state.calendar_data = {}
        if 'show_config' not in st.session_state:
            st.session_state.show_config = False
        if 'selected_config' not in st.session_state:
            st.session_state.selected_config = None
        if 'show_priority_settings' not in st.session_state:
            st.session_state.show_priority_settings = False
        if 'last_employees' not in st.session_state:
            st.session_state.last_employees = self.config_manager.get_employees()
        
        # 🆕 ビスポーク版：警乗基準日を固定
        self.keijo_base_date = KEIJO_BASE_DATE
        if 'year' not in st.session_state:
            st.session_state.year = 2025
        if 'month' not in st.session_state:
            st.session_state.month = 6
        # 🆕 現在アクティブな統合設定ファイルの追跡
        if 'current_unified_config' not in st.session_state:
            st.session_state.current_unified_config = None
        if 'unified_config_auto_save' not in st.session_state:
            st.session_state.unified_config_auto_save = True
        # 🆕 設定ファイル選択画面表示フラグ
        if 'show_config_selector' not in st.session_state:
            st.session_state.show_config_selector = False
        
        # デフォルト設定読み込み
        config_files = self.config_manager.get_config_files()
        if 'default.json' in config_files:
            self.config_manager.load_config('default.json')
        else:
            # デフォルト設定ファイルがない場合は作成
            default_filename = self.config_manager.save_config("デフォルト設定")
            if default_filename:
                print(f"✅ デフォルト設定ファイルを作成しました: {default_filename}")
        
        # 既存互換性維持
        self.location_manager.load_config()
        
        # 設定の初期読み込み後に重複除去と保存
        if len(self.location_manager.duty_locations) != len(set(loc["name"] for loc in self.location_manager.duty_locations)):
            # 重複が検出された場合、クリーンアップして保存
            self.location_manager.duty_locations = self.location_manager._remove_duplicates(self.location_manager.duty_locations)
            self.location_manager.save_config()
            print("✅ 重複した勤務場所を削除してクリーンアップしました")
    
    def run(self):
        """メイン実行（1ページ統合設計）"""
        # 🔧 実行開始時に統合設定との同期を確認
        self._ensure_config_sync()
        
        self._setup_page()
        
        # 🆕 1ページ統合設計 - 全ての機能を縦に配置
        self._unified_single_page()
    
    def _setup_page(self):
        """ページ設定（Phase 1）"""
        st.set_page_config(
            page_title="勤務表システム Phase 1",
            page_icon="📅",
            layout="wide"
        )
        
        st.title("📅 勤務表システム Phase 1")
        st.success("🎆 **Phase 1**: 優先度設定 + 設定保存機能搭載")
        
        # リセットボタンのみ表示
        col1, col2 = st.columns([1, 9])
        with col1:
            if st.button("🔄 リセット"):
                self.location_manager.reset_to_default()
                st.success("デフォルト設定に戻しました")
                st.rerun()
        
        st.markdown("---")
    
    def _unified_single_page(self):
        """🆕 1ページ統合設計のメイン画面"""
        
        # サイドバーナビゲーション（目次）
        self._create_navigation_sidebar()
        
        # メイン統合設定セクション
        st.container()
        with st.container():
            self._create_unified_config_section()
        
        # セクション1: 基本設定（最も使用頻度が高い）
        st.container()
        with st.container():
            st.markdown('<div id="basic-settings"></div>', unsafe_allow_html=True)
            st.header("📋 基本設定")
            self._basic_settings_section()
        
        # セクション2: スケジュール生成（使用頻度高）
        st.container()
        with st.container():
            st.markdown('<div id="schedule-generation"></div>', unsafe_allow_html=True)
            st.header("🚀 スケジュール生成")
            self._schedule_generation_section()
        
        # ビスポーク版：優先度は固定設定（設定変更時はハンドラー君へ）
        st.info("🎯 **優先度設定**: 固定済み（変更時はハンドラー君へご相談ください）")
        
        # セクション4: 詳細設定（使用頻度低 - 下部に配置）
        st.container()
        with st.container():
            st.markdown('<div id="detail-settings"></div>', unsafe_allow_html=True)
            st.header("⚙️ 詳細設定")
            self._inline_configuration_section()
        
        # 設定ファイル選択画面（必要時のみ表示）
        if st.session_state.get('show_config_selector', False):
            self._show_config_selector()
        
        # フッター
        self._create_footer()
    
    def _create_navigation_sidebar(self):
        """ナビゲーション用サイドバー（目次）"""
        with st.sidebar:
            st.title("📑 ページ目次")
            
            # 🆕 統合設定がアクティブな場合の表示
            if self._is_unified_config_active():
                current_config_name = self._get_current_unified_config_name()
                st.success(f"🔗 アクティブ: {current_config_name}")
            
            st.markdown("---")
            
            # ナビゲーションリンク（JavaScriptでスムーズスクロール）
            st.markdown("### 🧭 セクションジャンプ")
            
            # HTML+JavaScriptでスムーズスクロール
            navigation_html = """
            <style>
            .nav-button {
                display: block;
                width: 100%;
                padding: 8px 12px;
                margin: 4px 0;
                background-color: #f0f2f6;
                border: 1px solid #e6e9ef;
                border-radius: 4px;
                text-decoration: none;
                color: #333;
                transition: background-color 0.3s;
            }
            .nav-button:hover {
                background-color: #e6e9ef;
                text-decoration: none;
                color: #333;
            }
            </style>
            
            <a href="#basic-settings" class="nav-button">📋 基本設定</a>
            <a href="#schedule-generation" class="nav-button">🚀 スケジュール生成</a>
            <a href="#priority-settings" class="nav-button">🎯 優先度設定</a>
            <a href="#detail-settings" class="nav-button">⚙️ 詳細設定</a>
            
            <script>
            document.querySelectorAll('a[href^="#"]').forEach(anchor => {
                anchor.addEventListener('click', function (e) {
                    e.preventDefault();
                    const target = document.querySelector(this.getAttribute('href'));
                    if (target) {
                        target.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start'
                        });
                    }
                });
            });
            </script>
            """
            
            st.markdown(navigation_html, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # クイックアクション
            st.markdown("### ⚡ クイックアクション")
            
            if st.button("🔄 全体リセット", use_container_width=True):
                # セッション状態をクリア
                for key in list(st.session_state.keys()):
                    if key != 'gui_instance':  # GUIインスタンスは保持
                        del st.session_state[key]
                st.success("🔄 リセット完了")
                st.rerun()
            
            if st.button("📁 設定ファイル管理", use_container_width=True):
                st.session_state.show_config_selector = True
                st.rerun()
    
    def _basic_settings_section(self):
        """基本設定セクション（従業員・年月・前月末勤務）"""
        # 年月設定
        col1, col2 = st.columns(2)
        with col1:
            year = st.number_input(
                "年", 
                min_value=2020, 
                max_value=2030,
                key='year'
            )
        with col2:
            month = st.selectbox(
                "月", 
                range(1, 13), 
                key='month'
            )
        
        # インスタンス変数も更新（既存コード互換性のため）
        self.year = year
        self.month = month
        self.n_days = calendar.monthrange(self.year, self.month)[1]
        
        # 前月情報表示
        prev_year, prev_month = self._get_prev_month_info()
        st.info(f"対象: {self.year}年{self.month}月 ({self.n_days}日間)")
        st.info(f"前月: {prev_year}年{prev_month}月")
        
        st.markdown("---")
        
        # 従業員設定
        st.subheader("👥 従業員設定")
        
        # 保存された従業員設定を取得（セッション状態優先）
        if 'last_employees' in st.session_state and st.session_state.last_employees:
            saved_employees = st.session_state.last_employees
        else:
            saved_employees = self.config_manager.get_employees()
            # セッション状態に保存
            st.session_state.last_employees = saved_employees
        
        # 従業員入力
        employees_input = st.text_area(
            "従業員名（1行に1名）",
            value="\n".join(saved_employees),
            height=120,
            help="各行に1名ずつ従業員名を入力してください。「助勤」は自動的に最後に追加されます。"
        )
        
        # 入力から従業員リスト作成
        new_employees = [name.strip() for name in employees_input.split('\n') if name.strip()]
        
        # 助勤を自動追加（重複を避ける）
        if "助勤" not in new_employees:
            new_employees.append("助勤")
        
        # 保存ボタンとリセットボタン
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💾 従業員設定を保存", key="save_employees_basic"):
                if len(new_employees) >= 2:
                    # Config Managerに保存
                    self.config_manager.update_employees(new_employees)
                    
                    # セッション状態を強制更新
                    st.session_state.last_employees = new_employees.copy()
                    
                    # 🆕 統合設定への保存
                    if self._is_unified_config_active():
                        # アクティブな統合設定に自動保存
                        self._auto_save_unified_config()
                        current_config_name = self._get_current_unified_config_name()
                        st.success(f"✅ 統合設定 {current_config_name} に保存しました")
                        st.success(f"👥 従業員数: {len(new_employees)}名")
                    else:
                        # 統合設定がない場合は新規作成を促す
                        st.info("📝 統合設定ファイルがアクティブではありません")
                        if st.button("🆕 新しい統合設定として保存", key="create_new_unified_basic"):
                            config_name = "従業員設定_" + datetime.now().strftime("%Y%m%d")
                            self._save_unified_config_complete(config_name)
                    
                    # 保存後は saved_employees を更新
                    saved_employees = new_employees.copy()
                    st.rerun()
                else:
                    st.error("❌ 従業員は最低2名必要です")
        
        with col2:
            if st.button("🔄 デフォルトに戻す", key="reset_employees_basic"):
                default_employees = self.config_manager.default_config["employees"]
                self.config_manager.update_employees(default_employees)
                st.session_state.last_employees = default_employees.copy()
                
                # 🆕 統合設定への自動保存
                if self._is_unified_config_active():
                    self._auto_save_unified_config()
                    current_config_name = self._get_current_unified_config_name()
                    st.success(f"✅ デフォルト従業員設定に戻し、{current_config_name} に保存しました")
                else:
                    st.success("✅ デフォルト従業員設定に戻しました")
                    
                st.rerun()
        
        # 現在の従業員を設定（保存されたものを使用）
        self.employees = saved_employees
        
        # 変更がある場合の警告表示
        if new_employees != saved_employees:
            st.warning("⚠️ 従業員設定に変更があります。保存ボタンを押して保存してください。")
        
        st.markdown("---")
        
        # 前月末勤務設定
        st.subheader("🔄 前月末勤務情報")
        st.warning("⚠️ 前日勤務者は翌月1日目が自動的に非番になります")
        self.prev_schedule_data = self._create_prev_schedule_input(f"{prev_year}年{prev_month}月")
    
    def _schedule_generation_section(self):
        """スケジュール生成セクション"""
        # カレンダー設定
        st.subheader("📅 従業員別カレンダー設定")
        
        # カレンダー入力
        duty_names = self.location_manager.get_duty_names()
        
        for emp_name in [emp for emp in self.employees if emp != "助勤"]:
            with st.expander(f"👤 {emp_name}のカレンダー", expanded=False):
                self._create_employee_calendar(emp_name, duty_names)
        
        st.markdown("---")
        
        # 警乗隔日制約設定
        st.subheader("🚔 警乗隔日制約設定")
        
        # 警乗隔日の詳細設定
        # ビスポーク版：警乗隔日制約は常に有効（6月1日起点固定）
        st.info("🚁 **警乗隔日制約**: 6月1日起点で自動適用")
        
        # 警乗パターンの説明と表示
        if st.button("📊 警乗パターンを確認"):
            pattern_days = self._calculate_keijo_pattern(self.year, self.month)
            if pattern_days:
                st.success("✅ 警乗パターンが計算されました")
                pattern_str = "、".join([f"{day}日" for day in pattern_days])
                st.info(f"🚔 警乗勤務日: {pattern_str}")
            else:
                st.warning("警乗パターンが見つかりませんでした")
        
        st.markdown("---")
        
        # カレンダー入力のプレビュー
        st.subheader("📋 入力内容プレビュー")
        
        if st.session_state.calendar_data:
            # 統計表示
            total_holidays = 0
            total_duties = 0
            cross_constraints_preview = []
            
            for emp_name, emp_data in st.session_state.calendar_data.items():
                h_count = len(emp_data.get('holidays', []))
                d_count = len(emp_data.get('duty_preferences', {}))
                
                total_holidays += h_count
                total_duties += d_count
                
                if h_count > 0 or d_count > 0:
                    st.write(f"**{emp_name}**: 休暇{h_count}件, 勤務希望{d_count}件")
        
            # 月またぎ制約予測
            for emp in self.employees:
                if emp in self.prev_schedule_data:
                    emp_data = self.prev_schedule_data[emp]
                    if len(emp_data) >= 1:
                        last_shift = emp_data[-1]
                        if last_shift in self.location_manager.get_duty_names():
                            cross_constraints_preview.append(f"{emp}: 前日{last_shift}勤務 → 1日目非番")
        
            st.write(f"**合計**: 休暇希望{total_holidays}件, 勤務希望{total_duties}件")
            
            if cross_constraints_preview:
                st.write("**予想される月またぎ制約**:")
                for constraint in cross_constraints_preview:
                    st.write(f"- {constraint}")
            else:
                st.write("**月またぎ制約**: なし")
        
        # 生成ボタン
        if st.button("🚀 勤務表を生成", type="primary", use_container_width=True):
            self._generate_schedule()
    
    def _inline_priority_settings_section(self):
        """ビスポーク版：優先度設定は固定済み"""
        # 固定優先度確認（簡潔表示）
        with st.expander("🎯 優先度確認", expanded=False):
            for emp, priorities in PRIORITY_MATRIX.items():
                priority_text = []
                for loc, val in priorities.items():
                    text = {0: '不可', 1: '可', 2: '普通', 3: 'やや優先', 4: '優先', 5: '最優先'}[val]
                    priority_text.append(f"{loc}:{text}")
                st.write(f"**{emp}**: {', '.join(priority_text)}")
        
        # 現在の優先度設定取得
        current_priorities = self.config_manager.get_employee_priorities()
        duty_names = self.config_manager.get_duty_names()
        
        # 優先度選択肢
        priority_options = ["0 (不可)", "1 (可能)", "2 (普通)", "3 (最優先)"]
        
        # 新しい優先度設定を格納
        new_priorities = {}
        
        # 🆕 従業員リスト取得の優先順位を統合設定 > session_state > デフォルトに変更
        # 統合設定がアクティブな場合は、常にsession_stateから取得（リセット問題回避）
        if self._is_unified_config_active() and 'last_employees' in st.session_state:
            # 統合設定がアクティブな場合は、session_stateを最優先
            all_employees = st.session_state.last_employees
            target_employees = [emp for emp in all_employees if emp != "助勤"]
            st.info(f"📋 統合設定 {self._get_current_unified_config_name()} から従業員を取得")
        elif 'last_employees' in st.session_state and st.session_state.last_employees:
            all_employees = st.session_state.last_employees
            target_employees = [emp for emp in all_employees if emp != "助勤"]
        elif hasattr(self, 'employees') and self.employees:
            target_employees = [emp for emp in self.employees if emp != "助勤"]
        else:
            # デフォルト従業員設定
            target_employees = ["Aさん", "Bさん", "Cさん"]
            st.warning("⚠️ デフォルト従業員を使用中。統合設定を読み込んでください。")
        
        st.info(f"📊 設定対象従業員: {len(target_employees)}名（助勤除く）")
        
        # コンパクト表示用の列設定
        if len(target_employees) <= 6:
            # 6名以下の場合は全員表示
            display_employees = target_employees
        else:
            # 6名以上の場合はページ分割
            st.warning("⚠️ 従業員数が多いため、ページ分割表示になります")
            page_size = 6
            total_pages = (len(target_employees) + page_size - 1) // page_size
            current_page = st.selectbox("表示ページ", range(1, total_pages + 1), key="priority_page_inline") - 1
            start_idx = current_page * page_size
            end_idx = min(start_idx + page_size, len(target_employees))
            display_employees = target_employees[start_idx:end_idx]
            st.info(f"📄 ページ {current_page + 1}/{total_pages} - 従業員 {start_idx + 1}～{end_idx}名を表示")
        
        # 優先度設定テーブル（コンパクト表示）
        for emp_name in display_employees:
            st.write(f"**👤 {emp_name}**")
            emp_priorities = current_priorities.get(emp_name, {})
            
            # 各勤務場所の優先度を横並びで表示
            cols = st.columns(len(duty_names))
            for i, duty_name in enumerate(duty_names):
                with cols[i]:
                    current_priority = emp_priorities.get(duty_name, 2)
                    current_index = current_priority if 0 <= current_priority <= 3 else 2
                    
                    selected = st.selectbox(
                        f"{duty_name}",
                        priority_options,
                        index=current_index,
                        key=f"priority_inline_{emp_name}_{duty_name}"
                    )
                    
                    # 選択された優先度を解析
                    priority_value = int(selected.split(" ")[0])
                    if emp_name not in new_priorities:
                        new_priorities[emp_name] = {}
                    new_priorities[emp_name][duty_name] = priority_value
            
            st.markdown("---")
        
        # 保存ボタン
        col1, col2 = st.columns([3, 1])
        
        with col1:
            if st.button("💾 優先度設定を保存", type="primary", key="save_priority_inline"):
                # 既存の優先度設定をベースに更新
                updated_priorities = current_priorities.copy()
                updated_priorities.update(new_priorities)
                
                if self._is_unified_config_active():
                    try:
                        # メモリに優先度を反映
                        self.config_manager.update_employee_priorities(updated_priorities)
                        # 統合設定に自動保存
                        self._auto_save_unified_config()
                        current_config_name = self._get_current_unified_config_name()
                        st.success(f"✅ 統合設定 {current_config_name} に保存しました")
                        st.info(f"🔗 保存された優先度設定: {len(updated_priorities)}名分")
                        st.rerun()  # 画面を更新して保存を反映
                    except Exception as e:
                        st.error(f"❌ 保存エラー: {str(e)}")
                else:
                    st.info("📝 統合設定ファイルがアクティブではありません")
                    if st.button("🆕 新しい統合設定として保存", key="create_new_unified_priorities_inline"):
                        try:
                            self.config_manager.update_employee_priorities(updated_priorities)
                            config_name = "優先度設定_" + datetime.now().strftime("%Y%m%d")
                            self._save_unified_config_complete(config_name)
                        except Exception as e:
                            st.error(f"❌ 新規保存エラー: {str(e)}")
        
        with col2:
            if st.button("📊 設定表示", key="show_priority_table_inline"):
                # 現在の設定を表形式で表示
                st.subheader("📋 現在の優先度設定")
                
                import pandas as pd
                table_data = []
                
                for emp_name in target_employees:
                    row = {"従業員": emp_name}
                    emp_priorities = current_priorities.get(emp_name, {})
                    
                    for duty_name in duty_names:
                        priority = emp_priorities.get(duty_name, 2)
                        row[duty_name] = f"{priority} ({['❌', '🟡', '🔵', '✅'][priority]})"
                    
                    table_data.append(row)
                
                if table_data:
                    df = pd.DataFrame(table_data)
                    st.dataframe(df, use_container_width=True)
    
    def _inline_configuration_section(self):
        """インライン詳細設定セクション（勤務場所設定）"""
        st.info(f"現在の勤務場所数: {len(self.location_manager.duty_locations)} / 15（最大）")
        
        # 現在の勤務場所一覧
        duty_locations = self.location_manager.get_duty_locations()
        
        # 一時的な変更フラグ
        changes_made = False
        
        st.subheader("🏢 勤務場所一覧")
        
        for i, location in enumerate(duty_locations):
            with st.expander(f"📍 {location['name']}", expanded=False):
                col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])
                
                with col1:
                    new_name = st.text_input(
                        "勤務場所名",
                        value=location["name"],
                        key=f"loc_name_inline_{i}"
                    )
                
                with col2:
                    new_type = st.selectbox(
                        "勤務タイプ",
                        ["一徹勤務", "日勤", "夜勤", "その他"],
                        index=["一徹勤務", "日勤", "夜勤", "その他"].index(location.get("type", "一徹勤務")),
                        key=f"loc_type_inline_{i}"
                    )
                
                with col3:
                    new_duration = st.number_input(
                        "時間",
                        min_value=1,
                        max_value=24,
                        value=location.get("duration", 16),
                        key=f"loc_duration_inline_{i}"
                    )
                
                with col4:
                    new_color = st.color_picker(
                        "色",
                        value=location.get("color", "#FF6B6B"),
                        key=f"loc_color_inline_{i}"
                    )
                
                with col5:
                    if st.button("🗑️", key=f"delete_inline_{i}"):
                        location_name = location["name"]
                        self.location_manager.remove_duty_location(i)
                        if self.location_manager.save_config():
                            # 🆕 ConfigManagerに変更を同期
                            if self.location_manager.config_manager:
                                self.location_manager.config_manager.current_config["work_locations"] = self.location_manager.duty_locations.copy()
                            # 🆕 統合設定がアクティブな場合は統合設定にも反映
                            if self._is_unified_config_active():
                                self._auto_save_unified_config()
                                current_config_name = self._get_current_unified_config_name()
                                st.success(f"「{location_name}」を削除し、統合設定 {current_config_name} に保存しました")
                            else:
                                st.success(f"「{location_name}」を削除しました")
                            st.rerun()
                        else:
                            st.error("削除に失敗しました")
                
                # 変更があったかチェック
                if (new_name != location["name"] or 
                    new_type != location.get("type", "一徹勤務") or
                    new_duration != location.get("duration", 16) or
                    new_color != location.get("color", "#FF6B6B")):
                    self.location_manager.update_duty_location(i, new_name, new_type, new_duration, new_color)
                    changes_made = True
        
        # 変更があった場合は自動保存（統合設定対応）
        if changes_made:
            self.location_manager.save_config()
            # 🆕 ConfigManagerに変更を同期
            if self.location_manager.config_manager:
                self.location_manager.config_manager.current_config["work_locations"] = self.location_manager.duty_locations.copy()
            # 🆕 統合設定がアクティブな場合は統合設定にも反映
            if self._is_unified_config_active():
                self._auto_save_unified_config()
                current_config_name = self._get_current_unified_config_name()
                st.success(f"✅ 変更を統合設定 {current_config_name} に自動保存しました")
            else:
                st.success("✅ 変更を自動保存しました")
        
        # 新規追加（最大15まで）
        if len(duty_locations) < 15:
            st.subheader("➕ 新規勤務場所追加")
            
            # フォームを使用してセッション状態の問題を回避
            with st.form("add_location_form_inline"):
                col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
                
                with col1:
                    add_name = st.text_input("新しい勤務場所名")
                with col2:
                    add_type = st.selectbox("勤務タイプ", ["一徹勤務", "日勤", "夜勤", "その他"])
                with col3:
                    add_duration = st.number_input("時間", min_value=1, max_value=24, value=16)
                with col4:
                    add_color = st.color_picker("色", value="#45B7D1")
                
                submitted = st.form_submit_button("➕ 追加", use_container_width=True)
                
                if submitted:
                    if add_name.strip():
                        # 重複チェック
                        existing_names = [loc["name"] for loc in self.location_manager.duty_locations]
                        if add_name.strip() in existing_names:
                            st.error(f"「{add_name}」は既に存在します")
                        else:
                            self.location_manager.add_duty_location(add_name.strip(), add_type, add_duration, add_color)
                            if self.location_manager.save_config():
                                # 🆕 ConfigManagerに変更を同期
                                if self.location_manager.config_manager:
                                    self.location_manager.config_manager.current_config["work_locations"] = self.location_manager.duty_locations.copy()
                                # 🆕 統合設定がアクティブな場合は統合設定にも反映
                                if self._is_unified_config_active():
                                    self._auto_save_unified_config()
                                    current_config_name = self._get_current_unified_config_name()
                                    st.success(f"「{add_name}」を追加し、統合設定 {current_config_name} に保存しました")
                                else:
                                    st.success(f"「{add_name}」を追加しました")
                                st.rerun()
                            else:
                                st.error("保存に失敗しました")
                    else:
                        st.error("勤務場所名を入力してください")
        else:
            st.warning("⚠️ 最大15勤務場所まで追加できます")
    
    def _create_employee_calendar(self, emp_name, duty_names):
        """従業員別カレンダー入力UI"""
        # カレンダーデータの初期化
        if emp_name not in st.session_state.calendar_data:
            st.session_state.calendar_data[emp_name] = {
                'holidays': [],
                'duty_preferences': {}
            }
        
        emp_data = st.session_state.calendar_data[emp_name]
        
        # 休暇希望の設定
        st.write("**🌴 休暇希望日**")
        
        # 月の日付リストを生成
        available_dates = []
        for day in range(1, self.n_days + 1):
            try:
                date_obj = date(self.year, self.month, day)
                available_dates.append(date_obj)
            except ValueError:
                # 無効な日付はスキップ
                continue
        
        # 既存の休暇設定をdateオブジェクトに変換
        existing_holidays = emp_data.get('holidays', [])
        default_holidays = []
        for holiday in existing_holidays:
            if isinstance(holiday, str):
                try:
                    # 文字列の場合はdateオブジェクトに変換
                    holiday_date = datetime.strptime(holiday, '%Y-%m-%d').date()
                    if holiday_date in available_dates:
                        default_holidays.append(holiday_date)
                except (ValueError, TypeError):
                    continue
            elif isinstance(holiday, date):
                # 既にdateオブジェクトの場合
                if holiday in available_dates:
                    default_holidays.append(holiday)
        
        # 休暇希望の複数選択
        selected_holidays = st.multiselect(
            "休暇希望日を選択",
            options=available_dates,
            default=default_holidays,
            format_func=lambda d: f"{d.month}月{d.day}日({['月','火','水','木','金','土','日'][d.weekday()]})",
            key=f"holidays_{emp_name}"
        )
        
        # セッション状態に保存
        st.session_state.calendar_data[emp_name]['holidays'] = selected_holidays
        
        st.markdown("---")
        
        # 勤務場所希望の設定
        st.write("**🏢 勤務場所希望**")
        
        # 日別の勤務場所希望設定
        duty_preferences = emp_data.get('duty_preferences', {})
        
        # 日付範囲選択
        col1, col2 = st.columns(2)
        with col1:
            start_day = st.number_input(
                "開始日",
                min_value=1,
                max_value=self.n_days,
                value=1,
                key=f"start_day_{emp_name}"
            )
        
        with col2:
            end_day = st.number_input(
                "終了日",
                min_value=start_day,
                max_value=self.n_days,
                value=min(start_day + 6, self.n_days),
                key=f"end_day_{emp_name}"
            )
        
        # 勤務場所選択
        if duty_names:
            selected_duty = st.selectbox(
                "希望勤務場所",
                options=["なし"] + duty_names,
                key=f"duty_pref_{emp_name}"
            )
            
            if selected_duty != "なし":
                if st.button(f"📅 {start_day}日〜{end_day}日に{selected_duty}を設定", key=f"set_duty_{emp_name}"):
                    # 選択された日付範囲に勤務場所希望を設定
                    for day in range(start_day, end_day + 1):
                        duty_preferences[day] = selected_duty
                    
                    # セッション状態に保存
                    st.session_state.calendar_data[emp_name]['duty_preferences'] = duty_preferences
                    
                    # 統合設定への自動保存
                    if self._is_unified_config_active():
                        self._auto_save_unified_config()
                    
                    st.success(f"✅ {start_day}日〜{end_day}日に{selected_duty}勤務希望を設定しました")
                    st.rerun()
        
        # 現在の設定表示
        if duty_preferences:
            st.write("**📋 現在の勤務場所希望**")
            pref_text = []
            for day, duty in sorted(duty_preferences.items()):
                pref_text.append(f"{day}日: {duty}")
            st.info("、".join(pref_text))
            
            # 個別削除ボタン
            if st.button(f"🗑️ 勤務場所希望をクリア", key=f"clear_duty_{emp_name}"):
                st.session_state.calendar_data[emp_name]['duty_preferences'] = {}
                
                # 統合設定への自動保存
                if self._is_unified_config_active():
                    self._auto_save_unified_config()
                
                st.success("✅ 勤務場所希望をクリアしました")
                st.rerun()
        
        # 休暇希望の表示
        if selected_holidays:
            st.write("**📋 現在の休暇希望**")
            holiday_text = []
            for holiday in sorted(selected_holidays):
                holiday_text.append(f"{holiday.month}月{holiday.day}日")
            st.info("、".join(holiday_text))
        
        # 統合設定への自動保存（休暇希望変更時）
        if selected_holidays != emp_data.get('holidays', []):
            if self._is_unified_config_active():
                self._auto_save_unified_config()
    
    def _create_footer(self):
        """フッター"""
        st.markdown("---")
        st.markdown("💡 **Phase 1**: 優先度設定と設定保存機能が完全動作します")
        st.markdown("🎯 **重要**: 優先度が勤務表に反映され、設定保存で再利用可能です")
        
        # システム情報
        with st.expander("ℹ️ システム情報"):
            st.write("**1ページ統合設計の利点**:")
            st.write("- ✅ **ページ切り替えなし**: 全ての設定が1ページに統合")
            st.write("- ✅ **サイドバーナビゲーション**: 各セクションへ瞬時に移動")
            st.write("- ✅ **状態保持**: セッション状態の管理が単純で堅牢")
            st.write("- ✅ **自動保存**: 統合設定への即座の反映")
    
    def _configuration_page(self):
        """設定ページ（修正版）"""
        st.header("⚙️ 詳細設定")
        
        # 🔧 詳細設定ページ開始時に統合設定から最新状態を確認
        if self._is_unified_config_active():
            current_config_name = self._get_current_unified_config_name()
            st.info(f"🔗 アクティブ設定: {current_config_name}")
            st.info("📝 変更は自動的に統合設定に保存されます")
        
        # 戻るボタン
        if st.button("← メインページに戻る"):
            # 🔧 戻る前に統合設定への自動保存を確実に実行
            if self._is_unified_config_active():
                try:
                    # LocationManagerの変更をConfigManagerに同期
                    if self.location_manager.config_manager:
                        self.location_manager.config_manager.current_config["work_locations"] = self.location_manager.duty_locations.copy()
                    # 統合設定に保存
                    self._auto_save_unified_config()
                    current_config_name = self._get_current_unified_config_name()
                    st.success(f"✅ 変更を統合設定 {current_config_name} に保存しました")
                except Exception as e:
                    st.error(f"❌ 保存エラー: {str(e)}")
            
            st.session_state.show_config = False
            st.rerun()
        
        st.subheader("勤務場所設定")
        st.info(f"現在の勤務場所数: {len(self.location_manager.duty_locations)} / 15（最大）")
        
        # 現在の勤務場所一覧
        duty_locations = self.location_manager.get_duty_locations()
        
        # 一時的な変更フラグ
        changes_made = False
        
        for i, location in enumerate(duty_locations):
            st.write(f"**勤務場所 {i+1}**")
            col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])
            
            with col1:
                new_name = st.text_input(
                    "勤務場所名",
                    value=location["name"],
                    key=f"loc_name_{i}"
                )
            
            with col2:
                new_type = st.selectbox(
                    "勤務タイプ",
                    ["一徹勤務", "日勤", "夜勤", "その他"],
                    index=["一徹勤務", "日勤", "夜勤", "その他"].index(location.get("type", "一徹勤務")),
                    key=f"loc_type_{i}"
                )
            
            with col3:
                new_duration = st.number_input(
                    "時間",
                    min_value=1,
                    max_value=24,
                    value=location.get("duration", 16),
                    key=f"loc_duration_{i}"
                )
            
            with col4:
                new_color = st.color_picker(
                    "色",
                    value=location.get("color", "#FF6B6B"),
                    key=f"loc_color_{i}"
                )
            
            with col5:
                if st.button("🗑️", key=f"delete_{i}"):
                    location_name = location["name"]
                    self.location_manager.remove_duty_location(i)
                    if self.location_manager.save_config():
                        # 🆕 ConfigManagerに変更を同期
                        if self.location_manager.config_manager:
                            self.location_manager.config_manager.current_config["work_locations"] = self.location_manager.duty_locations.copy()
                        # 🆕 統合設定がアクティブな場合は統合設定にも反映
                        if self._is_unified_config_active():
                            self._auto_save_unified_config()
                            current_config_name = self._get_current_unified_config_name()
                            st.success(f"「{location_name}」を削除し、統合設定 {current_config_name} に保存しました")
                        else:
                            st.success(f"「{location_name}」を削除しました")
                        st.rerun()
                    else:
                        st.error("削除に失敗しました")
            
            # 変更があったかチェック
            if (new_name != location["name"] or 
                new_type != location.get("type", "一徹勤務") or
                new_duration != location.get("duration", 16) or
                new_color != location.get("color", "#FF6B6B")):
                self.location_manager.update_duty_location(i, new_name, new_type, new_duration, new_color)
                changes_made = True
            
            st.markdown("---")
        
        # 変更があった場合は自動保存（統合設定対応）
        if changes_made:
            self.location_manager.save_config()
            # 🆕 ConfigManagerに変更を同期
            if self.location_manager.config_manager:
                self.location_manager.config_manager.current_config["work_locations"] = self.location_manager.duty_locations.copy()
            # 🆕 統合設定がアクティブな場合は統合設定にも反映
            if self._is_unified_config_active():
                self._auto_save_unified_config()
                current_config_name = self._get_current_unified_config_name()
                st.success(f"✅ 変更を統合設定 {current_config_name} に自動保存しました")
            else:
                st.success("✅ 変更を自動保存しました")
        
        # 新規追加（最大15まで）
        if len(duty_locations) < 15:
            st.subheader("新規勤務場所追加")
            
            # フォームを使用してセッション状態の問題を回避
            with st.form("add_location_form"):
                col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
                
                with col1:
                    add_name = st.text_input("新しい勤務場所名")
                with col2:
                    add_type = st.selectbox("勤務タイプ", ["一徹勤務", "日勤", "夜勤", "その他"])
                with col3:
                    add_duration = st.number_input("時間", min_value=1, max_value=24, value=16)
                with col4:
                    add_color = st.color_picker("色", value="#45B7D1")
                
                submitted = st.form_submit_button("➕ 追加", use_container_width=True)
                
                if submitted:
                    if add_name.strip():
                        # 重複チェック
                        existing_names = [loc["name"] for loc in self.location_manager.duty_locations]
                        if add_name.strip() in existing_names:
                            st.error(f"「{add_name}」は既に存在します")
                        else:
                            self.location_manager.add_duty_location(add_name.strip(), add_type, add_duration, add_color)
                            if self.location_manager.save_config():
                                # 🆕 ConfigManagerに変更を同期
                                if self.location_manager.config_manager:
                                    self.location_manager.config_manager.current_config["work_locations"] = self.location_manager.duty_locations.copy()
                                # 🆕 統合設定がアクティブな場合は統合設定にも反映
                                if self._is_unified_config_active():
                                    self._auto_save_unified_config()
                                    current_config_name = self._get_current_unified_config_name()
                                    st.success(f"「{add_name}」を追加し、統合設定 {current_config_name} に保存しました")
                                else:
                                    st.success(f"「{add_name}」を追加しました")
                                st.rerun()
                            else:
                                st.error("保存に失敗しました")
                    else:
                        st.error("勤務場所名を入力してください")
        else:
            st.warning("⚠️ 最大15勤務場所まで追加できます")
        
        # 🆕 保存セクション
        st.markdown("---")
        st.subheader("💾 設定保存")
        
        # 🆕 設定名入力（アクティブな統合設定名を自動反映）
        default_config_name = "新しい設定"
        if self._is_unified_config_active():
            current_config_name = self._get_current_unified_config_name()
            default_config_name = current_config_name
            st.info(f"🔗 アクティブ設定: {current_config_name}")
        
        config_name = st.text_input(
            "設定名",
            value=default_config_name,
            help="統合設定ファイルの名前です",
            key="location_config_name"
        )
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # 保存ボタン
            if st.button("💾 全設定を保存", type="primary", key="save_location_config"):
                # 🆕 統合設定への保存
                if self._is_unified_config_active():
                    self.location_manager.save_config()
                    self._auto_save_unified_config()
                    current_config_name = self._get_current_unified_config_name()
                    st.success(f"✅ 統合設定 {current_config_name} に保存しました")
                    st.info(f"📁 保存先: {st.session_state.current_unified_config}")
                else:
                    if config_name.strip():
                        self.location_manager.save_config()
                        self._save_unified_config_complete(config_name.strip())
                        st.success(f"✅ 新しい統合設定 {config_name.strip()} として保存しました")
                    else:
                        st.error("設定名を入力してください")
        
        with col2:
            # 🆕 設定ファイル選択機能
            if st.button("📁 設定ファイル選択", key="select_config_locations"):
                st.session_state.show_config_selector = True
                st.rerun()
        
        # 🆕 設定ファイル選択画面
        if st.session_state.get('show_config_selector', False):
            self._show_config_selector()
    
    def _priority_settings_page(self):
        """優先度設定ページ（Phase 1）"""
        st.header("🎯 従業員優先度設定")
        
        # 🆕 アクティブな統合設定の表示
        if self._is_unified_config_active():
            current_config_name = self._get_current_unified_config_name()
            st.success(f"🔗 アクティブ: {current_config_name}")
            st.info("📝 変更は自動的に統合設定に保存されます")
        
        # 戻るボタン
        if st.button("← メインページに戻る"):
            st.session_state.show_priority_settings = False
            st.rerun()
        
        st.info("📝 優先度: 3=最優先, 2=普通, 1=可能, 0=不可")
        
        # 現在の優先度設定取得
        current_priorities = self.config_manager.get_employee_priorities()
        duty_names = self.config_manager.get_duty_names()
        
        # 優先度選択肢
        priority_options = ["0 (不可)", "1 (可能)", "2 (普通)", "3 (最優先)"]
        
        # 新しい優先度設定を格納
        new_priorities = {}
        
        # 🆕 従業員リスト取得の優先順位を統合設定 > session_state > デフォルトに変更
        # 統合設定がアクティブな場合は、常にsession_stateから取得（リセット問題回避）
        if self._is_unified_config_active() and 'last_employees' in st.session_state:
            # 統合設定がアクティブな場合は、session_stateを最優先
            all_employees = st.session_state.last_employees
            target_employees = [emp for emp in all_employees if emp != "助勤"]
            st.info(f"📋 統合設定 {self._get_current_unified_config_name()} から従業員を取得")
        elif 'last_employees' in st.session_state and st.session_state.last_employees:
            all_employees = st.session_state.last_employees
            target_employees = [emp for emp in all_employees if emp != "助勤"]
        elif hasattr(self, 'employees') and self.employees:
            target_employees = [emp for emp in self.employees if emp != "助勤"]
        else:
            # デフォルト従業員設定
            target_employees = ["Aさん", "Bさん", "Cさん"]
            st.warning("⚠️ デフォルト従業員を使用中。統合設定を読み込んでください。")
        
        st.info(f"📊 設定対象従業員: {len(target_employees)}名（助勤除く）")
        
        if len(target_employees) > 20:
            st.warning("⚠️ 従業員数が多いため、ページ分割表示を推奨します")
            
            # ページ分割機能
            page_size = 10
            total_pages = (len(target_employees) + page_size - 1) // page_size
            current_page = st.selectbox("表示ページ", range(1, total_pages + 1), key="priority_page") - 1
            start_idx = current_page * page_size
            end_idx = min(start_idx + page_size, len(target_employees))
            display_employees = target_employees[start_idx:end_idx]
            
            st.info(f"📄 ページ {current_page + 1}/{total_pages} - 従業員 {start_idx + 1}～{end_idx}名を表示")
        else:
            display_employees = target_employees
        
        for emp_name in display_employees:
            st.subheader(f"👤 {emp_name}の優先度設定")
            
            emp_priorities = {}
            cols = st.columns(len(duty_names))
            
            for i, duty_name in enumerate(duty_names):
                with cols[i]:
                    # 現在の設定をデフォルトに
                    current_value = current_priorities.get(emp_name, {}).get(duty_name, 2)
                    
                    selected = st.selectbox(
                        f"{duty_name}",
                        priority_options,
                        index=current_value,
                        key=f"priority_{emp_name}_{duty_name}"
                    )
                    
                    # 数値を抽出
                    priority_value = int(selected.split(" ")[0])
                    emp_priorities[duty_name] = priority_value
                    
                    # 色分け表示
                    if priority_value == 3:
                        st.success("✅ 最優先")
                    elif priority_value == 2:
                        st.info("🔵 普通")
                    elif priority_value == 1:
                        st.warning("🟡 可能")
                    else:
                        st.error("❌ 不可")
            
            new_priorities[emp_name] = emp_priorities
            st.markdown("---")
        
        # 保存セクション
        st.subheader("💾 設定保存")
        
        # 🆕 設定名入力（アクティブな統合設定名を自動反映）
        default_config_name = "新しい設定"
        if self._is_unified_config_active():
            current_config_name = self._get_current_unified_config_name()
            default_config_name = current_config_name
        
        config_name = st.text_input(
            "設定名",
            value=default_config_name,
            help="統合設定ファイルの名前です",
            key="priority_config_name"
        )
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            if st.button("💾 全設定を保存", type="primary"):
                # 🆕 統合設定への保存
                if self._is_unified_config_active():
                    try:
                        # メモリに優先度を反映
                        self.config_manager.update_employee_priorities(new_priorities)
                        # 統合設定に自動保存
                        self._auto_save_unified_config()
                        current_config_name = self._get_current_unified_config_name()
                        current_file = st.session_state.current_unified_config
                        st.success(f"✅ 統合設定 {current_config_name} に保存しました")
                        st.info(f"🔗 保存された優先度設定: {len(new_priorities)}名分")
                        st.info(f"📁 保存先: {current_file}")
                        st.rerun()  # 画面を更新して保存を反映
                    except Exception as e:
                        st.error(f"❌ 保存エラー: {str(e)}")
                else:
                    st.info("📝 統合設定ファイルがアクティブではありません")
                    if st.button("🆕 新しい統合設定として保存", key="create_new_unified_priorities"):
                        try:
                            self.config_manager.update_employee_priorities(new_priorities)
                            config_name = "優先度設定_" + datetime.now().strftime("%Y%m%d")
                            self._save_unified_config_complete(config_name)
                        except Exception as e:
                            st.error(f"❌ 新規保存エラー: {str(e)}")
        
        with col2:
            # 🆕 全設定ファイル選択機能
            if st.button("📁 設定ファイル選択"):
                st.session_state.show_config_selector = True
                st.rerun()
        
        with col3:
            if st.button("🔄 デフォルトに戻す"):
                # 🆕 統合設定がアクティブな場合は、現在の従業員に対するデフォルト設定を生成
                if self._is_unified_config_active():
                    # 現在の従業員リストに対してデフォルト優先度を設定
                    current_employees = st.session_state.get('last_employees', [])
                    duty_names = self.config_manager.get_duty_names()
                    
                    # 全従業員に対して一律の優先度設定（例：すべて「普通」）
                    default_priorities = {}
                    for emp in current_employees:
                        if emp != "助勤":  # 助勤は除外
                            default_priorities[emp] = {duty: 2 for duty in duty_names}  # 2=普通
                    
                    self.config_manager.update_employee_priorities(default_priorities)
                    st.success("✅ 現在の従業員に対してデフォルト設定を適用しました")
                    
                    # 統合設定に自動保存
                    self._auto_save_unified_config()
                    current_config_name = self._get_current_unified_config_name()
                    st.info(f"🔗 統合設定 {current_config_name} に自動保存しました")
                else:
                    # 従来のデフォルト復帰
                    default_priorities = self.config_manager.default_config["employee_priorities"]
                    self.config_manager.update_employee_priorities(default_priorities)
                    st.success("✅ デフォルト設定に戻しました")
                
                st.rerun()
        
        # 🆕 設定ファイル選択画面
        if st.session_state.get('show_config_selector', False):
            self._show_config_selector()
        
        # プレビューセクション
        with st.expander("🔍 優先度マトリックスプレビュー"):
            import pandas as pd
            
            # マトリックス作成
            matrix_data = []
            for emp_name in target_employees:
                row = [emp_name]
                emp_priorities = new_priorities.get(emp_name, {})
                for duty_name in duty_names:
                    priority = emp_priorities.get(duty_name, 2)
                    row.append(f"{priority} ({['❌', '🟡', '🔵', '✅'][priority]})")
                matrix_data.append(row)
            
            df = pd.DataFrame(matrix_data, columns=["従業員"] + duty_names)
            st.dataframe(df, use_container_width=True)
            
            st.info("📊 このマトリックスが勤務表生成時に反映されます")
    
    def _main_page(self):
        """メインページ"""
        # サイドバー
        with st.sidebar:
            self._create_sidebar()
        
        # メインエリア
        col1, col2 = st.columns([2, 1])
        
        with col1:
            self._create_calendar_input()
        
        with col2:
            self._create_control_panel()
    
    def _create_sidebar(self):
        """サイドバー（Phase 1: 設定管理対応）"""
        st.header("📋 基本設定")
        
        # 🆕 旧設定システムは廃止 - 統合設定のみ使用
        st.info("📋 統合設定システムを使用してください")
        st.info("💡 従来の設定ファイルは backup_configs/ に保存されています")
        
        st.markdown("---")
        
        # 🆕 統合設定管理セクション（メインシステム）
        if self.unified_config:
            self._create_unified_config_section()
            st.markdown("---")
        
        # 🆕 現在アクティブな統合設定の表示
        if self._is_unified_config_active():
            current_config_name = self._get_current_unified_config_name()
            st.success(f"🔗 アクティブ: {current_config_name}")
            st.info("📝 設定変更は自動的に保存されます")
            
            # 自動保存ON/OFF切り替え
            auto_save = st.checkbox(
                "自動保存を有効化", 
                value=st.session_state.get('unified_config_auto_save', True),
                key='unified_config_auto_save',
                help="チェックを外すと手動保存のみになります"
            )
            
            if not auto_save:
                if st.button("💾 手動保存", type="secondary"):
                    self._auto_save_unified_config()
                    st.success("✅ 手動保存しました")
            
            st.markdown("---")
        
        # 年月設定（最優先）（🆕 セッション状態と同期）
        year = st.number_input(
            "年", 
            min_value=2020, 
            max_value=2030,
            key='year'
        )
        month = st.selectbox(
            "月", 
            range(1, 13), 
            key='month'
        )
        # インスタンス変数も更新（既存コード互換性のため）
        self.year = year
        self.month = month
        self.n_days = calendar.monthrange(self.year, self.month)[1]
        
        # 前月情報表示
        prev_year, prev_month = self._get_prev_month_info()
        st.info(f"対象: {self.year}年{self.month}月 ({self.n_days}日間)")
        st.info(f"前月: {prev_year}年{prev_month}月")
        
        st.markdown("---")
        
        # 現在の勤務場所表示
        duty_names = self.location_manager.get_duty_names()
        st.write("**現在の勤務場所:**")
        for name in duty_names:
            st.write(f"• {name}")
        
        # 🆕 警乗設定セクション
        st.markdown("---")
        st.header("🚁 警乗設定")
        
        # 警乗起点日設定（🆕 セッション状態と同期）
        keijo_base_date = st.date_input(
            "警乗隔日の起点日",
            value=st.session_state.get('keijo_base_date', date(2025, 6, 1)),
            key='keijo_base_date',
            help="この日から偶数日に警乗が入ります"
        )
        # インスタンス変数も更新（既存コード互換性のため）
        self.keijo_base_date = keijo_base_date
        
        # パターン表示
        if self.keijo_base_date and "警乗" in duty_names:
            pattern_days = self._calculate_keijo_pattern(self.year, self.month)
            st.info(f"📅 警乗勤務日: {pattern_days['work_days']}")
            st.info(f"📅 警乗休止日: {pattern_days['rest_days']}")
            
            # 警告表示
            if pattern_days['total_work_days'] == 0:
                st.warning("⚠️ この月は警乗勤務日がありません")
        elif "警乗" not in duty_names:
            st.warning("⚠️ 「警乗」勤務場所が設定されていません")
        
        # ビスポーク版：優先度は固定（設定不要）
        st.info("🎯 優先度固定済み")
        
        # 詳細設定ボタン（勤務場所の下に配置）
        if st.button("⚙️ 詳細設定", use_container_width=True):
            st.session_state.show_config = True
            st.rerun()
        
        st.markdown("---")
        
        # 従業員設定
        st.header("👥 従業員設定")
        
        # 保存された従業員設定を取得（セッション状態優先）
        if 'last_employees' in st.session_state and st.session_state.last_employees:
            saved_employees = st.session_state.last_employees
        else:
            saved_employees = self.config_manager.get_employees()
            # セッション状態に保存
            st.session_state.last_employees = saved_employees
        
        employees_text = st.text_area(
            "従業員名（1行に1名）", 
            value="\n".join(saved_employees),
            height=150,
            help="変更後は下の保存ボタンを押してください"
        )
        new_employees = [emp.strip() for emp in employees_text.split('\n') if emp.strip()]
        
        # 従業員数チェック（最大50名まで）
        if len(new_employees) > 50:
            st.error("⚠️ 従業員は最大50名まで設定できます")
            new_employees = new_employees[:50]
        elif len(new_employees) < 2:
            st.error("❌ 従業員は最低2名必要です（固定従業員+助勤）")
        
        st.info(f"現在の従業員数: {len(new_employees)} / 50名")
        
        # 勤務体制の目安表示
        if len(new_employees) >= 30:
            estimated_duties = (len(new_employees) - 5) // 3  # バッファ5名除いて3名体制
            st.info(f"💡 推定対応可能勤務数: 約{estimated_duties}勤務（3名体制想定）")
        
        # 従業員保存機能
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("💾 全設定を保存", type="primary"):
                if len(new_employees) >= 2:
                    # Config Managerに保存
                    self.config_manager.update_employees(new_employees)
                    
                    # セッション状態を強制更新
                    st.session_state.last_employees = new_employees.copy()
                    
                    # 🆕 統合設定への保存
                    if self._is_unified_config_active():
                        # アクティブな統合設定に自動保存
                        self._auto_save_unified_config()
                        current_config_name = self._get_current_unified_config_name()
                        current_file = st.session_state.current_unified_config
                        st.success(f"✅ 統合設定 {current_config_name} に保存しました")
                        st.success(f"👥 従業員数: {len(new_employees)}名")
                        st.info(f"📁 保存先: {current_file}")
                    else:
                        # 統合設定がない場合は新規作成を促す
                        st.info("📝 統合設定ファイルがアクティブではありません")
                        if st.button("🆕 新しい統合設定として保存", key="create_new_unified"):
                            config_name = "従業員設定_" + datetime.now().strftime("%Y%m%d")
                            self._save_unified_config_complete(config_name)
                    
                    # 保存後は saved_employees を更新
                    saved_employees = new_employees.copy()
                    st.rerun()
                else:
                    st.error("❌ 従業員は最低2名必要です")
        
        with col2:
            if st.button("🔄 元に戻す"):
                default_employees = self.config_manager.default_config["employees"].copy()
                self.config_manager.current_config["employees"] = default_employees
                st.session_state.last_employees = default_employees
                
                # 🆕 統合設定への自動保存
                if self._is_unified_config_active():
                    self._auto_save_unified_config()
                    current_config_name = self._get_current_unified_config_name()
                    st.success(f"✅ デフォルト従業員設定に戻し、{current_config_name} に保存しました")
                else:
                    st.success("✅ デフォルト従業員設定に戻しました")
                    
                st.rerun()
        
        # 従業員リストが変更されたかチェック（表示用）
        if 'last_employees' not in st.session_state:
            st.session_state.last_employees = saved_employees
        
        # 現在の従業員を設定（保存されたものを使用）
        self.employees = saved_employees
        
        # 変更がある場合の警告表示
        if new_employees != saved_employees:
            st.warning("⚠️ 従業員設定に変更があります。保存ボタンを押して保存してください。")
        
        # 前月末勤務設定
        st.header("🔄 前月末勤務情報")
        st.warning("⚠️ 前日勤務者は翌月1日目が自動的に非番になります")
        self.prev_schedule_data = self._create_prev_schedule_input(prev_month)
    
    def _get_prev_month_info(self):
        """前月情報取得"""
        if self.month == 1:
            return self.year - 1, 12
        else:
            return self.year, self.month - 1
    
    def _create_prev_schedule_input(self, prev_month_display):
        """前月末勤務入力UI（重複キー修正版）"""
        prev_schedule = {}
        PREV_DAYS_COUNT = 3  # 前月末3日分
        prev_year, prev_month = self._get_prev_month_info()
        prev_days = calendar.monthrange(prev_year, prev_month)[1]
        
        duty_options = ["未入力"] + self.location_manager.get_duty_names() + ["非番", "休"]
        
        for emp_idx, emp in enumerate(self.employees):
            with st.expander(f"{emp}の前月末勤務"):
                emp_schedule = []
                for i in range(PREV_DAYS_COUNT):
                    day_num = prev_days - PREV_DAYS_COUNT + i + 1
                    
                    # ユニークキー生成（従業員インデックス使用）
                    unique_key = f"prev_emp_{emp_idx}_day_{i}_{prev_month}_{self.year}"
                    
                    shift = st.selectbox(
                        f"{prev_month}月{day_num}日",
                        duty_options,
                        key=unique_key,
                        help=f"{'🚨 前日勤務なら翌月1日目は非番' if i == PREV_DAYS_COUNT-1 else ''}"
                    )
                    emp_schedule.append(shift)
                    
                    # リアルタイム警告
                    if i == PREV_DAYS_COUNT-1 and shift in self.location_manager.get_duty_names():
                        st.error(f"⚠️ {emp}は前日({prev_month}月{day_num}日)に{shift}勤務 → {self.month}月1日は非番")
                
                prev_schedule[emp] = emp_schedule
        
        return prev_schedule
    
    def _calculate_keijo_pattern(self, year, month):
        """警乗勤務日パターンを計算"""
        base_date = self.keijo_base_date
        month_start = date(year, month, 1)
        days_offset = (month_start - base_date).days
        
        keijo_work_days = []
        keijo_rest_days = []
        n_days = calendar.monthrange(year, month)[1]
        
        for d in range(n_days):
            day_num = d + 1
            if (days_offset + d) % 2 == 0:
                keijo_work_days.append(day_num)
            else:
                keijo_rest_days.append(day_num)
        
        # 表示用フォーマット
        work_str = f"{', '.join(map(str, keijo_work_days[:5]))}{'...' if len(keijo_work_days) > 5 else ''}"
        rest_str = f"{', '.join(map(str, keijo_rest_days[:5]))}{'...' if len(keijo_rest_days) > 5 else ''}"
        
        return {
            'work_days': work_str,
            'rest_days': rest_str,
            'total_work_days': len(keijo_work_days),
            'total_rest_days': len(keijo_rest_days)
        }
    
    def _create_calendar_input(self):
        """カレンダー入力（完全修正版）"""
        st.header("📅 希望入力")
        
        if not self.employees:
            st.warning("先に従業員を設定してください")
            return
        
        # 従業員選択（安全な処理）
        if not self.employees:
            st.warning("先に従業員を設定してください")
            return
        
        # 現在の従業員リストに存在しない選択をクリア
        if 'main_emp_select' in st.session_state:
            if st.session_state.main_emp_select not in self.employees:
                del st.session_state['main_emp_select']
        
        selected_emp = st.selectbox("従業員を選択", self.employees, key="main_emp_select")
        
        if selected_emp:
            # データ初期化
            if selected_emp not in st.session_state.calendar_data:
                st.session_state.calendar_data[selected_emp] = {
                    'holidays': [],
                    'duty_preferences': {}
                }
            
            # タブ方式
            tab1, tab2 = st.tabs(["🏖️ 休暇希望", "💼 勤務場所希望"])
            
            with tab1:
                # 現在の選択を表示
                current_holidays = st.session_state.calendar_data[selected_emp]['holidays']
                current_holiday_days = set()
                if current_holidays:
                    current_holiday_days = {d.day if isinstance(d, date) else d for d in current_holidays}
                    st.write(f"**現在の選択**: {sorted(current_holiday_days)}日")
                
                # 完全リセットボタン（先に配置）
                if st.button("🗑️ 休暇希望をクリア", key=f"clear_holidays_{selected_emp}"):
                    # データクリア
                    st.session_state.calendar_data[selected_emp]['holidays'] = []
                    # セッション状態をクリアして強制更新（完全版）
                    keys_to_delete = []
                    for key in st.session_state.keys():
                        if key.startswith(f"holiday_{selected_emp}_"):
                            keys_to_delete.append(key)
                    for key in keys_to_delete:
                        del st.session_state[key]
                    # 即座に再実行
                    st.success("✅ 休暇希望をクリアしました")
                    st.rerun()
                
                st.write("**複数日選択**:")
                
                # 新しい選択状態を追跡
                new_selected_days = []
                
                # 日付を4列で表示
                for row in range((self.n_days + 3) // 4):
                    cols = st.columns(4)
                    for col_idx, col in enumerate(cols):
                        day = row * 4 + col_idx + 1
                        if day <= self.n_days:
                            # チェックボックスの初期値は現在の選択状態
                            checkbox_key = f"holiday_{selected_emp}_{day}"
                            is_currently_selected = day in current_holiday_days
                            
                            # 強制的にセッション状態をチェック
                            if checkbox_key in st.session_state:
                                # セッション状態がある場合はそれを使用
                                checkbox_value = st.session_state[checkbox_key]
                            else:
                                # セッション状態がない場合は現在の選択状態を使用
                                checkbox_value = is_currently_selected
                            
                            # チェックボックス
                            is_checked = col.checkbox(
                                f"{day}日", 
                                value=checkbox_value,
                                key=checkbox_key
                            )
                            
                            # チェックされていたら新しい選択に追加
                            if is_checked:
                                day_date = date(self.year, self.month, day)
                                new_selected_days.append(day_date)
                
                # 選択状態を即座に更新（重要：ここで同期）
                if new_selected_days != st.session_state.calendar_data[selected_emp]['holidays']:
                    st.session_state.calendar_data[selected_emp]['holidays'] = new_selected_days
                    # 更新後の表示
                    if new_selected_days:
                        updated_days = [d.day for d in new_selected_days]
                        st.success(f"✅ 選択更新: {sorted(updated_days)}日")
            
            with tab2:
                # 勤務場所選択
                duty_names = self.location_manager.get_duty_names()
                
                duty_date = st.date_input(
                    "勤務希望日",
                    value=None,
                    min_value=date(self.year, self.month, 1),
                    max_value=date(self.year, self.month, self.n_days),
                    key=f"duty_date_{selected_emp}"
                )
                
                if duty_date:
                    preferred_duty = st.selectbox(
                        f"{duty_date.day}日の希望勤務場所",
                        duty_names,
                        key=f"duty_select_{selected_emp}_{duty_date.day}"
                    )
                    
                    if st.button(f"追加", key=f"add_duty_{selected_emp}_{duty_date.day}"):
                        st.session_state.calendar_data[selected_emp]['duty_preferences'][duty_date.day] = preferred_duty
                        st.success(f"{duty_date.day}日: {preferred_duty}希望を追加")
                        st.rerun()
                
                # 現在の勤務希望表示
                duty_prefs = st.session_state.calendar_data[selected_emp]['duty_preferences']
                if duty_prefs:
                    st.write("**現在の勤務希望:**")
                    for day, duty in sorted(duty_prefs.items()):
                        st.write(f"• {day}日: {duty}")
                    
                    # 一括削除ボタン
                    if st.button("🗑️ すべての勤務希望をクリア", key=f"clear_duty_prefs_{selected_emp}"):
                        st.session_state.calendar_data[selected_emp]['duty_preferences'] = {}
                        st.rerun()
    
    def _create_control_panel(self):
        """制御パネル"""
        st.header("🎛️ 生成制御")
        
        # 設定確認
        with st.expander("📊 設定確認"):
            total_holidays = 0
            total_duties = 0
            cross_constraints_preview = []
            
            # 希望統計
            for emp in self.employees:
                if emp in st.session_state.calendar_data:
                    emp_data = st.session_state.calendar_data[emp]
                    h_count = len(emp_data['holidays'])
                    d_count = len(emp_data['duty_preferences'])
                    total_holidays += h_count
                    total_duties += d_count
                    
                    if h_count > 0 or d_count > 0:
                        st.write(f"**{emp}**: 休暇{h_count}件, 勤務希望{d_count}件")
            
            # 月またぎ制約予測
            for emp in self.employees:
                if emp in self.prev_schedule_data:
                    emp_data = self.prev_schedule_data[emp]
                    if len(emp_data) >= 1:
                        last_shift = emp_data[-1]
                        if last_shift in self.location_manager.get_duty_names():
                            cross_constraints_preview.append(f"{emp}: 前日{last_shift}勤務 → 1日目非番")
            
            st.write(f"**合計**: 休暇希望{total_holidays}件, 勤務希望{total_duties}件")
            
            if cross_constraints_preview:
                st.write("**予想される月またぎ制約**:")
                for constraint in cross_constraints_preview:
                    st.write(f"- {constraint}")
            else:
                st.write("**月またぎ制約**: なし")
        
        # 生成ボタン
        if st.button("🚀 勤務表を生成", type="primary", use_container_width=True):
            self._generate_schedule()
    
    def _generate_schedule(self):
        """勤務表生成"""
        with st.spinner("勤務表を生成中..."):
            try:
                result = self.engine.solve_schedule(
                    year=self.year,
                    month=self.month,
                    employee_names=self.employees,
                    calendar_data=st.session_state.calendar_data,
                    prev_schedule_data=self.prev_schedule_data,
                    keijo_base_date=datetime.combine(KEIJO_BASE_DATE, datetime.min.time())
                )
                
                if result['success']:
                    st.success("✅ 勤務表が生成されました！")
                    self._show_results(result)
                else:
                    # 改善されたエラー表示（原因分析機能付き）
                    failure_analysis = result.get('failure_analysis')
                    
                    if failure_analysis:
                        # 原因分析結果を表示
                        st.error(f"❌ 勤務表作成失敗：{failure_analysis['reason']}")
                        
                        # 詳細説明
                        st.markdown("### 📅 **問題**")
                        detail_lines = failure_analysis['detail'].split('\\n')
                        for line in detail_lines:
                            if line.strip():
                                st.write(f"   {line}")
                        
                        # 対処法
                        st.markdown("### 💡 **対処法**")
                        for solution in failure_analysis['solutions']:
                            st.write(f"   • {solution}")
                            
                        # デバッグ情報は展開可能に
                        with st.expander("🔍 デバッグ情報"):
                            self._show_debug_info(result.get('debug_info', []))
                    else:
                        # 従来のエラー表示（分析機能が利用できない場合）
                        st.error(f"❌ {result['error']}")
                        self._show_debug_info(result.get('debug_info', []))
                    
            except Exception as e:
                st.error(f"❌ エラー: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
    
    def _show_results(self, result):
        """結果表示（簡略表記版）"""
        st.subheader(f"📋 生成された勤務表 (緩和レベル {result['relax_level']})")
        
        solver = result['solver']
        w = result['w']
        employees = result['employees']
        n_days = result['n_days']
        location_manager = result['location_manager']
        
        duty_names = location_manager.get_duty_names()
        
        # テーブル作成
        table_data = []
        
        for emp_id, emp_name in enumerate(employees):
            row = [emp_name]
            for day in range(min(15, n_days)):  # 最初の15日
                assigned = "?"
                
                # 勤務場所チェック
                for duty_id, duty_name in enumerate(duty_names):
                    if solver.Value(w[emp_id, day, duty_id]):
                        assigned = duty_name
                        break
                
                # 休暇チェック
                if assigned == "?":
                    holiday_shift_id = len(duty_names)
                    if solver.Value(w[emp_id, day, holiday_shift_id]):
                        assigned = "休"  # 簡略表記
                
                # 非番チェック
                if assigned == "?":
                    off_shift_id = self.engine.OFF_SHIFT_ID
                    if solver.Value(w[emp_id, day, off_shift_id]):
                        assigned = "-"  # 簡略表記
                
                row.append(assigned)
            
            table_data.append(row)
        
        # 表示
        headers = ["従業員"] + [f"{d+1}日" for d in range(min(15, n_days))]
        
        import pandas as pd
        df = pd.DataFrame(table_data, columns=headers)
        st.dataframe(df, use_container_width=True)
        
        if n_days > 15:
            st.info(f"最初の15日のみ表示（全{n_days}日）")
        
        # Excel生成とダウンロード
        self._create_excel_download(result)
        
        # 詳細分析表示
        self._show_detailed_analysis(result)
    
    def _create_excel_download(self, result):
        """Excel生成とダウンロード（改善版）"""
        st.subheader("📁 Excel出力")
        
        try:
            # 一時ファイルでExcel生成
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                excel_path = self.excel_exporter.create_excel_file(tmp_file.name, result)
                
                with open(excel_path, 'rb') as f:
                    excel_data = f.read()
                
                # ファイル名
                filename = f"勤務表_{self.year}年{self.month:02d}月_完全版.xlsx"
                
                # ファイルサイズ表示
                file_size = len(excel_data) / 1024  # KB
                st.info(f"📊 Excel生成完了 (サイズ: {file_size:.1f} KB)")
                
                # ダウンロードボタン（2つの方法）
                col1, col2 = st.columns(2)
                
                with col1:
                    # 通常のダウンロードボタン
                    st.download_button(
                        "📥 Excel勤務表をダウンロード",
                        data=excel_data,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                
                with col2:
                    # 代替ダウンロード方法の説明
                    st.info("💡 ダウンロードできない場合は、ブラウザの設定でダウンロードを許可してください")
                
                # 一時ファイル削除
                os.unlink(excel_path)
                
                st.success("✅ Excel勤務表が正常に生成されました")
                st.markdown("**含まれるシート:**")
                st.markdown("- 📋 **勤務表**: メイン勤務表（色分け付き）")
                st.markdown("- 📊 **統計**: 個人別勤務統計")
                if result.get('prev_duties'):
                    st.markdown("- 🔄 **月またぎ制約分析**: 前月末勤務の影響分析")
                st.markdown("- 📝 **制約緩和レポート**: 最適化の詳細情報")
                
        except Exception as e:
            st.error(f"❌ Excel生成エラー: {str(e)}")
            st.warning("Excelの生成に失敗しました。画面上の表をコピーしてご利用ください。")
    
    def _show_detailed_analysis(self, result):
        """詳細分析表示"""
        # 月またぎ制約分析
        if result.get('cross_analysis'):
            with st.expander("🔄 月またぎ制約分析結果"):
                violation_count = 0
                for analysis in result['cross_analysis']:
                    st.write(f"**{analysis['name']}**:")
                    st.write(f"  前月末: {'; '.join(analysis['prev_month'])}")
                    st.write(f"  当月初: {'; '.join(analysis['current_month'])}")
                    st.write(f"  制約違反: {'; '.join(analysis['violations'])}")
                    st.write(f"  適用制約: {'; '.join(analysis['constraints_applied'])}")
                    
                    if any("❌" in v for v in analysis['violations']):
                        violation_count += 1
                    st.write("---")
                
                if violation_count == 0:
                    st.success("🎉 月またぎ制約違反なし！")
                else:
                    st.error(f"❌ 制約違反が {violation_count} 件残っています")
        
        # 制約緩和情報
        with st.expander("🔍 詳細情報"):
            st.write(f"**制約緩和レベル**: {result['relax_level']}")
            st.write(f"**最適化ステータス**: {result['solver'].StatusName(result['status'])}")
            st.write("**制約緩和メッセージ**:")
            for note in result.get('relax_notes', []):
                st.write(f"- {note}")
            st.write("**適用された月またぎ制約**:")
            for constraint in result.get('cross_constraints', []):
                st.write(f"- {constraint}")
        
        # 優先度設定適用状況
        with st.expander("🎯 優先度設定適用状況"):
            self._show_priority_application_status(result)
        
        # デバッグ情報
        with st.expander("🔍 パース結果デバッグ"):
            self._show_debug_info(result.get('debug_info', []))
    
    def _show_priority_application_status(self, result):
        """優先度設定適用状況の表示"""
        try:
            # 現在の優先度設定を取得
            current_priorities = self.config_manager.get_employee_priorities()
            
            if not current_priorities:
                st.warning("⚠️ 優先度設定が見つかりません")
                return
            
            st.write("**現在の優先度設定**:")
            
            # 優先度設定を表形式で表示
            import pandas as pd
            priority_data = []
            
            for emp_name, priorities in current_priorities.items():
                row = {"従業員": emp_name}
                for duty_name, priority in priorities.items():
                    priority_emoji = ["❌", "🟡", "🔵", "✅"][priority] if 0 <= priority <= 3 else "❓"
                    row[duty_name] = f"{priority} {priority_emoji}"
                priority_data.append(row)
            
            if priority_data:
                df = pd.DataFrame(priority_data)
                st.dataframe(df, use_container_width=True)
                
                # 優先度の効果分析
                st.write("**優先度効果分析**:")
                preferences = result.get('preferences', {})
                priority_effects = 0
                
                for (emp_id, day, duty_id), penalty in preferences.items():
                    if penalty != 0:  # ペナルティが設定されている場合
                        priority_effects += 1
                
                st.write(f"- 適用されたペナルティ/報酬: {priority_effects}件")
                
                # デバッグ情報から優先度関連を抽出
                debug_info = result.get('debug_info', [])
                priority_debug = [info for info in debug_info if "優先度" in info or "ペナルティ" in info]
                
                if priority_debug:
                    st.write("**優先度適用詳細**:")
                    for info in priority_debug[:10]:  # 最初の10件のみ表示
                        st.write(f"- {info}")
                    if len(priority_debug) > 10:
                        st.write(f"... 他 {len(priority_debug) - 10} 件")
                else:
                    st.warning("⚠️ 優先度適用ログが見つかりません")
            else:
                st.warning("⚠️ 優先度設定データがありません")
                
        except Exception as e:
            st.error(f"❌ 優先度状況表示エラー: {str(e)}")
    
    def _show_debug_info(self, debug_info):
        """デバッグ情報表示"""
        if debug_info:
            for info in debug_info:
                if "❌" in info:
                    st.error(info)
                elif "⚠️" in info:
                    st.warning(info)
                elif "✅" in info:
                    st.success(info)
                else:
                    st.info(info)
        else:
            st.info("デバッグ情報はありません")
    
    def _create_unified_config_section(self):
        """🆕 統合設定管理セクション"""
        st.header("📁 設定管理")
        
        # 統合設定ファイル一覧
        unified_configs = self.unified_config.get_unified_config_files()
        
        if unified_configs:
            st.subheader("📥 設定読み込み")
            selected_config = st.selectbox(
                "設定ファイル",
                ["--- 選択してください ---"] + unified_configs,
                key="unified_config_select"
            )
            
            if selected_config != "--- 選択してください ---":
                # プレビュー表示
                preview = self.unified_config.get_config_preview(selected_config)
                if "error" not in preview:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.text(f"📝 名前: {preview['config_name']}")
                        st.text(f"📅 作成: {preview['created_date']}")
                        st.text(f"👥 従業員: {preview['employees_count']}名")
                    with col2:
                        st.text(f"🏢 勤務場所: {preview['work_locations_count']}箇所")
                        st.text(f"📋 カレンダー: {'有' if preview['has_calendar_data'] else '無'}")
                        st.text(f"🚔 警乗: {'有効' if preview['keijo_enabled'] else '無効'}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button(f"📥 {selected_config}を読み込み", type="primary", key="load_unified"):
                        self._load_unified_config_complete(selected_config)
                
                with col2:
                    if st.button("💾 現在設定で上書き保存", key="overwrite_unified"):
                        config_name = selected_config.split('_')[0]  # ファイル名から設定名を抽出
                        self._save_unified_config_complete(config_name)
        
        # 新規設定保存
        st.subheader("💾 新規設定")
        new_config_name = st.text_input("設定名", placeholder="金沢警備隊", key="new_unified_config_name")
        
        if st.button("💾 全設定を保存", type="primary", key="save_new_unified"):
            if new_config_name.strip():
                self._save_unified_config_complete(new_config_name.strip())
            else:
                st.error("設定名を入力してください")
    
    def _load_unified_config_complete(self, filename):
        """統合設定の完全読み込み"""
        try:
            config = self.unified_config.load_complete_config(filename)
            
            if config:
                # 🆕 現在アクティブな統合設定を記録
                st.session_state.current_unified_config = filename
                st.session_state.unified_config_auto_save = True
                
                # 🔧 重要: location_managerの状態を統合設定に合わせて強制更新
                work_locations = config.get("work_locations", [])
                if work_locations:
                    self.location_manager.duty_locations = work_locations.copy()
                    # ConfigManagerの状態も同期
                    self.config_manager.current_config["work_locations"] = work_locations.copy()
                    
                # 🔧 重要: 従業員設定も強制更新
                employees = config.get("employees", [])
                if employees:
                    st.session_state.last_employees = employees.copy()
                    self.config_manager.current_config["employees"] = employees.copy()
                
                st.success(f"✅ {filename}を完全読み込みしました")
                st.success("🔄 設定反映のため画面を更新します...")
                st.info(f"🔗 以降の設定変更は自動的に{filename}に保存されます")
                
                # 読み込み後の情報表示
                st.info(f"📋 反映内容: 従業員{len(employees)}名, 勤務場所{len(work_locations)}箇所")
                
                # 即座にUIを更新
                st.rerun()
            else:
                st.error("❌ 設定の読み込みに失敗しました")
                
        except Exception as e:
            st.error(f"❌ 設定読み込みエラー: {str(e)}")
    
    def _initialize_from_existing_config(self):
        """初期化時に既存の統合設定があれば読み込み"""
        try:
            if 'current_unified_config' in st.session_state and st.session_state.current_unified_config:
                filename = st.session_state.current_unified_config
                
                # ファイルが存在するか確認
                if self.unified_config:
                    available_configs = self.unified_config.get_unified_config_files()
                    if filename in available_configs:
                        # 設定を静かに読み込み（メッセージなし）
                        config = self.unified_config.load_complete_config(filename, force_update_session=False)
                        
                        if config:
                            # location_managerとconfig_managerに設定を反映
                            work_locations = config.get("work_locations", [])
                            if work_locations:
                                self.location_manager.duty_locations = work_locations.copy()
                                self.config_manager.current_config["work_locations"] = work_locations.copy()
                            
                            employees = config.get("employees", [])
                            if employees:
                                self.config_manager.current_config["employees"] = employees.copy()
                            
                            # 優先度設定の反映
                            priorities = config.get("employee_priorities", {})
                            if priorities:
                                self.config_manager.current_config["employee_priorities"] = priorities.copy()
                    else:
                        # ファイルが見つからない場合はセッション状態をクリア
                        st.session_state.current_unified_config = None
                        
        except Exception as e:
            # 初期化時のエラーは静かに処理
            pass
    
    def _ensure_config_sync(self):
        """統合設定との同期を確認（毎回実行時）"""
        try:
            if (self._is_unified_config_active() and 
                'current_unified_config' in st.session_state and 
                st.session_state.current_unified_config):
                
                # 統合設定ファイルの最終更新時刻を確認
                filename = st.session_state.current_unified_config
                if self.unified_config and filename in self.unified_config.get_unified_config_files():
                    filepath = os.path.join(self.unified_config.configs_dir, filename)
                    
                    # ファイルの変更時刻をチェック（他の処理で更新されている可能性）
                    if os.path.exists(filepath):
                        # 設定を再読み込み（静かに実行）
                        config = self.unified_config.load_complete_config(filename, force_update_session=False)
                        
                        if config:
                            # LocationManagerとConfigManagerに最新設定を反映
                            work_locations = config.get("work_locations", [])
                            if work_locations and work_locations != self.location_manager.duty_locations:
                                self.location_manager.duty_locations = work_locations.copy()
                                self.config_manager.current_config["work_locations"] = work_locations.copy()
                            
                            employees = config.get("employees", [])
                            if employees and employees != st.session_state.get('last_employees', []):
                                st.session_state.last_employees = employees.copy()
                                self.config_manager.current_config["employees"] = employees.copy()
                            
                            priorities = config.get("employee_priorities", {})
                            if priorities:
                                self.config_manager.current_config["employee_priorities"] = priorities.copy()
                    
        except Exception as e:
            # 同期エラーは静かに処理（ユーザーには表示しない）
            pass
    
    def _save_unified_config_complete(self, config_name):
        """統合設定の完全保存"""
        try:
            # 現在のGUI状態を収集
            gui_state = {
                'last_employees': getattr(self, 'employees', st.session_state.get('last_employees', [])),
                'keijo_base_date': getattr(self, 'keijo_base_date', date(2025, 6, 1)),
                'year': getattr(self, 'year', 2025),
                'month': getattr(self, 'month', 6)
            }
            
            filename = self.unified_config.save_complete_config(
                config_name, 
                st.session_state, 
                gui_state
            )
            
            if filename:
                # 🆕 新規保存の場合は現在アクティブ設定に設定
                st.session_state.current_unified_config = filename
                st.session_state.unified_config_auto_save = True
                
                st.success(f"✅ {filename}として統合保存しました")
                st.info("📋 保存内容: 従業員・勤務場所・優先度・年休申請・警乗設定・すべて")
                st.info(f"🔗 以降の設定変更は自動的に{filename}に保存されます")
                
                # 保存後の詳細情報表示
                employees_count = len(gui_state.get('last_employees', []))
                locations_count = len(self.location_manager.get_duty_locations())
                calendar_data_count = len(st.session_state.get('calendar_data', {}))
                
                st.text(f"💾 詳細: 従業員{employees_count}名, 勤務場所{locations_count}箇所, カレンダー項目{calendar_data_count}件")
            else:
                st.error("❌ 保存に失敗しました")
                
        except Exception as e:
            st.error(f"❌ 設定保存エラー: {str(e)}")
    
    def _auto_save_unified_config(self):
        """🆕 統合設定の自動保存"""
        try:
            if (st.session_state.get('current_unified_config') and 
                st.session_state.get('unified_config_auto_save', True)):
                
                current_config = st.session_state.current_unified_config
                config_name = current_config.split('_')[0]  # ファイル名から設定名を抽出
                
                # 現在のGUI状態を収集
                gui_state = {
                    'last_employees': getattr(self, 'employees', st.session_state.get('last_employees', [])),
                    'keijo_base_date': getattr(self, 'keijo_base_date', date(2025, 6, 1)),
                    'year': getattr(self, 'year', 2025),
                    'month': getattr(self, 'month', 6)
                }
                
                # 既存ファイルを上書き保存
                success = self.unified_config.overwrite_config(
                    current_config,
                    config_name,
                    st.session_state,
                    gui_state
                )
                
                if success:
                    # サイレント保存（UIには表示しない）
                    pass
                else:
                    # エラー時のみ表示
                    st.warning(f"⚠️ 自動保存に失敗: {current_config}")
                    
        except Exception as e:
            # エラー時のみ表示
            st.warning(f"⚠️ 自動保存エラー: {str(e)}")
    
    def _is_unified_config_active(self):
        """🆕 統合設定がアクティブかチェック"""
        return st.session_state.get('current_unified_config') is not None
    
    def _get_current_unified_config_name(self):
        """🆕 現在の統合設定名を取得"""
        current_config = st.session_state.get('current_unified_config')
        if current_config:
            return current_config.split('_')[0]  # ファイル名から設定名を抽出
        return None
    
    def _show_config_selector(self):
        """🆕 設定ファイル選択画面"""
        st.markdown("---")
        st.header("📁 設定ファイル選択")
        
        # 閉じるボタン
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("❌ 閉じる"):
                st.session_state.show_config_selector = False
                st.rerun()
        
        # 統合設定ファイル一覧
        unified_configs = self.unified_config.get_unified_config_files()
        
        if unified_configs:
            st.subheader("📋 利用可能な設定ファイル")
            
            for filename in unified_configs:
                # プレビュー取得
                preview = self.unified_config.get_config_preview(filename)
                
                if "error" not in preview:
                    # ファイル情報表示
                    with st.expander(f"📄 {filename}", expanded=False):
                        col1, col2, col3 = st.columns([2, 2, 1])
                        
                        with col1:
                            st.text(f"📝 設定名: {preview['config_name']}")
                            st.text(f"📅 作成日: {preview['created_date']}")
                            st.text(f"👥 従業員: {preview['employees_count']}名")
                        
                        with col2:
                            st.text(f"🏢 勤務場所: {preview['work_locations_count']}箇所")
                            st.text(f"📋 カレンダー: {'有' if preview['has_calendar_data'] else '無'}")
                            st.text(f"🚔 警乗: {'有効' if preview['keijo_enabled'] else '無効'}")
                        
                        with col3:
                            # 選択ボタン
                            if st.button(f"✅ この設定を選択", key=f"select_{filename}"):
                                # 設定を読み込み
                                self._load_unified_config_complete(filename)
                                st.session_state.show_config_selector = False
                                st.success(f"✅ {filename} を読み込みました")
                                st.rerun()
                            
                            # 現在アクティブかチェック
                            if st.session_state.get('current_unified_config') == filename:
                                st.success("🔗 アクティブ")
                else:
                    st.error(f"❌ {filename}: 読み込みエラー")
        else:
            st.info("📝 利用可能な設定ファイルがありません")
            st.info("💡 メインページで新しい設定を作成してください")
        
        st.markdown("---")


# =================== メイン実行 ===================

def main():
    """メイン関数"""
    try:
        # 🔧 CompleteGUIインスタンスをセッション状態で保持（重要な修正）
        if 'gui_instance' not in st.session_state:
            st.session_state.gui_instance = CompleteGUI()
        
        gui = st.session_state.gui_instance
        gui.run()
        
        # フッター
        st.markdown("---")
        st.markdown("🚀 **としかず隊専用**: 固定設定で高速動作")
        st.markdown("🎯 **5段階優先度**: 細かい調整可能")
        
        # システム情報
        with st.expander("ℹ️ システム情報"):
            st.write("**としかず隊専用機能**:")
            st.write("- ✅ **8名固定**: 中谷、宮崎、木村、田中、谷村、新蔵、川口、杉本")
            st.write("- ✅ **3勤務固定**: A、D、警乗")
            st.write("- ✅ **5段階優先度**: 0=不可, 1=可, 2=普通, 3=やや優先, 4=優先, 5=最優先")
            st.write("- ✅ **月またぎ制約**: 前日勤務→翌月１日非番")
            st.write("- ✅ **警乗隔日制約**: 隔日勤務システム")
            st.write("- ✅ **Excel色分け出力**: 優先度反映表示")
            
            st.write("**優先度システム**:")
            st.write("- ✅ **最優先(5)**: ペナルティなし")
            st.write("- 🟢 **優先(4)**: 軽微ペナルティ")
            st.write("- 🔵 **やや優先(3)**: 小ペナルティ")
            st.write("- 🟡 **普通(2)**: 中ペナルティ")
            st.write("- 🟠 **可能(1)**: 高ペナルティ")
            st.write("- ❌ **不可(0)**: 最高ペナルティ")
            
            st.write("**色分け説明**:")
            st.write("- 🟡 **黄色**: 有休実現")
            st.write("- 🔴 **ピンク**: 有休希望なのに勤務")
            st.write("- 🔵 **青色**: 助勤勤務")
            st.write("- 🟠 **オレンジ**: シフト希望未実現")
            st.write("- 🟣 **紫色**: 月またぎ制約による配置")
    
    except Exception as e:
        st.error(f"❌ システムエラー: {str(e)}")
        import traceback
        st.code(traceback.format_exc())


if __name__ == "__main__":
    main()
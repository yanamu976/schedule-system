#!/usr/bin/env python3
"""
勤務表自動作成システム 完全版
- 月またぎ制約完全対応（前月末勤務処理）
- 複数勤務場所対応（駅A、指令、警乗等）
- 非番自動処理
- カレンダー複数選択対応
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


# =================== 設定管理システム（Phase 1） ===================

class ConfigurationManager:
    """Phase 1: 最小限設定管理クラス"""
    
    def __init__(self):
        self.configs_dir = "configs"
        self.ensure_configs_dir()
        
        # デフォルト設定
        self.default_config = {
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
            "priority_weights": {"0": 1000, "1": 10, "2": 5, "3": 0}
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
        """優先度重み取得"""
        weights = self.current_config.get("priority_weights", self.default_config["priority_weights"])
        return {int(k): v for k, v in weights.items()}
    
    def update_employee_priorities(self, priorities):
        """従業員優先度更新"""
        self.current_config["employee_priorities"] = priorities
    
    def get_employees(self):
        """従業員リスト取得"""
        return self.current_config.get("employees", ["Aさん", "Bさん", "Cさん", "Dさん", "Eさん", "Fさん", "Gさん", "助勤"])
    
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
            1: "⚠️ 二徹バランス緩和（格差許容）",
            2: "⚠️ 助勤フル解禁（ペナルティ低減）", 
            3: "⚠️ 有休の一部を勤務変更（休多→勤務優先）"
        }
    
    def update_weights(self, new_weights):
        """重みパラメータを更新"""
        self.weights.update(new_weights)
    
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
                            
                            # 優先度に基づいたペナルティ設定
                            for day in range(n_days):
                                if penalty > 0:  # ペナルティありの場合
                                    preferences[(emp_id, day, duty_id)] = penalty
                                    
                            debug_info.append(f"✅ {emp_name}:{duty_name}優先度{priority}(ペナルティ{penalty})適用")
        
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
                                relax_level=0, prev_duties=None):
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
        
        # 基本制約2: 各勤務場所は1日1人
        for d in range(n_days):
            for s in range(self.n_duties):
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
        
        # 🔥 月またぎ制約（完全修正版）
        cross_month_constraints = []
        cross_month_nitetu_vars = []
        
        if prev_duties:
            for e in range(self.n_employees):
                emp_name = self.id_to_name[e]
                
                # 制約1: 前日勤務なら1日目は必ず非番
                if (e, -1) in prev_duties and prev_duties[(e, -1)]:
                    model.Add(w[e, 0, self.OFF_SHIFT_ID] == 1)
                    cross_month_constraints.append(f"{emp_name}: 前日勤務 → 1日目非番強制")
                
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
        relief_weight = self.weights['RELIEF'] if relax_level < 2 else self.weights['RELIEF'] // 10
        
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
        
        # 目的関数
        objective_terms = [
            relief_weight * sum(relief_work_vars),
            holiday_weight * sum(holiday_violations),
            self.weights['NITETU'] * sum(nitetu_vars),
            self.weights['CROSS_MONTH'] * sum(cross_month_nitetu_vars)
        ]
        
        if nitetu_gap != 0:
            objective_terms.append(self.weights['N2_GAP'] * nitetu_gap)
        
        objective_terms.extend(preference_terms)
        model.Minimize(sum(objective_terms))
        
        return model, w, nitetu_counts, cross_month_constraints
    
    def solve_with_relaxation(self, n_days, ng_constraints, preferences, holidays, prev_duties=None):
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
                n_days, ng_constraints, preferences, holidays_to_use, relax_level, prev_duties
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
    
    def solve_schedule(self, year, month, employee_names, calendar_data, prev_schedule_data=None):
        """スケジュール求解（Phase 1: 優先度対応版）"""
        n_days = calendar.monthrange(year, month)[1]
        self.setup_system(employee_names)
        
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
        result = self.solve_with_relaxation(n_days, ng_constraints, preferences, holidays, prev_duties)
        relax_level_used, status, solver, w, nitetu_counts, relax_notes, cross_constraints = result
        
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
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
        self.engine = CompleteScheduleEngine(self.location_manager, self.config_manager)
        self.excel_exporter = ExcelExporter(self.engine)
        
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
        """メイン実行"""
        self._setup_page()
        
        if st.session_state.show_config:
            self._configuration_page()
        elif st.session_state.show_priority_settings:
            self._priority_settings_page()
        else:
            self._main_page()
    
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
    
    def _configuration_page(self):
        """設定ページ（修正版）"""
        st.header("⚙️ 詳細設定")
        
        # 戻るボタン
        if st.button("← メインページに戻る"):
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
        
        # 変更があった場合は自動保存
        if changes_made:
            self.location_manager.save_config()
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
                                st.success(f"「{add_name}」を追加しました")
                                st.rerun()
                            else:
                                st.error("保存に失敗しました")
                    else:
                        st.error("勤務場所名を入力してください")
        else:
            st.warning("⚠️ 最大15勤務場所まで追加できます")
        
        # 保存ボタン
        if st.button("💾 設定を保存", type="primary"):
            self.location_manager.save_config()
            st.success("✅ 設定を保存しました")
    
    def _priority_settings_page(self):
        """優先度設定ページ（Phase 1）"""
        st.header("🎯 従業員優先度設定")
        
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
        
        # 動的な従業員設定（助勤除く）
        # セッション状態から従業員リストを取得
        if 'last_employees' in st.session_state and st.session_state.last_employees:
            all_employees = st.session_state.last_employees
            target_employees = [emp for emp in all_employees if emp != "助勤"]  # 制限なしで全従業員表示
        elif hasattr(self, 'employees') and self.employees:
            target_employees = [emp for emp in self.employees if emp != "助勤"]  # 制限なしで全従業員表示
        else:
            # デフォルト従業員設定
            target_employees = ["Aさん", "Bさん", "Cさん"]
        
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
        
        config_name = st.text_input(
            "設定名",
            value="新しい設定",
            help="日本語名も使用可能です"
        )
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("💾 一時保存", type="primary"):
                # メモリに保存（セッション間のみ）
                self.config_manager.update_employee_priorities(new_priorities)
                st.success("✅ 一時保存しました（セッション間有効）")
        
        with col2:
            if st.button("📁 ファイル保存"):
                if config_name.strip():
                    filename = self.config_manager.save_config(config_name.strip(), new_priorities)
                    if filename:
                        st.success(f"✅ {filename}として保存しました")
                    else:
                        st.error("⚠ 保存に失敗しました")
                else:
                    st.error("設定名を入力してください")
        
        with col3:
            if st.button("🔄 デフォルトに戻す"):
                default_priorities = self.config_manager.default_config["employee_priorities"]
                self.config_manager.update_employee_priorities(default_priorities)
                st.success("✅ デフォルト設定に戻しました")
                st.rerun()
        
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
        
        # Phase 1: 設定ファイル選択
        st.subheader("📁 設定選択")
        config_files = self.config_manager.get_config_files()
        
        if config_files:
            selected_file = st.selectbox(
                "設定ファイル",
                ["--- 選択してください ---"] + config_files,
                key="config_file_select"
            )
            
            if selected_file != "--- 選択してください ---":
                if st.button(f"📥 {selected_file}を読み込み"):
                    if self.config_manager.load_config(selected_file):
                        st.session_state.selected_config = selected_file
                        # 従業員設定も強制更新
                        employees = self.config_manager.get_employees()
                        st.session_state.last_employees = employees.copy()
                        # 関連データをクリア
                        st.session_state.calendar_data = {}
                        st.success(f"✅ {selected_file}を読み込みました")
                        st.success(f"👥 従業員: {len(employees)}名 - {', '.join(employees[:5])}{'...' if len(employees) > 5 else ''}")
                        st.rerun()
                    else:
                        st.error("❗ 設定の読み込みに失敗しました")
        else:
            st.info("設定ファイルがありません")
        
        # 現在の設定表示
        if st.session_state.selected_config:
            st.success(f"現在: {st.session_state.selected_config}")
        
        st.markdown("---")
        
        # 年月設定（最優先）
        self.year = st.number_input("年", value=2025, min_value=2020, max_value=2030)
        self.month = st.selectbox("月", range(1, 13), index=5)
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
        
        # Phase 1: 優先度設定ボタン
        if st.button("🎯 優先度設定", use_container_width=True):
            st.session_state.show_priority_settings = True
            st.rerun()
        
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
            if st.button("💾 従業員設定を保存", type="primary"):
                if len(new_employees) >= 2:
                    # Config Managerに保存
                    self.config_manager.update_employees(new_employees)
                    
                    # セッション状態を強制更新
                    st.session_state.last_employees = new_employees.copy()
                    st.session_state.calendar_data = {}
                    
                    # 設定ファイルに保存
                    filename = self.config_manager.save_config("従業員設定_自動保存")
                    if filename:
                        st.success(f"✅ 従業員設定を保存しました ({filename})")
                        st.success(f"👥 従業員数: {len(new_employees)}名")
                    else:
                        st.success("✅ 従業員設定を一時保存しました")
                    
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
    
    def _create_prev_schedule_input(self, prev_month):
        """前月末勤務入力UI（重複キー修正版）"""
        prev_schedule = {}
        PREV_DAYS_COUNT = 3  # 前月末3日分
        prev_year, _ = self._get_prev_month_info()
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
                    prev_schedule_data=self.prev_schedule_data
                )
                
                if result['success']:
                    st.success("✅ 勤務表が生成されました！")
                    self._show_results(result)
                else:
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
        
        # デバッグ情報
        with st.expander("🔍 パース結果デバッグ"):
            self._show_debug_info(result.get('debug_info', []))
    
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


# =================== メイン実行 ===================

def main():
    """メイン関数"""
    try:
        gui = CompleteGUI()
        gui.run()
        
        # フッター
        st.markdown("---")
        st.markdown("💡 **Phase 1**: 優先度設定と設定保存機能が完全動作します")
        st.markdown("🎯 **重要**: 優先度が勤務表に反映され、設定保存で再利用可能です")
        
        # システム情報
        with st.expander("ℹ️ システム情報"):
            st.write("**Phase 1 機能一覧**:")
            st.write("- ✅ **優先度設定**: 3人分の勤務場所優先度設定")
            st.write("- ✅ **設定保存/読み込み**: JSONファイルで設定管理")
            st.write("- ✅ **月またぎ制約**: 前日勤務→翌月１日非番")
            st.write("- ✅ **複数勤務場所対応**: 駅A、指令、警乗等")
            st.write("- ✅ **Excel色分け出力**: 優先度反映表示")
            
            st.write("**優先度システム**:")
            st.write("- ✅ **最優先(3)**: ペナルティなし")
            st.write("- 🔵 **普通(2)**: 小ペナルティ")
            st.write("- 🟡 **可能(1)**: 軽微ペナルティ")
            st.write("- ❌ **不可(0)**: 高ペナルティ")
            
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
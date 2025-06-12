#!/usr/bin/env python3
"""
勤務表自動作成システム 修正版
- 月またぎ制約完全対応（前月末勤務処理）
- 複数勤務場所対応（駅A、指令、警乗等）
- 非番自動処理
- カレンダー複数選択対応
- Excel色分け出力
- シンプル・安定動作版
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


# =================== 勤務場所管理 ===================

# =================== 設定管理 ===================

class ConfigurationManager:
    """設定管理クラス（Phase 2: 大人数対応・高度制約対応）"""
    
    def __init__(self):
        self.configs_dir = "configs"
        self.current_config = None
        self.max_employees = 50  # Phase 2: 最大50人対応
        
        # デフォルト従業員設定（3人）
        self.default_employee_preferences = {
            "Aさん": {"駅A": 3, "指令": 2, "警乗": 0},
            "Bさん": {"駅A": 3, "指令": 3, "警乗": 3},
            "Cさん": {"駅A": 0, "指令": 0, "警乗": 3}
        }
        
        # Phase 2: 高度制約テンプレート
        self.employee_constraint_templates = {
            "基本制約": {
                "max_consecutive_days": 2,
                "prohibited_days": [],
                "required_rest_after": None,
                "skill_level": {},
                "weekly_hour_limit": 48,
                "monthly_holiday_min": 8
            },
            "管理職制約": {
                "max_consecutive_days": 3,
                "prohibited_days": [],
                "required_rest_after": None,
                "skill_level": {"駅A": "上級", "指令": "上級", "警乗": "上級"},
                "weekly_hour_limit": 60,
                "monthly_holiday_min": 6
            },
            "新人制約": {
                "max_consecutive_days": 1,
                "prohibited_days": [],
                "required_rest_after": "駅A",
                "skill_level": {"駅A": "初級", "指令": "初級", "警乗": "初級"},
                "weekly_hour_limit": 40,
                "monthly_holiday_min": 10
            }
        }
        
        self.priority_weights = {0: 1000, 1: 10, 2: 5, 3: 0}
        
        # Phase 2: 複数現場対応
        self.sites = {}  # 現場情報管理
        self.current_site = None  # 現在選択中の現場
    
    def get_config_files(self):
        """利用可能な設定ファイル一覧"""
        import glob
        import os
        if not os.path.exists(self.configs_dir):
            return []
        pattern = os.path.join(self.configs_dir, "*.json")
        files = glob.glob(pattern)
        return [os.path.basename(f) for f in files]
    
    def load_config(self, filename):
        """設定ファイル読み込み"""
        try:
            filepath = os.path.join(self.configs_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.current_config = config
                return True, config
        except Exception as e:
            return False, str(e)
    
    def save_config(self, config_data, filename):
        """設定ファイル保存"""
        try:
            os.makedirs(self.configs_dir, exist_ok=True)
            filepath = os.path.join(self.configs_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            return True, None
        except Exception as e:
            return False, str(e)
    
    def get_employee_preferences(self):
        """現在の従業員優先度設定取得"""
        if self.current_config and "employee_preferences" in self.current_config:
            return self.current_config["employee_preferences"]
        return self.default_employee_preferences
    
    def update_employee_preferences(self, preferences):
        """従業員優先度設定更新"""
        if not self.current_config:
            self.current_config = {
                "config_name": "新規設定",
                "created_date": datetime.now().strftime("%Y-%m-%d"),
                "site_name": "現場",
                "employee_preferences": {},
                "priority_weights": self.priority_weights,
                "description": "Phase 1設定"
            }
        self.current_config["employee_preferences"] = preferences
    
    def get_priority_penalty(self, employee_name, location_name, default_priority=2):
        """優先度をペナルティ重みに変換"""
        preferences = self.get_employee_preferences()
        
        if employee_name in preferences and location_name in preferences[employee_name]:
            priority = preferences[employee_name][location_name]
        else:
            priority = default_priority
        
        return self.priority_weights.get(priority, self.priority_weights[2])
    
    # Phase 2: 大人数対応拡張メソッド
    def add_employee(self, employee_name, preferences=None, constraints=None):
        """従業員追加（最大50人まで）"""
        current_prefs = self.get_employee_preferences()
        if len(current_prefs) >= self.max_employees:
            return False, f"最大従業員数({self.max_employees}人)に達しています"
        
        if employee_name in current_prefs:
            return False, f"{employee_name}は既に存在します"
        
        # デフォルト優先度設定
        if preferences is None:
            preferences = {"駅A": 2, "指令": 2, "警乗": 2}
        
        current_prefs[employee_name] = preferences
        
        # 制約設定（Phase 2）
        if constraints is None:
            constraints = self.employee_constraint_templates["基本制約"].copy()
        
        if not self.current_config:
            self.current_config = self._create_default_config()
        
        if "employee_constraints" not in self.current_config:
            self.current_config["employee_constraints"] = {}
        
        self.current_config["employee_constraints"][employee_name] = constraints
        self.update_employee_preferences(current_prefs)
        
        return True, None
    
    def remove_employee(self, employee_name):
        """従業員削除"""
        current_prefs = self.get_employee_preferences()
        if employee_name not in current_prefs:
            return False, f"{employee_name}が見つかりません"
        
        del current_prefs[employee_name]
        
        # 制約も削除
        if (self.current_config and 
            "employee_constraints" in self.current_config and 
            employee_name in self.current_config["employee_constraints"]):
            del self.current_config["employee_constraints"][employee_name]
        
        self.update_employee_preferences(current_prefs)
        return True, None
    
    def get_employee_constraints(self, employee_name=None):
        """従業員制約取得"""
        if not self.current_config or "employee_constraints" not in self.current_config:
            return {}
        
        if employee_name:
            return self.current_config["employee_constraints"].get(
                employee_name, self.employee_constraint_templates["基本制約"].copy()
            )
        
        return self.current_config["employee_constraints"]
    
    def update_employee_constraints(self, employee_name, constraints):
        """従業員制約更新"""
        if not self.current_config:
            self.current_config = self._create_default_config()
        
        if "employee_constraints" not in self.current_config:
            self.current_config["employee_constraints"] = {}
        
        self.current_config["employee_constraints"][employee_name] = constraints
    
    def apply_constraint_template(self, employee_name, template_name):
        """制約テンプレート適用"""
        if template_name not in self.employee_constraint_templates:
            return False, f"テンプレート'{template_name}'が見つかりません"
        
        template = self.employee_constraint_templates[template_name].copy()
        self.update_employee_constraints(employee_name, template)
        return True, None
    
    def _create_default_config(self):
        """デフォルト設定作成"""
        return {
            "config_name": "新規設定",
            "created_date": datetime.now().strftime("%Y-%m-%d"),
            "site_name": "現場",
            "employee_preferences": {},
            "employee_constraints": {},
            "priority_weights": self.priority_weights,
            "description": "Phase 2設定",
            "max_employees": self.max_employees
        }
    
    # Phase 2: 複数現場対応メソッド
    def get_available_sites(self):
        """利用可能な現場一覧取得"""
        # configs/フォルダから現場名を抽出
        config_files = self.get_config_files()
        sites = set()
        
        for filename in config_files:
            try:
                success, config = self.load_config(filename)
                if success and 'site_name' in config:
                    sites.add(config['site_name'])
            except:
                continue
        
        # デフォルト現場を追加
        sites.add("本社現場")
        return sorted(list(sites))
    
    def get_site_configs(self, site_name):
        """特定現場の設定ファイル一覧取得"""
        config_files = self.get_config_files()
        site_configs = []
        
        for filename in config_files:
            try:
                success, config = self.load_config(filename)
                if success and config.get('site_name') == site_name:
                    site_configs.append({
                        'filename': filename,
                        'config_name': config.get('config_name', filename),
                        'created_date': config.get('created_date', 'Unknown'),
                        'description': config.get('description', '')
                    })
            except:
                continue
        
        return site_configs
    
    def create_site_config(self, site_name, config_name, description=""):
        """新しい現場設定作成"""
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"{site_name}_{timestamp}.json"
        
        config = {
            "config_name": config_name,
            "created_date": datetime.now().strftime("%Y-%m-%d"),
            "site_name": site_name,
            "employee_preferences": self.default_employee_preferences.copy(),
            "employee_constraints": {},
            "priority_weights": self.priority_weights,
            "description": description,
            "max_employees": self.max_employees,
            "site_specific_settings": {
                "work_locations": ["駅A", "指令", "警乗"],
                "shift_patterns": ["16h勤務"],
                "special_rules": []
            }
        }
        
        success, error = self.save_config(config, filename)
        if success:
            self.current_config = config
            return True, filename
        else:
            return False, error
    
    def switch_site(self, site_name):
        """現場切り替え"""
        self.current_site = site_name
        # この現場の最新設定をロード
        site_configs = self.get_site_configs(site_name)
        if site_configs:
            # 最新の設定をロード
            latest_config = max(site_configs, key=lambda x: x['created_date'])
            success, config = self.load_config(latest_config['filename'])
            return success, config if success else None
        else:
            # 現場設定がない場合はデフォルト作成
            return self.create_site_config(site_name, f"{site_name}_デフォルト")
    
    def get_current_site(self):
        """現在の現場取得"""
        if self.current_config and 'site_name' in self.current_config:
            return self.current_config['site_name']
        return "本社現場"
    
    def clone_site_config(self, source_site, target_site, new_config_name):
        """現場設定のコピー作成"""
        # ソース現場の設定を取得
        source_configs = self.get_site_configs(source_site)
        if not source_configs:
            return False, f"ソース現場'{source_site}'の設定が見つかりません"
        
        latest_source = max(source_configs, key=lambda x: x['created_date'])
        success, source_config = self.load_config(latest_source['filename'])
        
        if not success:
            return False, f"ソース設定の読み込みに失敗: {source_config}"
        
        # ターゲット現場用に設定をコピー
        target_config = source_config.copy()
        target_config['config_name'] = new_config_name
        target_config['site_name'] = target_site
        target_config['created_date'] = datetime.now().strftime("%Y-%m-%d")
        target_config['description'] = f"{source_site}からコピー"
        
        # 新しいファイル名で保存
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"{target_site}_{timestamp}.json"
        
        return self.save_config(target_config, filename)


class WorkLocationManager:
    """勤務場所管理クラス"""
    
    def __init__(self):
        # デフォルト設定（すぐに使用可能）
        self.default_config = {
            "duty_locations": [
                {"name": "駅A", "type": "一徹勤務", "duration": 16, "color": "#FF6B6B"},
                {"name": "指令", "type": "一徹勤務", "duration": 16, "color": "#FF8E8E"},
                {"name": "警乗", "type": "一徹勤務", "duration": 16, "color": "#FFB6B6"},
            ],
            "holiday_type": {"name": "休暇", "color": "#FFEAA7"}
        }
        
        # 現在の設定
        self.duty_locations = self.default_config["duty_locations"].copy()
        self.holiday_type = self.default_config["holiday_type"].copy()
    
    def get_duty_locations(self):
        """勤務場所一覧取得"""
        return self.duty_locations
    
    def get_duty_names(self):
        """勤務場所名一覧"""
        return [loc["name"] for loc in self.duty_locations]
    
    def add_duty_location(self, name, duty_type, duration, color):
        """勤務場所追加"""
        self.duty_locations.append({
            "name": name,
            "type": duty_type,
            "duration": duration,
            "color": color
        })
    
    def remove_duty_location(self, index):
        """勤務場所削除"""
        if 0 <= index < len(self.duty_locations):
            del self.duty_locations[index]
    
    def update_duty_location(self, index, name, duty_type, duration, color):
        """勤務場所更新"""
        if 0 <= index < len(self.duty_locations):
            self.duty_locations[index] = {
                "name": name,
                "type": duty_type,
                "duration": duration,
                "color": color
            }
    
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
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    
    def load_config(self, filename="work_locations.json"):
        """設定読み込み"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.duty_locations = config.get("duty_locations", self.default_config["duty_locations"])
                self.holiday_type = config.get("holiday_type", self.default_config["holiday_type"])
                return True
        except:
            return False


# =================== 完全版エンジン ===================

class CompleteScheduleEngine:
    """完全版勤務表生成エンジン（月またぎ制約完全対応）"""
    
    def __init__(self, location_manager, config_manager=None):
        self.location_manager = location_manager
        self.config_manager = config_manager
        
        # 非番シフトID（動的に設定）
        self.OFF_SHIFT_ID = None
        
        # Phase 2: 拡張重み設定
        self.weights = {
            'RELIEF': 10,           # 助勤使用ペナルティ
            'HOLIDAY': 50,          # 有休違反ペナルティ  
            'NITETU': 15,           # 二徹ペナルティ
            'N2_GAP': 30,           # 二徹格差ペナルティ
            'PREF': 5,              # 希望違反ペナルティ
            'CROSS_MONTH': 20,      # 月またぎ二徹ペナルティ
            # Phase 2: 高度制約ペナルティ
            'CONSECUTIVE': 100,     # 連続勤務違反
            'PROHIBITED_DAY': 200,  # 勤務禁止日違反
            'SKILL_MISMATCH': 75,   # スキルミスマッチ
            'HOUR_LIMIT': 50,       # 勤務時間限界違反
            'REQUIRED_REST': 150    # 必須休み違反
        }
        
        # Phase 2: 拡張制約緩和メッセージ
        self.relax_messages = {
            0: "✅ 全制約満足",
            1: "⚠️ 二徹バランス緩和（格差許容）",
            2: "⚠️ 助勤フル解禁（ペナルティ低減）", 
            3: "⚠️ 有休の一部を勤務変更（休多→勤務優先）",
            4: "⚠️ 高度制約緩和（連続勤務・スキル制約緩和）",
            5: "🚨 緊急モード（全制約大幅緩和）"
        }
    
    def update_weights(self, new_weights):
        """重みパラメータを更新"""
        self.weights.update(new_weights)
    
    def setup_system(self, employee_names):
        """システム設定（Phase 2: 大人数対応）"""
        self.employees = employee_names
        self.n_employees = len(employee_names)
        
        # Phase 2: 大人数対応 - 助勤は最後の従業員ではなく専用として扱う
        if self.n_employees > 10:
            # 10人を超える場合は専用助勤を設定
            self.relief_employee_id = None  # 専用助勤として処理
        else:
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
        
        # Phase 2: 高度制約情報表示
        if self.config_manager:
            constraints_count = 0
            for emp_name in self.employees:
                emp_constraints = self.config_manager.get_employee_constraints(emp_name)
                if emp_constraints:
                    constraints_count += 1
            print(f"  高度制約適用従業員: {constraints_count}名")
    
    def parse_requirements(self, requirement_lines, n_days):
        """要求文の解析（Phase 2: 高度制約対応）"""
        ng_constraints = defaultdict(list)
        preferences = {}
        holidays = set()
        debug_info = []
        
        # Phase 2: 高度制約情報収集
        individual_constraints = {}
        if self.config_manager:
            for emp_name in self.employees:
                emp_constraints = self.config_manager.get_employee_constraints(emp_name)
                if emp_constraints:
                    individual_constraints[emp_name] = emp_constraints
        
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
        
        # Phase 2: 個人制約解析結果追加
        if individual_constraints:
            debug_info.append(f"🔧 高度制約適用: {len(individual_constraints)}名")
            for emp_name, constraints in individual_constraints.items():
                if constraints.get('prohibited_days'):
                    debug_info.append(f"  {emp_name}: 勤務禁止日 {constraints['prohibited_days']}")
                if constraints.get('max_consecutive_days', 2) != 2:
                    debug_info.append(f"  {emp_name}: 最大連続{constraints['max_consecutive_days']}日")
        
        return ng_constraints, preferences, holidays, debug_info, individual_constraints
    
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
                    debug_info.append(f"⚠️ {employee_name}は前日({shift})勤務 → 当月1日は非番必須")
        
        debug_info.append(f"📊 前月末勤務データ: {len(prev_duties)}件")
        return prev_duties, debug_info
    
    def build_optimization_model(self, n_days, ng_constraints, preferences, holidays, 
                                relax_level=0, prev_duties=None, individual_constraints=None):
        """最適化モデル構築（Phase 2: 高度制約対応）"""
        model = cp_model.CpModel()
        
        # Phase 2: 個人制約のデフォルト値
        if individual_constraints is None:
            individual_constraints = {}
        
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
        
        # Phase 2: 高度個人制約適用
        advanced_constraint_violations = []
        
        for emp_name, constraints in individual_constraints.items():
            if emp_name not in self.name_to_id:
                continue
            
            emp_id = self.name_to_id[emp_name]
            
            # 1. 連続勤務日数制約
            max_consecutive = constraints.get('max_consecutive_days', 2)
            if max_consecutive < 2:  # 1日連続のみ許可（新人等）
                for d in range(n_days - 1):
                    # 連続して勤務してはいけない
                    duty_today = sum(w[emp_id, d, s] for s in range(self.n_duties))
                    duty_tomorrow = sum(w[emp_id, d + 1, s] for s in range(self.n_duties))
                    if relax_level < 4:
                        model.Add(duty_today + duty_tomorrow <= 1)
                    else:
                        # 緩和モード: ペナルティとして処理
                        violation_var = model.NewBoolVar(f"consecutive_violation_{emp_id}_{d}")
                        model.Add(duty_today + duty_tomorrow >= 2).OnlyEnforceIf(violation_var)
                        model.Add(duty_today + duty_tomorrow <= 1).OnlyEnforceIf(violation_var.Not())
                        advanced_constraint_violations.append(violation_var)
            
            # 2. 勤務禁止日制約
            prohibited_days = constraints.get('prohibited_days', [])
            for day in prohibited_days:
                if 1 <= day <= n_days:  # 1-indexedから0-indexedに変換
                    day_idx = day - 1
                    if relax_level < 4:
                        # 全勤務を禁止
                        for s in range(self.n_duties):
                            model.Add(w[emp_id, day_idx, s] == 0)
                    else:
                        # 緩和モード: ペナルティとして処理
                        violation_var = model.NewBoolVar(f"prohibited_day_violation_{emp_id}_{day}")
                        duty_on_prohibited = sum(w[emp_id, day_idx, s] for s in range(self.n_duties))
                        model.Add(duty_on_prohibited >= 1).OnlyEnforceIf(violation_var)
                        model.Add(duty_on_prohibited == 0).OnlyEnforceIf(violation_var.Not())
                        advanced_constraint_violations.append(violation_var)
            
            # 3. 特定勤務後の必須休み制約
            required_rest_after = constraints.get('required_rest_after')
            if required_rest_after and required_rest_after in self.duty_names:
                rest_duty_id = self.duty_names.index(required_rest_after)
                for d in range(n_days - 1):
                    if relax_level < 4:
                        # 特定勤務の翌日は絶対休み
                        model.AddImplication(w[emp_id, d, rest_duty_id], w[emp_id, d + 1, self.OFF_SHIFT_ID])
                    else:
                        # 緩和モード: ペナルティとして処理
                        violation_var = model.NewBoolVar(f"rest_violation_{emp_id}_{d}")
                        next_day_duty = sum(w[emp_id, d + 1, s] for s in range(self.n_duties))
                        # 特定勤務かつ翌日勤務の場合違反
                        model.Add(w[emp_id, d, rest_duty_id] + next_day_duty >= 2).OnlyEnforceIf(violation_var)
                        model.Add(w[emp_id, d, rest_duty_id] + next_day_duty <= 1).OnlyEnforceIf(violation_var.Not())
                        advanced_constraint_violations.append(violation_var)
        
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
        
        # 助勤制約（Phase 2: 大人数対応）
        relief_work_vars = []
        if self.relief_employee_id is not None:
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
        
        # 希望制約（Phase 1: 優先度統合）
        preference_terms = []
        priority_penalty_terms = []
        
        # 従来の希望制約
        if relax_level == 0:
            for (emp_id, day, shift), weight in preferences.items():
                if 0 <= day < n_days and 0 <= shift < self.n_shifts:
                    preference_terms.append(weight * w[emp_id, day, shift])
        
        # Phase 1: 従業員優先度による重み付け
        if self.config_manager:
            for emp_id in range(self.n_employees):
                emp_name = self.id_to_name[emp_id]
                for day in range(n_days):
                    for duty_id in range(self.n_duties):
                        duty_name = self.duty_names[duty_id]
                        penalty = self.config_manager.get_priority_penalty(emp_name, duty_name)
                        if penalty > 0:  # ペナルティがある場合のみ追加
                            priority_penalty_terms.append(penalty * w[emp_id, day, duty_id])
        
        # Phase 2: スキルミスマッチペナルティ計算
        skill_mismatch_terms = []
        if relax_level < 5:
            for emp_name, constraints in individual_constraints.items():
                if emp_name not in self.name_to_id:
                    continue
                emp_id = self.name_to_id[emp_name]
                skill_levels = constraints.get('skill_level', {})
                
                for duty_name, skill_level in skill_levels.items():
                    if duty_name in self.duty_names and skill_level == "初級":
                        duty_id = self.duty_names.index(duty_name)
                        for d in range(n_days):
                            skill_mismatch_terms.append(
                                self.weights['SKILL_MISMATCH'] * w[emp_id, d, duty_id]
                            )
        
        # 目的関数（Phase 2: 高度制約ペナルティ追加）
        objective_terms = [
            relief_weight * sum(relief_work_vars),
            holiday_weight * sum(holiday_violations),
            self.weights['NITETU'] * sum(nitetu_vars),
            self.weights['CROSS_MONTH'] * sum(cross_month_nitetu_vars),
            # Phase 2: 高度制約ペナルティ
            self.weights['CONSECUTIVE'] * sum(advanced_constraint_violations),
            sum(skill_mismatch_terms)
        ]
        
        # Phase 1: 優先度ペナルティ項目を追加
        if priority_penalty_terms:
            objective_terms.append(sum(priority_penalty_terms))
        
        if nitetu_gap != 0:
            objective_terms.append(self.weights['N2_GAP'] * nitetu_gap)
        
        objective_terms.extend(preference_terms)
        model.Minimize(sum(objective_terms))
        
        return model, w, nitetu_counts, cross_month_constraints, advanced_constraint_violations
    
    def solve_with_relaxation(self, n_days, ng_constraints, preferences, holidays, prev_duties=None, individual_constraints=None):
        """段階的制約緩和による求解（Phase 2: 高度制約対応）"""
        relax_notes = []
        cross_constraints = []
        advanced_violations = []
        
        # Phase 2: 高度制約ありの場合は緩和レベルを拡張
        max_relax_level = 6 if individual_constraints else 4
        
        for relax_level in range(max_relax_level):
            # レベル3では有休を削減
            holidays_to_use = holidays
            if relax_level == 3:
                holidays_to_use, reduction_note = self.reduce_holidays(holidays)
                if reduction_note:
                    relax_notes.append(reduction_note)
            
            # モデル構築（Phase 2: 個人制約付き）
            model, w, nitetu_counts, cross_const, adv_violations = self.build_optimization_model(
                n_days, ng_constraints, preferences, holidays_to_use, relax_level, prev_duties, individual_constraints
            )
            cross_constraints = cross_const
            advanced_violations = adv_violations
            
            # 求解
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 30
            status = solver.Solve(model)
            
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                return relax_level, status, solver, w, nitetu_counts, relax_notes, cross_constraints, advanced_violations
            
            relax_notes.append(self.relax_messages[relax_level])
        
        # すべてのレベルで解けない場合
        return 99, cp_model.INFEASIBLE, None, None, None, relax_notes, cross_constraints, advanced_violations
    
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
        """スケジュール求解（新GUI対応版）"""
        n_days = calendar.monthrange(year, month)[1]
        self.setup_system(employee_names)
        
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
        
        # データ解析
        ng_constraints, preferences, holidays, debug_info = self.parse_requirements(requirement_lines, n_days)
        
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
    """完全版GUI（月またぎ制約対応）"""
    
    def __init__(self):
        self.location_manager = WorkLocationManager()
        self.config_manager = ConfigurationManager()
        self.engine = CompleteScheduleEngine(self.location_manager, self.config_manager)
        self.excel_exporter = ExcelExporter(self.engine)
        
        # セッション状態初期化
        if 'calendar_data' not in st.session_state:
            st.session_state.calendar_data = {}
        if 'show_config' not in st.session_state:
            st.session_state.show_config = False
        
        # 設定読み込み
        self.location_manager.load_config()
        
        # Phase 1: デフォルト設定読み込み
        default_files = self.config_manager.get_config_files()
        if "default.json" in default_files:
            self.config_manager.load_config("default.json")
    
    def run(self):
        """メイン実行（Phase 2: アコーディオンUI）"""
        self._setup_page()
        
        # Phase 2: 高度ナビゲーション
        if st.session_state.ui_mode == 'advanced':
            self._advanced_accordion_ui()
        elif st.session_state.show_config:
            self._configuration_page()
        else:
            self._main_page()
    
    def _setup_page(self):
        """ページ設定（シンプル版）"""
        st.set_page_config(
            page_title="勤務表システム（修正版）",
            page_icon="📅",
            layout="wide"
        )
        
        # Initialize session state variables if not exists
        if 'ui_mode' not in st.session_state:
            st.session_state.ui_mode = 'basic'
        if 'show_config' not in st.session_state:
            st.session_state.show_config = False
        if 'current_site' not in st.session_state:
            available_sites = self.config_manager.get_available_sites()
            st.session_state.current_site = available_sites[0] if available_sites else 'default'
        if 'expanded_sections' not in st.session_state:
            st.session_state.expanded_sections = {
                'employees': False,
                'sites': False, 
                'constraints': False,
                'schedule': True,
                'analysis': False
            }
        
        # Phase 2: ヘッダー拡張
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.title("🎆 勤務表システム Phase 2")
            
        with col2:
            # UIモード切り替え
            ui_mode = st.selectbox(
                "🎨 UIモード",
                options=['basic', 'advanced'],
                format_func=lambda x: '🔰 シンプル' if x == 'basic' else '🎆 高度',
                index=0 if st.session_state.ui_mode == 'basic' else 1
            )
            if ui_mode != st.session_state.ui_mode:
                st.session_state.ui_mode = ui_mode
                st.rerun()
        
        with col3:
            # 現場切り替え
            available_sites = self.config_manager.get_available_sites()
            current_site = st.selectbox(
                "🏢 現場選択",
                options=available_sites,
                index=available_sites.index(st.session_state.current_site) if st.session_state.current_site in available_sites else 0
            )
            if current_site != st.session_state.current_site:
                st.session_state.current_site = current_site
                self.config_manager.switch_site(current_site)
                st.rerun()
        
        # Phase 2: 機能ステータス表示
        if st.session_state.ui_mode == 'advanced':
            st.info("🎆 **Phase 2 高度モード**: 大人数対応・高度制約・複数現場対応")
        else:
            st.success("🔰 **シンプルモード**: Phase 1互換機能")
        
        # リセットボタンとコントロール
        col1, col2, col3 = st.columns([1, 7, 2])
        with col1:
            if st.button("🔄 リセット"):
                for key in list(st.session_state.keys()):
                    if key not in ['show_config', 'ui_mode', 'current_site']:
                        del st.session_state[key]
                st.rerun()
        
        with col3:
            # Phase 2: クイックアクション
            if st.session_state.ui_mode == 'advanced':
                if st.button("⚙️ 設定"):
                    st.session_state.show_config = True
                    st.rerun()
            else:
                if st.button("⚙️ 詳細設定"):
                    st.session_state.show_config = True
                    st.rerun()
        
        st.markdown("---")
    
    def _advanced_accordion_ui(self):
        """高度アコーディオン式UI（Phase 2）"""
        st.markdown("### 🎆 Phase 2 高度モード")
        
        # メインアコーディオンセクション
        with st.expander("👥 従業員管理 & 大人数対応", expanded=st.session_state.expanded_sections.get('employees', False)):
            self._employee_management_section()
        
        with st.expander("🏢 現場管理 & 設定", expanded=st.session_state.expanded_sections.get('sites', False)):
            self._site_management_section()
        
        with st.expander("⚙️ 高度個人制約設定", expanded=st.session_state.expanded_sections.get('constraints', False)):
            self._advanced_constraints_section()
        
        with st.expander("📅 スケジュール生成", expanded=st.session_state.expanded_sections.get('schedule', True)):
            self._schedule_generation_section()
        
        with st.expander("📈 分析 & レポート", expanded=st.session_state.expanded_sections.get('analysis', False)):
            self._analysis_section()
    
    def _employee_management_section(self):
        """従業員管理セクション（Phase 2）"""
        st.markdown("#### 👥 従業員管理（最大50人対応）")
        
        current_prefs = self.config_manager.get_employee_preferences()
        employee_list = list(current_prefs.keys())
        
        # 現在の従業員数表示
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("登録従業員数", len(employee_list))
        with col2:
            st.metric("最大対応数", self.config_manager.max_employees)
        with col3:
            remaining = self.config_manager.max_employees - len(employee_list)
            st.metric("追加可能数", remaining)
        
        # 従業員追加
        st.markdown("**新しい従業員を追加**")
        col1, col2 = st.columns(2)
        
        with col1:
            new_emp_name = st.text_input("従業員名", key="new_employee_name")
        
        with col2:
            constraint_template = st.selectbox(
                "制約テンプレート",
                options=list(self.config_manager.employee_constraint_templates.keys()),
                key="new_emp_constraint_template"
            )
        
        if st.button("➕ 従業員追加") and new_emp_name.strip():
            success, error = self.config_manager.add_employee(
                new_emp_name.strip(),
                constraints=self.config_manager.employee_constraint_templates[constraint_template].copy()
            )
            if success:
                st.success(f"✅ {new_emp_name}を追加しました")
                st.rerun()
            else:
                st.error(f"❌ エラー: {error}")
        
        # 従業員一覧と管理
        if employee_list:
            st.markdown("**現在の従業員一覧**")
            
            for emp_name in employee_list:
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.write(f"👤 **{emp_name}**")
                        # 制約情報表示
                        constraints = self.config_manager.get_employee_constraints(emp_name)
                        if constraints:
                            st.caption(f"連続勤務上限: {constraints.get('max_consecutive_days', 2)}日")
                    
                    with col2:
                        if st.button("✏️ 編集", key=f"edit_{emp_name}"):
                            st.session_state[f"editing_{emp_name}"] = True
                    
                    with col3:
                        if st.button("🗑️ 削除", key=f"delete_{emp_name}"):
                            success, error = self.config_manager.remove_employee(emp_name)
                            if success:
                                st.success(f"✅ {emp_name}を削除しました")
                                st.rerun()
                            else:
                                st.error(f"❌ エラー: {error}")
                    
                    # 編集モード
                    if st.session_state.get(f"editing_{emp_name}", False):
                        self._edit_employee_section(emp_name)
                    
                    st.markdown("---")
    
    def _edit_employee_section(self, emp_name):
        """従業員編集セクション"""
        st.markdown(f"#### ✏️ {emp_name} の設定編集")
        
        # 優先度設定
        st.markdown("**優先度設定**")
        current_prefs = self.config_manager.get_employee_preferences()
        emp_prefs = current_prefs.get(emp_name, {})
        
        duty_names = self.location_manager.get_duty_names()
        new_prefs = {}
        
        cols = st.columns(len(duty_names))
        for i, duty_name in enumerate(duty_names):
            with cols[i]:
                current_value = emp_prefs.get(duty_name, 2)
                priority = st.selectbox(
                    f"{duty_name}",
                    options=[0, 1, 2, 3],
                    index=[0, 1, 2, 3].index(current_value),
                    format_func=lambda x: f"{x} - {['❌不可', '🟠可能', '🟡普通', '🌟最優先'][x]}",
                    key=f"edit_pref_{emp_name}_{duty_name}"
                )
                new_prefs[duty_name] = priority
        
        # 高度制約設定
        st.markdown("**高度制約設定**")
        constraints = self.config_manager.get_employee_constraints(emp_name)
        
        col1, col2 = st.columns(2)
        with col1:
            max_consecutive = st.number_input(
                "最大連続勤務日数",
                min_value=1, max_value=5,
                value=constraints.get('max_consecutive_days', 2),
                key=f"edit_consecutive_{emp_name}"
            )
        
        with col2:
            prohibited_days_input = st.text_input(
                "勤務禁止日 (カンマ区切り)",
                value=",".join(map(str, constraints.get('prohibited_days', []))),
                key=f"edit_prohibited_{emp_name}"
            )
        
        # スキルレベル設定
        st.markdown("**スキルレベル設定**")
        skill_levels = constraints.get('skill_level', {})
        new_skills = {}
        
        cols = st.columns(len(duty_names))
        for i, duty_name in enumerate(duty_names):
            with cols[i]:
                current_skill = skill_levels.get(duty_name, "中級")
                skill = st.selectbox(
                    f"{duty_name} スキル",
                    options=["初級", "中級", "上級"],
                    index=["初級", "中級", "上級"].index(current_skill),
                    key=f"edit_skill_{emp_name}_{duty_name}"
                )
                new_skills[duty_name] = skill
        
        # 保存・キャンセル
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 保存", key=f"save_{emp_name}"):
                # 優先度更新
                current_prefs[emp_name] = new_prefs
                self.config_manager.update_employee_preferences(current_prefs)
                
                # 制約更新
                prohibited_days = []
                if prohibited_days_input.strip():
                    try:
                        prohibited_days = [int(x.strip()) for x in prohibited_days_input.split(',') if x.strip()]
                    except:
                        st.error("禁止日の形式が正しくありません")
                        return
                
                new_constraints = {
                    'max_consecutive_days': max_consecutive,
                    'prohibited_days': prohibited_days,
                    'required_rest_after': constraints.get('required_rest_after'),
                    'skill_level': new_skills,
                    'weekly_hour_limit': constraints.get('weekly_hour_limit', 48),
                    'monthly_holiday_min': constraints.get('monthly_holiday_min', 8)
                }
                
                self.config_manager.update_employee_constraints(emp_name, new_constraints)
                st.success(f"✅ {emp_name}の設定を更新しました")
                del st.session_state[f"editing_{emp_name}"]
                st.rerun()
        
        with col2:
            if st.button("❌ キャンセル", key=f"cancel_{emp_name}"):
                del st.session_state[f"editing_{emp_name}"]
                st.rerun()
    
    def _site_management_section(self):
        """現場管理セクション（Phase 2）"""
        st.markdown("#### 🏢 現場管理")
        
        # 現在の現場情報
        current_site = self.config_manager.get_current_site()
        st.info(f"🏢 現在の現場: **{current_site}**")
        
        # 新しい現場作成
        st.markdown("**新しい現場作成**")
        col1, col2 = st.columns(2)
        
        with col1:
            new_site_name = st.text_input("現場名", key="new_site_name")
        
        with col2:
            new_site_desc = st.text_input("説明", key="new_site_desc")
        
        if st.button("➕ 現場作成") and new_site_name.strip():
            success, filename = self.config_manager.create_site_config(
                new_site_name.strip(),
                f"{new_site_name.strip()}_初期設定",
                new_site_desc
            )
            if success:
                st.success(f"✅ 現場 '{new_site_name}' を作成しました")
                st.session_state.current_site = new_site_name.strip()
                st.rerun()
            else:
                st.error(f"❌ エラー: {filename}")
        
        # 現場コピー
        st.markdown("**現場設定コピー**")
        available_sites = self.config_manager.get_available_sites()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            source_site = st.selectbox("コピー元現場", available_sites, key="copy_source_site")
        
        with col2:
            target_site = st.text_input("コピー先現場名", key="copy_target_site")
        
        with col3:
            if st.button("📋 コピー") and target_site.strip():
                success, error = self.config_manager.clone_site_config(
                    source_site, target_site.strip(), f"{target_site.strip()}_コピー"
                )
                if success:
                    st.success(f"✅ 現場設定をコピーしました")
                    st.rerun()
                else:
                    st.error(f"❌ エラー: {error}")
    
    def _advanced_constraints_section(self):
        """高度制約設定セクション（Phase 2）"""
        st.markdown("#### ⚙️ 高度制約設定")
        
        # 制約テンプレート管理
        st.markdown("**制約テンプレート**")
        
        templates = self.config_manager.employee_constraint_templates
        selected_template = st.selectbox(
            "テンプレート選択",
            options=list(templates.keys()),
            key="constraint_template_select"
        )
        
        if selected_template:
            template_data = templates[selected_template]
            st.json(template_data)
        
        # 一括適用
        st.markdown("**一括テンプレート適用**")
        current_employees = list(self.config_manager.get_employee_preferences().keys())
        
        selected_employees = st.multiselect(
            "適用対象従業員",
            options=current_employees,
            key="bulk_apply_employees"
        )
        
        if st.button("⚙️ 一括適用") and selected_employees:
            for emp_name in selected_employees:
                success, error = self.config_manager.apply_constraint_template(emp_name, selected_template)
                if not success:
                    st.error(f"❌ {emp_name}: {error}")
            
            st.success(f"✅ {len(selected_employees)}名にテンプレートを適用しました")
            st.rerun()
    
    def _schedule_generation_section(self):
        """スケジュール生成セクション（Phase 2）"""
        st.markdown("#### 📅 スケジュール生成")
        
        # ここでパラメータ設定UIを呼び出す
        self._create_schedule_parameters_input()

        st.markdown("---")
        
        # 既存のメインページ機能を組み込み
        col1, col2 = st.columns(2)
        
        with col1:
            self._create_calendar_input()
        
        with col2:
            self._create_control_panel()
    
    def _analysis_section(self):
        """分析レポートセクション（Phase 2）"""
        st.markdown("#### 📈 分析 & レポート")
        
        # 現在の設定統計
        current_prefs = self.config_manager.get_employee_preferences()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("登録従業員数", len(current_prefs))
        
        with col2:
            constraints_count = 0
            for emp_name in current_prefs.keys():
                if self.config_manager.get_employee_constraints(emp_name):
                    constraints_count += 1
            st.metric("高度制約適用者", constraints_count)
        
        with col3:
            current_site = self.config_manager.get_current_site()
            site_configs = self.config_manager.get_site_configs(current_site)
            st.metric(f"{current_site} 設定数", len(site_configs))
        
        # 設定データエクスポート
        if st.button("📥 現在の設定をエクスポート"):
            if self.config_manager.current_config:
                config_json = json.dumps(self.config_manager.current_config, ensure_ascii=False, indent=2)
                st.download_button(
                    "📥 JSONファイルダウンロード",
                    data=config_json.encode('utf-8'),
                    file_name=f"{current_site}_設定_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json"
                )
            else:
                st.error("エクスポートする設定がありません")
    
    def _configuration_page(self):
        """設定ページ（Phase 1: 優先度設定対応）"""
        st.header("⚙️ 詳細設定")
        
        # 戻るボタン
        if st.button("← メインページに戻る"):
            st.session_state.show_config = False
            if 'new_config_mode' in st.session_state:
                del st.session_state.new_config_mode
            st.rerun()
        
        # Phase 1: タブ切り替え
        tab1, tab2 = st.tabs(["🏢 勤務場所設定", "👥 優先度設定 (Phase 1)"])
        
        with tab1:
            self._create_location_settings_tab()
        
        with tab2:
            self._create_preference_settings_tab()
    
    def _create_location_settings_tab(self):
        """勤務場所設定タブ"""
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
                    self.location_manager.remove_duty_location(i)
                    self.location_manager.save_config()  # 即座に保存
                    st.success(f"勤務場所 {i+1} を削除しました")
                    st.rerun()
            
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
        
        # 新規追加（最大15まで）
        if len(duty_locations) < 15:
            st.subheader("新規勤務場所追加")
            col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])
            
            with col1:
                add_name = st.text_input("新しい勤務場所名", key="add_name")
            with col2:
                add_type = st.selectbox("勤務タイプ", ["一徹勤務", "日勤", "夜勤", "その他"], key="add_type")
            with col3:
                add_duration = st.number_input("時間", min_value=1, max_value=24, value=16, key="add_duration")
            with col4:
                add_color = st.color_picker("色", value="#45B7D1", key="add_color")
            with col5:
                if st.button("➕ 追加"):
                    if add_name.strip():
                        self.location_manager.add_duty_location(add_name.strip(), add_type, add_duration, add_color)
                        self.location_manager.save_config()  # 即座に保存
                        st.success(f"「{add_name}」を追加しました")
                        st.rerun()
                    else:
                        st.error("勤務場所名を入力してください")
        else:
            st.warning("⚠️ 最大15勤務場所まで追加できます")
        
        # 保存ボタン
        if st.button("💾 勤務場所設定を保存", type="primary"):
            self.location_manager.save_config()
            st.success("✅ 勤務場所設定を保存しました")
    
    def _create_preference_settings_tab(self):
        """優先度設定タブ（Phase 1）"""
        st.subheader("👥 従業員優先度設定 (Phase 1)")
        st.info("🎡 3人分（Aさん、Bさん、Cさん）の優先度設定")
        
        # 現在の設定表示
        current_prefs = self.config_manager.get_employee_preferences()
        duty_names = self.location_manager.get_duty_names()
        
        st.write("📋 **優先度レベル**:")
        st.write("- 3: 🌟 最優先 (ペナルティ 0)")
        st.write("- 2: 🟡 普通 (ペナルティ 5)")
        st.write("- 1: 🟠 可能 (ペナルティ 10)")
        st.write("- 0: ❌ 不可 (ペナルティ 1000)")
        
        st.markdown("---")
        
        # 3人の優先度設定エリア
        employees = ["Aさん", "Bさん", "Cさん"]
        new_preferences = {}
        
        for emp in employees:
            st.write(f"**{emp} の優先度設定**")
            
            emp_prefs = {}
            cols = st.columns(len(duty_names))
            
            for i, duty_name in enumerate(duty_names):
                current_value = current_prefs.get(emp, {}).get(duty_name, 2)
                
                with cols[i]:
                    priority = st.selectbox(
                        f"{duty_name}",
                        options=[0, 1, 2, 3],
                        index=[0, 1, 2, 3].index(current_value),
                        format_func=lambda x: f"{x} - {['❌不可', '🟠可能', '🟡普通', '🌟最優先'][x]}",
                        key=f"pref_{emp}_{duty_name}"
                    )
                    emp_prefs[duty_name] = priority
            
            new_preferences[emp] = emp_prefs
            st.markdown("---")
        
        # 現在の設定との変更チェック
        if new_preferences != current_prefs:
            st.warning("⚠️ 設定が変更されています。保存してください。")
            self.config_manager.update_employee_preferences(new_preferences)
        
        # 保存機能
        col1, col2 = st.columns(2)
        
        with col1:
            # 既存ファイル更新
            if st.button("💾 現在の設定を更新", type="primary"):
                if self.config_manager.current_config:
                    filename = st.session_state.get('last_config_file', 'default.json')
                    success, error = self.config_manager.save_config(self.config_manager.current_config, filename)
                    if success:
                        st.success(f"✅ {filename} を更新しました")
                    else:
                        st.error(f"❌ 保存エラー: {error}")
                else:
                    st.error("保存する設定がありません")
        
        with col2:
            # 新規保存
            new_filename = st.text_input(
                "新規ファイル名",
                value=f"としかず現場_{datetime.now().strftime('%Y%m%d')}.json",
                key="new_config_filename"
            )
            
            if st.button("🆕 新規保存"):
                if new_filename.strip():
                    if not new_filename.endswith('.json'):
                        new_filename += '.json'
                    
                    # 新規設定作成
                    if not self.config_manager.current_config:
                        self.config_manager.update_employee_preferences(new_preferences)
                    
                    # メタデータ更新
                    self.config_manager.current_config.update({
                        "config_name": new_filename.replace('.json', ''),
                        "created_date": datetime.now().strftime("%Y-%m-%d"),
                        "site_name": "としかず現場",
                        "description": "Phase 1: 3人分優先度設定"
                    })
                    
                    success, error = self.config_manager.save_config(self.config_manager.current_config, new_filename)
                    if success:
                        st.success(f"✅ {new_filename} で保存しました")
                        st.session_state.last_config_file = new_filename
                    else:
                        st.error(f"❌ 保存エラー: {error}")
                else:
                    st.error("ファイル名を入力してください")
        
        # 設定プレビュー
        with st.expander("🔍 現在の設定プレビュー"):
            st.json(new_preferences)
        
        # ダウンロード機能
        if self.config_manager.current_config:
            config_json = json.dumps(self.config_manager.current_config, ensure_ascii=False, indent=2)
            st.download_button(
                "📎 JSONファイルをダウンロード",
                data=config_json.encode('utf-8'),
                file_name=f"優先度設定_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json"
            )
    
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
    
    def _create_schedule_parameters_input(self):
        """スケジュールパラメータ入力UIを作成し、インスタンス属性を設定する"""
        st.header("📋 基本設定")

        # 年月設定（最優先）
        self.year = st.number_input("年", value=datetime.now().year, min_value=2020, max_value=2030)
        self.month = st.selectbox("月", range(1, 13), index=datetime.now().month - 1)
        self.n_days = calendar.monthrange(self.year, self.month)[1]

        # 前月情報表示
        prev_year, prev_month = self._get_prev_month_info()
        st.info(f"対象: {self.year}年{self.month}月 ({self.n_days}日間)")
        st.info(f"前月: {prev_year}年{prev_month}月")

        st.markdown("---")

        # 従業員設定（この部分はAdvanced UIでは別管理のため、ここではシンプルなリスト取得に留める）
        # basicモードとの互換性のため、ここではconfig_managerから取得する形に統一
        self.employees = list(self.config_manager.get_employee_preferences().keys())
        if not self.employees:
            # デフォルトとしてA,B,Cさんを設定
            self.employees = ["Aさん", "Bさん", "Cさん"]
            st.warning("従業員が設定されていません。デフォルトの従業員（A,B,Cさん）を使用します。")
        
        st.info(f"対象従業員数: {len(self.employees)} 名")

        # 前月末勤務設定
        st.header("🔄 前月末勤務情報")
        st.warning("⚠️ 前日勤務者は翌月1日目が自動的に非番になります")
        self.prev_schedule_data = self._create_prev_schedule_input(prev_month)
    
    def _create_sidebar(self):
        """サイドバー（Phase 1: 設定選択対応）"""
        # Phase 1: 設定ファイル選択
        st.header("📁 設定選択")
        
        config_files = self.config_manager.get_config_files()
        if config_files:
            selected_config = st.selectbox(
                "設定ファイル",
                config_files,
                index=config_files.index("default.json") if "default.json" in config_files else 0,
                key="config_file_select"
            )
            
            # 設定変更時の読み込み
            if st.session_state.get('last_config_file') != selected_config:
                success, result = self.config_manager.load_config(selected_config)
                if success:
                    st.success(f"✅ {selected_config} を読み込みました")
                    st.session_state.last_config_file = selected_config
                else:
                    st.error(f"❌ 読み込みエラー: {result}")
            
            # 現在の設定情報表示
            if self.config_manager.current_config:
                config = self.config_manager.current_config
                st.info(f"🏢 {config.get('site_name', '現場名不明')}")
                st.info(f"📅 {config.get('created_date', '日付不明')}")
                
                # 優先度設定数表示
                prefs = config.get('employee_preferences', {})
                if prefs:
                    st.write(f"👥 設定済み従業員: {len(prefs)}名")
        else:
            st.warning("⚠️ 設定ファイルがありません")
        
        st.markdown("---")
        
        # 新しいメソッドを呼び出す
        self._create_schedule_parameters_input()

        st.markdown("---")
        
        # 勤務場所表示と詳細設定ボタンは残す
        duty_names = self.location_manager.get_duty_names()
        st.write("**現在の勤務場所:**")
        for name in duty_names:
            st.write(f"• {name}")
        
        if st.button("⚙️ 詳細設定", use_container_width=True):
            st.session_state.show_config = True
            st.rerun()
    
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
            with st.container(border=True):
                st.subheader(f"📅 {emp}の前月末勤務")
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
        
        # 従業員リストを取得
        current_employees = list(self.config_manager.get_employee_preferences().keys())
        
        if not current_employees:
            st.warning("先に従業員を設定してください")
            return
        
        # 年月から日数を計算（先にUI要素で年月を設定）
        year = st.number_input("年", value=2025, min_value=2020, max_value=2030, key="calendar_year")
        month = st.selectbox("月", range(1, 13), index=5, key="calendar_month")
        n_days = calendar.monthrange(year, month)[1]
        
        st.info(f"対象: {year}年{month}月 ({n_days}日間)")
        
        # 従業員選択（安全な処理）
        if not current_employees:
            st.warning("先に従業員を設定してください")
            return
        
        # 現在の従業員リストに存在しない選択をクリア
        if 'main_emp_select' in st.session_state:
            if st.session_state.main_emp_select not in current_employees:
                del st.session_state['main_emp_select']
        
        selected_emp = st.selectbox("従業員を選択", current_employees, key="main_emp_select")
        
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
                for row in range((n_days + 3) // 4):
                    cols = st.columns(4)
                    for col_idx, col in enumerate(cols):
                        day = row * 4 + col_idx + 1
                        if day <= n_days:
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
                    min_value=date(year, month, 1),
                    max_value=date(year, month, n_days),
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
        with st.container(border=True):
            st.markdown("##### 📊 設定確認")
            total_holidays = 0
            total_duties = 0
            cross_constraints_preview = []
            
            # 従業員リストを取得
            current_employees = list(self.config_manager.get_employee_preferences().keys())
            
            # 希望統計
            for emp in current_employees:
                if emp in st.session_state.calendar_data:
                    emp_data = st.session_state.calendar_data[emp]
                    h_count = len(emp_data['holidays'])
                    d_count = len(emp_data['duty_preferences'])
                    total_holidays += h_count
                    total_duties += d_count
                    
                    if h_count > 0 or d_count > 0:
                        st.write(f"**{emp}**: 休暇{h_count}件, 勤務希望{d_count}件")
            
            # 月またぎ制約予測
            for emp in current_employees:
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
        
        # pandasを使わずに表を作成
        st.write("**勤務表:**")
        for i, row in enumerate(table_data):
            if i == 0:
                st.write(" | ".join([f"**{h}**" for h in headers]))
                st.write(" | ".join(["---"] * len(headers)))
            formatted_row = []
            for j, cell in enumerate(row):
                if j == 0:  # 従業員名
                    formatted_row.append(f"**{cell}**")
                else:
                    formatted_row.append(cell)
            st.write(" | ".join(formatted_row))
        
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
                filename = f"勤務表_{self.year}年{self.month:02d}月_修正版.xlsx"
                
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
        st.markdown("💡 **修正版**: シンプル・安定動作を重視した版")
        st.markdown("🎯 **重要**: Aさんが31日B勤務 → 1日目は自動的に非番になります")
        
        # システム情報
        with st.expander("ℹ️ システム情報"):
            st.write("**機能一覧**:")
            st.write("- ✅ **月またぎ制約（完全版）**: 前日勤務→翌月1日非番")
            st.write("- ✅ **複数勤務場所対応**: 駅A、指令、警乗等の独立管理")
            st.write("- ✅ **非番自動処理**: 勤務翌日は自動的に非番")
            st.write("- ✅ **複数日選択**: チェックボックスで飛び飛び選択")
            st.write("- ✅ **二徹・三徹防止**: 段階的制約緩和")
            st.write("- ✅ **Excel色分け出力**: 完全な色分け分析")
            st.write("- ✅ **リアルタイム制約チェック**: 前月末勤務の即座検証")
            
            st.write("**色分け説明**:")
            st.write("- 🟡 **黄色**: 有休実現")
            st.write("- 🔴 **ピンク**: 有休希望なのに勤務（違反）")
            st.write("- 🔵 **青色**: 助勤勤務")
            st.write("- 🟠 **オレンジ**: シフト希望未実現")
            st.write("- 🟣 **紫色**: 月またぎ制約による配置")
    
    except Exception as e:
        st.error(f"❌ システムエラー: {str(e)}")
        import traceback
        st.code(traceback.format_exc())


if __name__ == "__main__":
    main()
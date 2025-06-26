#!/usr/bin/env python3
"""
統合設定管理システム - UnifiedConfigManager
すべての設定を統合して管理し、ワンクリック完全読み込み・保存を実現
"""

import os
import json
import streamlit as st
from datetime import datetime, date

# Import classes from the same directory
try:
    from schedule_gui_fixed import ConfigurationManager, WorkLocationManager
except ImportError:
    # Fallback for when imported as module
    import sys
    sys.path.append(os.path.dirname(__file__))
    from schedule_gui_fixed import ConfigurationManager, WorkLocationManager


class UnifiedConfigManager:
    """完全統合設定管理システム"""
    
    def __init__(self):
        self.configs_dir = "configs"  # 🆕 統合後は configs ディレクトリを使用
        self.ensure_configs_dir()
        
        # 既存管理クラスとの統合
        self.config_manager = ConfigurationManager()
        self.location_manager = WorkLocationManager(self.config_manager)
        
        # デフォルト年休残数
        self.default_annual_leave = 20
    
    def ensure_configs_dir(self):
        """設定ディレクトリの確保"""
        if not os.path.exists(self.configs_dir):
            os.makedirs(self.configs_dir)
    
    def get_unified_config_files(self):
        """統合設定ファイル一覧取得"""
        if not os.path.exists(self.configs_dir):
            return []
        files = [f for f in os.listdir(self.configs_dir) if f.endswith('.json')]
        return sorted(files, reverse=True)  # 新しい順
    
    def save_complete_config(self, config_name, session_state, gui_state):
        """全設定を統合保存"""
        try:
            unified_config = {
                "config_name": config_name,
                "created_date": datetime.now().strftime("%Y-%m-%d"),
                "last_modified": datetime.now().isoformat(),
                
                # 従業員設定
                "employees": gui_state.get('last_employees', []),
                
                # 勤務場所設定  
                "work_locations": self.location_manager.get_duty_locations(),
                
                # 優先度設定
                "employee_priorities": self.config_manager.get_employee_priorities(),
                
                # 警乗設定
                "keijo_settings": {
                    "base_date": gui_state.get('keijo_base_date', date(2025, 6, 1)).isoformat(),
                    "enabled": True
                },
                
                # カレンダーデータ（年休申請・勤務希望）
                "current_calendar_data": session_state.get('calendar_data', {}),
                
                # 年休残数（将来実装のため現在はデフォルト値）
                "annual_leave_remaining": self._get_annual_leave_data(gui_state.get('last_employees', [])),
                
                # システム設定
                "system_settings": {
                    "target_year": gui_state.get('year', 2025),
                    "target_month": gui_state.get('month', 6),
                    "priority_weights": self.config_manager.get_priority_weights()
                }
            }
            
            # ファイル保存
            filename = f"{config_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(self.configs_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(unified_config, f, ensure_ascii=False, indent=2, default=str)
            
            return filename
            
        except Exception as e:
            st.error(f"統合設定保存エラー: {str(e)}")
            return None
    
    def load_complete_config(self, filename, force_update_session=True):
        """全設定を統合読み込み・即反映"""
        try:
            filepath = os.path.join(self.configs_dir, filename)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 既存システムに強制反映
            self._apply_all_settings(config, force_update_session)
            
            return config
            
        except Exception as e:
            st.error(f"統合設定読み込みエラー: {str(e)}")
            return None
    
    def _apply_all_settings(self, config, force_update_session):
        """全設定を強制適用"""
        try:
            # 1. 従業員設定の強制更新
            employees = config.get("employees", [])
            self.config_manager.update_employees(employees)
            
            # 2. 勤務場所設定の強制更新
            work_locations = config.get("work_locations", [])
            self.location_manager.duty_locations = work_locations.copy()
            # ConfigManagerにも反映
            self.config_manager.current_config["work_locations"] = work_locations.copy()
            
            # 3. 優先度設定の強制更新
            priorities = config.get("employee_priorities", {})
            self.config_manager.update_employee_priorities(priorities)
            
            # 4. session_stateの強制更新
            if force_update_session:
                # 従業員リスト
                st.session_state.last_employees = employees.copy()
                
                # カレンダーデータ
                calendar_data = config.get("current_calendar_data", {})
                st.session_state.calendar_data = calendar_data
                
                # 警乗設定の反映
                keijo_settings = config.get("keijo_settings", {})
                if keijo_settings.get("base_date"):
                    base_date_str = keijo_settings["base_date"]
                    if isinstance(base_date_str, str):
                        try:
                            st.session_state.keijo_base_date = datetime.fromisoformat(base_date_str).date()
                        except:
                            st.session_state.keijo_base_date = date(2025, 6, 1)
                    else:
                        st.session_state.keijo_base_date = date(2025, 6, 1)
                
                # システム設定の反映
                system_settings = config.get("system_settings", {})
                if system_settings.get("target_year"):
                    st.session_state.year = system_settings.get("target_year", 2025)
                if system_settings.get("target_month"):
                    st.session_state.month = system_settings.get("target_month", 6)
                
                # 年休残数の反映（将来実装）
                annual_leave = config.get("annual_leave_remaining", {})
                if annual_leave:
                    st.session_state.annual_leave_remaining = annual_leave
                
                # 優先度重みの反映
                if system_settings.get("priority_weights"):
                    weights = system_settings["priority_weights"]
                    self.config_manager.current_config["priority_weights"] = weights
            
            return True
            
        except Exception as e:
            st.error(f"設定適用エラー: {str(e)}")
            return False
    
    def _get_annual_leave_data(self, employees):
        """年休残数データ取得（将来実装用）"""
        annual_leave = {}
        for emp in employees:
            # 現在はデフォルト値、将来的にはDBやファイルから取得
            annual_leave[emp] = self.default_annual_leave
        return annual_leave
    
    def get_config_preview(self, filename):
        """設定ファイルのプレビュー情報を取得"""
        try:
            filepath = os.path.join(self.configs_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            preview = {
                "config_name": config.get("config_name", "不明"),
                "created_date": config.get("created_date", "不明"),
                "last_modified": config.get("last_modified", "不明"),
                "employees_count": len(config.get("employees", [])),
                "work_locations_count": len(config.get("work_locations", [])),
                "has_calendar_data": bool(config.get("current_calendar_data", {})),
                "keijo_enabled": config.get("keijo_settings", {}).get("enabled", False)
            }
            
            return preview
            
        except Exception as e:
            return {"error": f"プレビュー取得エラー: {str(e)}"}
    
    def delete_config(self, filename):
        """統合設定ファイルの削除"""
        try:
            filepath = os.path.join(self.configs_dir, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
            return False
        except Exception as e:
            st.error(f"設定削除エラー: {str(e)}")
            return False
    
    def export_config(self, filename):
        """設定をエクスポート用形式で取得"""
        try:
            filepath = os.path.join(self.configs_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            st.error(f"設定エクスポートエラー: {str(e)}")
            return None
    
    def import_config(self, config_content, config_name):
        """設定をインポート"""
        try:
            config = json.loads(config_content)
            
            # 基本的なバリデーション
            required_keys = ["employees", "work_locations", "employee_priorities"]
            for key in required_keys:
                if key not in config:
                    raise ValueError(f"必須キー '{key}' が見つかりません")
            
            # ファイル名生成
            filename = f"{config_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(self.configs_dir, filename)
            
            # 作成日時を更新
            config["config_name"] = config_name
            config["created_date"] = datetime.now().strftime("%Y-%m-%d")
            config["last_modified"] = datetime.now().isoformat()
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2, default=str)
            
            return filename
            
        except Exception as e:
            st.error(f"設定インポートエラー: {str(e)}")
            return None
    
    def overwrite_config(self, filename, config_name, session_state, gui_state):
        """🆕 既存の統合設定ファイルを上書き保存"""
        try:
            # 既存設定ファイルを読み込んで元の情報を保持
            filepath = os.path.join(self.configs_dir, filename)
            existing_config = {}
            
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    existing_config = json.load(f)
            
            # 新しい統合設定を作成（save_complete_configと同じロジック）
            unified_config = {
                "config_name": config_name,
                "created_date": existing_config.get("created_date", datetime.now().strftime("%Y-%m-%d")),
                "last_modified": datetime.now().isoformat(),
                
                # 従業員設定
                "employees": gui_state.get('last_employees', []),
                
                # 勤務場所設定  
                "work_locations": self.location_manager.get_duty_locations(),
                
                # 優先度設定
                "employee_priorities": self.config_manager.get_employee_priorities(),
                
                # 警乗設定
                "keijo_settings": {
                    "base_date": gui_state.get('keijo_base_date', date(2025, 6, 1)).isoformat(),
                    "enabled": True
                },
                
                # カレンダーデータ（年休申請・勤務希望）
                "current_calendar_data": session_state.get('calendar_data', {}),
                
                # 年休残数（将来実装のため現在はデフォルト値）
                "annual_leave_remaining": self._get_annual_leave_data(gui_state.get('last_employees', [])),
                
                # システム設定
                "system_settings": {
                    "target_year": gui_state.get('year', 2025),
                    "target_month": gui_state.get('month', 6),
                    "priority_weights": self.config_manager.get_priority_weights()
                }
            }
            
            # ファイル上書き保存
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(unified_config, f, ensure_ascii=False, indent=2, default=str)
            
            return True
            
        except Exception as e:
            st.error(f"設定上書き保存エラー: {str(e)}")
            return False
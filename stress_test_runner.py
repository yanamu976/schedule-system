#!/usr/bin/env python3
"""
🧪 勤務表ストレステストアプリ (stress_test_runner.py)

メインアプリ（schedule_gui_fixed.py）をテストする完全独立したテストアプリ
- 完全分離アーキテクチャ
- メインアプリに一切の変更なし
- 大量テストケースの自動実行
- Excel一括出力

作成者: Claude Code for としかずさん
"""

import streamlit as st
import json
import os
import calendar
from datetime import datetime, timedelta
import pandas as pd
import io
import traceback
from typing import Dict, List, Any, Tuple, Optional

# メインアプリからの必要なクラスをimport（完全独立）
try:
    from schedule_gui_fixed import (
        CompleteScheduleEngine,
        WorkLocationManager, 
        ConfigurationManager,
        ExcelExporter
    )
except ImportError as e:
    st.error(f"メインアプリのimportに失敗しました: {e}")
    st.stop()


class StressTestRunner:
    """ストレステスト実行エンジン"""
    
    def __init__(self):
        """初期化"""
        self.config_manager = ConfigurationManager()
        self.location_manager = WorkLocationManager(self.config_manager)
        self.schedule_engine = CompleteScheduleEngine(self.location_manager, self.config_manager)
        self.excel_exporter = ExcelExporter(self.schedule_engine)
        
        # テストシナリオディレクトリ
        self.test_scenarios_dir = "test_scenarios"
        self.test_results_dir = "test_results"
        
        # 結果格納
        self.test_results = {}
        
    def load_test_scenarios(self) -> Dict[str, Dict]:
        """全テストシナリオを読み込み"""
        scenarios = {}
        
        scenario_files = [
            ("basic", "basic_tests.json"),
            ("stress", "stress_tests.json"), 
            ("extreme", "extreme_tests.json")
        ]
        
        for category, filename in scenario_files:
            file_path = os.path.join(self.test_scenarios_dir, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for test_name, test_data in data.items():
                            test_data['category'] = category
                            scenarios[test_name] = test_data
                except Exception as e:
                    st.warning(f"シナリオファイル読み込みエラー ({filename}): {e}")
        
        return scenarios
    
    def create_calendar_data(self, year: int, month: int, holidays: Dict[str, List[int]]) -> Dict:
        """カレンダーデータを生成"""
        num_days = calendar.monthrange(year, month)[1]
        
        # 基本カレンダー（全て勤務日として初期化）
        calendar_data = {}
        for day in range(1, num_days + 1):
            calendar_data[day] = {"type": "勤務日", "name": ""}
        
        # 休暇希望を反映
        for employee, holiday_days in holidays.items():
            for day in holiday_days:
                if 1 <= day <= num_days:
                    if day not in calendar_data:
                        calendar_data[day] = {"type": "休日", "name": ""}
                    # 複数人の休暇が重なる場合は休日として扱う
                    calendar_data[day]["type"] = "休日"
        
        return calendar_data
    
    def create_prev_schedule_data(self, prev_duties: List[Dict]) -> Optional[str]:
        """前月勤務データを生成"""
        if not prev_duties:
            return None
            
        # 簡単な前月勤務データフォーマット
        lines = []
        for duty in prev_duties:
            employee = duty.get("employee", "")
            duty_type = duty.get("duty", "勤務")
            if duty_type == "勤務":
                lines.append(f"{employee}: 前月末勤務")
        
        return "\\n".join(lines) if lines else None
    
    def run_single_test(self, test_name: str, test_data: Dict, year: int, month: int) -> Dict:
        """単一テストケースを実行"""
        result = {
            "test_name": test_name,
            "category": test_data.get("category", "unknown"),
            "description": test_data.get("description", ""),
            "status": "未実行",
            "relaxation_level": 0,
            "error_message": "",
            "execution_time": 0,
            "result_data": None,
            "excel_data": None
        }
        
        try:
            start_time = datetime.now()
            
            # テストデータから必要な情報を抽出
            employees = test_data.get("employees", [])
            holidays = test_data.get("holidays", {})
            prev_duties = test_data.get("prev_month_duties", [])
            
            # カレンダーデータ生成
            calendar_data = self.create_calendar_data(year, month, holidays)
            
            # 前月勤務データ生成
            prev_schedule_data = self.create_prev_schedule_data(prev_duties)
            
            # スケジュール生成実行
            schedule_result = self.schedule_engine.solve_schedule(
                year=year,
                month=month,
                employee_names=employees,
                calendar_data=calendar_data,
                prev_schedule_data=prev_schedule_data
            )
            
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            if schedule_result and schedule_result.get("success", False):
                result["status"] = "成功"
                result["relaxation_level"] = schedule_result.get("relaxation_level", 0)
                result["result_data"] = schedule_result
                result["execution_time"] = execution_time
                
                # Excel出力データ生成
                result["excel_data"] = self.generate_excel_data(
                    test_name, year, month, schedule_result
                )
                
            else:
                result["status"] = "失敗"
                result["error_message"] = schedule_result.get("error", "不明なエラー")
                result["execution_time"] = execution_time
                
        except Exception as e:
            result["status"] = "エラー"
            result["error_message"] = str(e)
            result["execution_time"] = (datetime.now() - start_time).total_seconds() if 'start_time' in locals() else 0
            
        return result
    
    def generate_excel_data(self, test_name: str, year: int, month: int, result_data: Dict) -> bytes:
        """Excel出力データを生成"""
        try:
            filename = f"{test_name}_{year}{month:02d}.xlsx"
            
            # 一時的なファイルパスを使用
            temp_path = os.path.join(self.test_results_dir, filename)
            
            # ディレクトリが存在しない場合は作成
            os.makedirs(self.test_results_dir, exist_ok=True)
            
            # Excel出力
            self.excel_exporter.create_excel_file(temp_path, result_data)
            
            # ファイルからデータを読み込み
            with open(temp_path, 'rb') as f:
                excel_data = f.read()
            
            # 一時ファイルを削除
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
            return excel_data
            
        except Exception as e:
            st.error(f"Excel生成エラー ({test_name}): {e}")
            return None
    
    def run_test_suite(self, test_suite: str, year: int, month: int, scenarios: Dict) -> Dict:
        """テストスイートを実行"""
        
        # テストスイート別のフィルタリング
        test_filters = {
            "基本テスト": ["normal_3people", "normal_5people", "normal_8people"],
            "標準テスト": [
                "normal_3people", "normal_5people", "normal_8people",
                "heavy_holidays_start", "heavy_holidays_middle", 
                "cross_month_nitetu", "minimum_staff", "new_employee_flood"
            ],
            "完全テスト": list(scenarios.keys())  # 全てのテストケース
        }
        
        selected_tests = test_filters.get(test_suite, [])
        results = {}
        
        # プログレスバー
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_tests = len(selected_tests)
        
        for i, test_name in enumerate(selected_tests):
            if test_name in scenarios:
                status_text.text(f"実行中: {test_name} ({i+1}/{total_tests})")
                
                test_data = scenarios[test_name]
                result = self.run_single_test(test_name, test_data, year, month)
                results[test_name] = result
                
                progress_bar.progress((i + 1) / total_tests)
            else:
                st.warning(f"テストケース '{test_name}' が見つかりません")
        
        status_text.text("テスト完了!")
        
        return results


def display_test_results(results: Dict):
    """テスト結果を表示"""
    if not results:
        st.info("実行結果がありません")
        return
    
    st.subheader("📊 実行結果")
    
    # サマリー統計
    total_tests = len(results)
    success_count = sum(1 for r in results.values() if r["status"] == "成功")
    failed_count = sum(1 for r in results.values() if r["status"] == "失敗")
    error_count = sum(1 for r in results.values() if r["status"] == "エラー")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("総テスト数", total_tests)
    with col2:
        st.metric("成功", success_count, delta=f"{success_count/total_tests*100:.1f}%")
    with col3:
        st.metric("失敗", failed_count, delta=f"{failed_count/total_tests*100:.1f}%")
    with col4:
        st.metric("エラー", error_count, delta=f"{error_count/total_tests*100:.1f}%")
    
    # 詳細結果
    for test_name, result in results.items():
        status = result["status"]
        
        # ステータス別のアイコンと色
        if status == "成功":
            icon = "✅"
            status_color = "green"
        elif status == "失敗":
            icon = "⚠️"
            status_color = "orange"
        else:
            icon = "❌"
            status_color = "red"
        
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 2])
            
            with col1:
                st.write(f"{icon} **{test_name}**: {result['description']}")
                if result["error_message"]:
                    st.error(f"Error: {result['error_message']}")
            
            with col2:
                if status == "成功":
                    st.success(f"緩和Lv{result['relaxation_level']}")
                else:
                    st.error(status)
            
            with col3:
                if result["excel_data"]:
                    st.download_button(
                        f"📥 Excel",
                        data=result["excel_data"],
                        file_name=f"{test_name}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"download_{test_name}"
                    )


def main():
    """メインアプリケーション"""
    st.set_page_config(
        page_title="🧪 勤務表ストレステストアプリ",
        page_icon="🧪",
        layout="wide"
    )
    
    st.title("🧪 勤務表ストレステストアプリ")
    st.markdown("---")
    st.markdown("**メインアプリ（schedule_gui_fixed.py）の品質検証システム**")
    
    # テストランナー初期化
    test_runner = StressTestRunner()
    
    # サイドバー設定
    with st.sidebar:
        st.header("⚙️ テスト設定")
        
        # 年月選択
        current_date = datetime.now()
        year = st.selectbox("年", range(2024, 2030), index=1)  # デフォルト2025
        month = st.selectbox("月", range(1, 13), index=current_date.month - 1)
        
        # テストスイート選択
        test_suite = st.radio(
            "🎯 テストセット選択",
            ["基本テスト", "標準テスト", "完全テスト"],
            index=1
        )
        
        suite_descriptions = {
            "基本テスト": "3パターン（通常動作確認）",
            "標準テスト": "8パターン（実用的なテスト）", 
            "完全テスト": "15パターン（全シナリオ実行）"
        }
        
        st.caption(suite_descriptions[test_suite])
    
    # メインエリア
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader(f"📅 対象: {year}年{month}月")
        st.write(f"選択中: **{test_suite}** ({suite_descriptions[test_suite]})")
    
    with col2:
        run_tests = st.button("🚀 ストレステスト実行", type="primary", use_container_width=True)
    
    # テストシナリオ読み込み
    scenarios = test_runner.load_test_scenarios()
    
    if not scenarios:
        st.error("テストシナリオが読み込めませんでした。test_scenarios/ ディレクトリを確認してください。")
        return
    
    # テスト実行
    if run_tests:
        st.markdown("---")
        with st.spinner("テスト実行中..."):
            results = test_runner.run_test_suite(test_suite, year, month, scenarios)
            st.session_state['test_results'] = results
    
    # 結果表示
    if 'test_results' in st.session_state:
        st.markdown("---")
        display_test_results(st.session_state['test_results'])
    
    # テストシナリオ一覧表示（展開可能）
    with st.expander("📋 利用可能なテストシナリオ"):
        for category in ["basic", "stress", "extreme"]:
            category_scenarios = {k: v for k, v in scenarios.items() if v.get("category") == category}
            if category_scenarios:
                st.write(f"**{category.upper()}**")
                for name, data in category_scenarios.items():
                    st.write(f"- {name}: {data.get('description', '')}")
                st.write("")


if __name__ == "__main__":
    main()
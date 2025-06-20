#!/usr/bin/env python3
"""
🔍 勤務表「解なし原因分析機能」

メインアプリ（schedule_gui_fixed.py）の「解なし」原因を分析し、
具体的な対処法を提示する後付け分析システム

作成者: Claude Code for としかずさん
"""

import calendar
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
from collections import defaultdict


class FailureAnalyzer:
    """解なし原因分析クラス"""
    
    def __init__(self):
        """初期化"""
        self.analysis_cache = {}
        
    def analyze_failure_reason(self, 
                             debug_info: List[str], 
                             constraints_data: Dict,
                             year: int,
                             month: int,
                             employee_names: List[str],
                             calendar_data: Dict = None,
                             prev_schedule_data: str = None) -> Tuple[str, str, List[str]]:
        """
        解なし原因を特定し対処法を提案
        
        Args:
            debug_info: デバッグ情報リスト
            constraints_data: 制約データ
            year: 対象年
            month: 対象月
            employee_names: 従業員名リスト
            calendar_data: カレンダーデータ
            prev_schedule_data: 前月勤務データ
            
        Returns:
            (原因カテゴリ, 詳細説明, 対処法リスト)
        """
        
        # 1. 人員不足チェック（最優先）
        # 実際の勤務場所数を取得
        work_locations_count = constraints_data.get('work_locations_count', 3)
        personnel_result = self._check_personnel_shortage(employee_names, work_locations_count)
        if personnel_result:
            return personnel_result
            
        # 2. 休暇集中チェック
        if calendar_data:
            holiday_result = self._check_holiday_concentration(
                calendar_data, employee_names, year, month
            )
            if holiday_result:
                return holiday_result
        
        # 3. 月またぎ制約チェック
        if prev_schedule_data:
            cross_month_result = self._check_cross_month_conflict(
                prev_schedule_data, employee_names, calendar_data
            )
            if cross_month_result:
                return cross_month_result
        
        # 4. 制約緩和レベル不足チェック
        relax_result = self._check_relaxation_level_needed(debug_info)
        if relax_result:
            return relax_result
            
        # 5. 一般的制約競合
        return self._general_constraint_conflict(debug_info, constraints_data)
    
    def _check_personnel_shortage(self, employee_names: List[str], work_locations_count: int = None) -> Optional[Tuple[str, str, List[str]]]:
        """人員不足の判定"""
        num_employees = len(employee_names)
        
        # 勤務場所数を動的に取得（デフォルトは3箇所）
        min_required = work_locations_count if work_locations_count else 3
        
        if num_employees < min_required:
            reason = "人員不足"
            detail = f"最低{min_required}人必要ですが{num_employees}人しか設定されていません\\n" + \
                    f"勤務場所：{min_required}箇所\\n" + \
                    f"設定人員：{', '.join(employee_names)}（{num_employees}人）"
            
            solutions = [
                f"助勤を{min_required - num_employees}名以上追加してください",
                f"勤務場所を{num_employees}箇所に減らしてください",
                "一部勤務場所を非常勤で対応してください"
            ]
            
            return reason, detail, solutions
        
        elif num_employees == min_required:
            # ギリギリ人員の場合の特別分析
            reason = "ギリギリ人員での制約競合"
            detail = f"人員数と勤務場所数が同数（{num_employees}人 vs {min_required}箇所）\\n" + \
                    f"制約が厳しすぎて配置不可能な状況\\n" + \
                    f"二徹制限、三徹禁止、休暇制約などが競合"
            
            solutions = [
                "助勤を1-2名追加してください（推奨）",
                "制約緩和レベルを2以上に上げてください",
                "一部勤務場所を削除してください",
                "休暇申請を調整してください"
            ]
            
            return reason, detail, solutions
            
        return None
    
    def _check_holiday_concentration(self, 
                                   calendar_data: Dict,
                                   employee_names: List[str],
                                   year: int,
                                   month: int) -> Optional[Tuple[str, str, List[str]]]:
        """休暇集中日の特定"""
        
        # 日別の休暇申請者数をカウント
        daily_holiday_count = defaultdict(list)
        
        # カレンダーデータから休暇情報を抽出
        for emp_name in employee_names:
            if emp_name in calendar_data:
                emp_data = calendar_data[emp_name]
                holidays = emp_data.get('holidays', [])
                
                for holiday in holidays:
                    if hasattr(holiday, 'day'):
                        day = holiday.day
                    elif isinstance(holiday, int):
                        day = holiday
                    else:
                        continue
                        
                    daily_holiday_count[day].append(emp_name)
        
        # 人員不足となる日をチェック
        num_days = calendar.monthrange(year, month)[1]
        min_required_staff = 3  # 基本勤務場所数
        
        for day in range(1, num_days + 1):
            holiday_requesters = daily_holiday_count.get(day, [])
            available_staff = len(employee_names) - len(holiday_requesters)
            
            if available_staff < min_required_staff:
                reason = "休暇集中"
                detail = f"{month}月{day}日に{len(holiday_requesters)}人が休暇申請\\n" + \
                        f"申請者：{', '.join(holiday_requesters)}\\n" + \
                        f"必要人員：{min_required_staff}人、申請後残り：{available_staff}人"
                
                solutions = [
                    f"{day}日の休暇申請を他の日に分散してください",
                    f"助勤で{day}日をカバーしてください",
                    "制約緩和レベルを2以上に上げてください",
                    f"{day}日を特別勤務日として設定してください"
                ]
                
                return reason, detail, solutions
        
        return None
    
    def _check_cross_month_conflict(self,
                                  prev_schedule_data: str,
                                  employee_names: List[str],
                                  calendar_data: Dict = None) -> Optional[Tuple[str, str, List[str]]]:
        """月またぎ制約競合の検出"""
        
        if not prev_schedule_data:
            return None
            
        # 前月末勤務者を特定
        prev_workers = []
        lines = prev_schedule_data.strip().split('\\n')
        
        for line in lines:
            line = line.strip()
            if '前月末勤務' in line or '勤務' in line:
                # "田中: 前月末勤務" や "田中: 勤務" の形式を想定
                for emp_name in employee_names:
                    if emp_name in line:
                        prev_workers.append(emp_name)
                        break
        
        if not prev_workers:
            return None
            
        # 1日目の勤務希望があるかチェック
        first_day_conflicts = []
        if calendar_data:
            for emp_name in prev_workers:
                if emp_name in calendar_data:
                    emp_data = calendar_data[emp_name]
                    # 1日目に勤務希望がある場合は二徹制約違反の可能性
                    duty_preferences = emp_data.get('duty_preferences', {})
                    if 1 in duty_preferences:
                        first_day_conflicts.append(emp_name)
        
        if first_day_conflicts or len(prev_workers) >= len(employee_names) - 1:
            reason = "月またぎ制約"
            detail = f"前月末勤務者との競合\\n" + \
                    f"前月末勤務：{', '.join(prev_workers)}\\n" + \
                    f"二徹制約により1日目の配置が困難"
            
            if first_day_conflicts:
                detail += f"\\n1日目勤務希望：{', '.join(first_day_conflicts)}"
            
            solutions = [
                "前月末勤務設定を確認してください",
                "1日目の勤務希望を調整してください",
                "助勤で1日目をカバーしてください",
                "制約緩和レベルを3以上に上げてください"
            ]
            
            return reason, detail, solutions
            
        return None
    
    def _check_relaxation_level_needed(self, debug_info: List[str]) -> Optional[Tuple[str, str, List[str]]]:
        """制約緩和レベル不足のチェック"""
        
        # デバッグ情報から制約違反の種類を特定
        constraint_violations = []
        
        for info in debug_info:
            if '二徹' in info:
                constraint_violations.append("二徹制限")
            elif '三徹' in info:
                constraint_violations.append("三徹禁止")
            elif '非番' in info:
                constraint_violations.append("非番制約")
            elif '有休' in info:
                constraint_violations.append("有休制約")
        
        if constraint_violations:
            reason = "制約緩和不足"
            detail = f"以下の制約が競合しています\\n" + \
                    f"違反制約：{', '.join(set(constraint_violations))}"
            
            solutions = [
                "制約緩和レベルを段階的に上げてください（レベル1→2→3）",
                "勤務希望を調整してください",
                "助勤を追加してください",
                "一部制約を一時的に緩和してください"
            ]
            
            return reason, detail, solutions
            
        return None
    
    def _general_constraint_conflict(self, 
                                   debug_info: List[str], 
                                   constraints_data: Dict) -> Tuple[str, str, List[str]]:
        """一般的制約競合の分析"""
        
        reason = "制約競合"
        detail = "複数の制約が競合しています"
        
        # デバッグ情報から具体的な問題を特定
        if debug_info:
            specific_issues = []
            for info in debug_info:
                if '希望' in info:
                    specific_issues.append("勤務希望の競合")
                elif '制約' in info:
                    specific_issues.append("制約の競合")
                elif '不足' in info:
                    specific_issues.append("人員不足")
            
            if specific_issues:
                detail = f"以下の問題が検出されました\\n" + \
                        f"問題：{', '.join(set(specific_issues))}"
        
        solutions = [
            "制約緩和レベルを上げてください（レベル2以上推奨）",
            "勤務希望を分散してください",
            "助勤の追加を検討してください",
            "勤務場所の設定を見直してください",
            "従業員の優先度設定を調整してください"
        ]
        
        return reason, detail, solutions
    
    def get_analysis_summary(self, 
                           analysis_result: Tuple[str, str, List[str]]) -> Dict[str, Any]:
        """分析結果のサマリーを取得"""
        
        reason, detail, solutions = analysis_result
        
        return {
            "category": reason,
            "description": detail,
            "solutions": solutions,
            "urgency": self._get_urgency_level(reason),
            "estimated_fix_time": self._estimate_fix_time(reason)
        }
    
    def _get_urgency_level(self, reason: str) -> str:
        """緊急度レベルを取得"""
        urgency_map = {
            "人員不足": "高",
            "休暇集中": "中",
            "月またぎ制約": "中", 
            "制約緩和不足": "低",
            "制約競合": "低"
        }
        return urgency_map.get(reason, "低")
    
    def _estimate_fix_time(self, reason: str) -> str:
        """修正時間の目安を取得"""
        time_map = {
            "人員不足": "1-2時間（人員調整）",
            "休暇集中": "30分-1時間（日程調整）",
            "月またぎ制約": "15-30分（設定確認）",
            "制約緩和不足": "5-15分（レベル調整）",
            "制約競合": "15-30分（設定見直し）"
        }
        return time_map.get(reason, "15-30分")
    
    def _estimate_work_locations_count(self, constraints_data: Dict) -> int:
        """勤務場所数を推定（実際のシステムから情報が取得できない場合の対処）"""
        # デフォルトは3箇所だが、より多くの場所がある可能性を考慮
        # 人員数から推定：8人いるなら最低6-8箇所はあると推定
        # 実装を簡単にするため、まずは固定値で対応
        return 8  # 8箇所と仮定（実際の現場に合わせて調整）
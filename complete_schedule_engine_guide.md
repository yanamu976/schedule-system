# CompleteScheduleEngine 完全解説書
## 勤務表自動作成エンジンの仕組みを詳しく理解する

---

## 📚 目次

1. [CompleteScheduleEngineとは？](#1-completescheduleengineとは)
2. [全体アーキテクチャ](#2-全体アーキテクチャ)
3. [主要メソッドの詳細解説](#3-主要メソッドの詳細解説)
4. [制約プログラミングの数学的背景](#4-制約プログラミングの数学的背景)
5. [制約緩和メカニズム](#5-制約緩和メカニズム)
6. [データ構造と内部処理](#6-データ構造と内部処理)
7. [実践的な使用例](#7-実践的な使用例)
8. [トラブルシューティング](#8-トラブルシューティング)

---

## 1. CompleteScheduleEngineとは？

### 🎯 基本概念

`CompleteScheduleEngine`は、**Google OR-Tools**の制約プログラミング（CP-SAT）を使用した高度な勤務表自動生成システムです。単純なルールベースではなく、**数学的最適化**により、複雑な制約条件を満たす最適なスケジュールを生成します。

### 🏗️ システムの位置づけ

```
📊 データ入力
    ↓
🧠 CompleteScheduleEngine (ここが核心！)
    ↓
📋 最適スケジュール出力
```

### 📍 ファイル内の位置
- **ファイル**: `schedule_gui_fixed.py`
- **行番号**: 216-779行目（564行に渡る大規模クラス）
- **実装言語**: Python + OR-Tools

---

## 2. 全体アーキテクチャ

### 🏛️ クラス構造

```python
class CompleteScheduleEngine:
    """完全版勤務表生成エンジン（Phase 1: 優先度対応）"""
    
    def __init__(self, location_manager, config_manager=None):
        # 初期化：重み設定、制約緩和メッセージ等
        
    def solve_schedule(self, n_days, ng_constraints, preferences, holidays):
        # メイン処理：スケジュール生成の全体制御
        
    def build_optimization_model(self, ...):
        # OR-Toolsモデル構築：制約とペナルティの定義
        
    def solve_with_relaxation(self, ...):
        # 制約緩和：解が見つからない場合の段階的緩和
```

### 🔄 処理フロー

```
[1] 初期化・設定読み込み
    ↓
[2] 要求文解析 (parse_requirements)
    ↓
[3] 前月データ解析 (parse_previous_month_schedule)
    ↓
[4] 最適化モデル構築 (build_optimization_model)
    ↓
[5] 制約緩和求解 (solve_with_relaxation)
    ↓
[6] 結果抽出・検証
```

### 📊 入出力仕様

#### 入力
- **従業員リスト**: `["田中", "佐藤", "鈴木"]`
- **対象期間**: 日数（通常30-31日）
- **制約条件**: NG制約、希望、有休
- **前月末データ**: 月またぎ制約用

#### 出力
- **最適スケジュール**: 日次割り当て結果
- **制約充足状況**: どの制約が満たされたか
- **統計情報**: 二徹回数、ペナルティ値等

---

## 3. 主要メソッドの詳細解説

### 🚀 3.1 `solve_schedule()` - メイン制御メソッド

**役割**: スケジュール生成全体の制御を行う最重要メソッド

```python
def solve_schedule(self, n_days, ng_constraints, preferences, holidays, 
                  prev_schedule=None, requirement_lines=None, employee_priorities=None):
    """
    スケジュール生成のメイン制御
    
    引数:
        n_days: 対象月の日数
        ng_constraints: NG制約辞書
        preferences: 希望設定辞書  
        holidays: 有休希望セット
        prev_schedule: 前月末スケジュール
        requirement_lines: 要求文リスト
        employee_priorities: 従業員優先度設定
    
    戻り値:
        dict: 生成結果（成功/失敗、スケジュール、統計等）
    """
```

#### 処理ステップ詳細

**Step 1: システム初期化**
```python
# 従業員・勤務場所の設定
self.setup_system(employee_names)

# 前月データの解析
prev_duties = None
if prev_schedule:
    prev_duties, prev_debug = self.parse_previous_month_schedule(prev_schedule)
```

**Step 2: 要求文解析**
```python
# 自然言語要求の構造化
ng_constraints, preferences, holidays, priority_violations, req_debug = \
    self.parse_requirements(requirement_lines, n_days, employee_priorities)
```

**Step 3: 制約緩和求解**
```python
# 段階的制約緩和による解の探索
result = self.solve_with_relaxation(n_days, ng_constraints, preferences, holidays, prev_duties)
```

### 🔧 3.2 `parse_requirements()` - 要求文解析

**役割**: 自然言語で書かれた要求を制約として構造化

```python
def parse_requirements(self, requirement_lines, n_days, employee_priorities=None):
    """要求文を解析して制約に変換"""
    
    ng_constraints = defaultdict(list)
    preferences = defaultdict(list)  
    holidays = defaultdict(lambda: defaultdict(set))
    debug_info = []
```

#### 解析パターン例

**パターン1: 休暇希望**
```python
# "田中さんは1日と15日は休み"
holiday_match = re.search(r'(\w+)(?:さん)?は(.+?)(?:は|に)休み', line)
if holiday_match:
    name = holiday_match.group(1)
    date_part = holiday_match.group(2)
    
    # 日付抽出（複数形式対応）
    dates = re.findall(r'(\d+)日', date_part)
    dates.extend(re.findall(r'(\d+)-(\d+)', date_part))  # 範囲指定
```

**パターン2: 勤務希望**
```python
# "佐藤さんは警乗希望"
duty_match = re.search(r'(\w+)(?:さん)?は(.+?)希望', line)
if duty_match:
    employee_name = duty_match.group(1)
    duty_name = duty_match.group(2)
    
    if duty_name in self.duty_names:
        # 希望をペナルティ重みとして設定
        preferences[(emp_id, day, duty_id)] = preference_weight
```

**Phase 1新機能: 優先度ペナルティ**
```python
# 従業員優先度設定の処理
if employee_priorities:
    priority_weights = self.config_manager.get_priority_weights()
    for emp_name, duty_priorities in employee_priorities.items():
        for duty_name, priority in duty_priorities.items():
            if priority in priority_weights:
                penalty_weight = priority_weights[priority]
                # 優先度の低い勤務にペナルティを追加
```

### ⚙️ 3.3 `build_optimization_model()` - 最適化モデル構築

**役割**: OR-Toolsの制約プログラミングモデルを構築

```python
def build_optimization_model(self, n_days, ng_constraints, preferences, holidays, 
                           relax_level=0, prev_duties=None):
    """OR-Tools CP-SATモデルの構築"""
    
    model = cp_model.CpModel()
    
    # 決定変数の定義
    w = {}
    for e in range(self.n_employees):
        for d in range(n_days):
            for s in range(self.n_shifts):
                w[e, d, s] = model.NewBoolVar(f"w_{e}_{d}_{s}")
```

#### 制約の種類と実装

**基本制約1: 排他性制約**
```python
# 各従業員は1日1シフトのみ
for e in range(self.n_employees):
    for d in range(n_days):
        model.AddExactlyOne(w[e, d, s] for s in range(self.n_shifts))
```

**基本制約2: 割当制約**
```python
# 各勤務場所は1日1人必須
for d in range(n_days):
    for s in range(self.n_duties):
        model.Add(sum(w[e, d, s] for e in range(self.n_employees)) == 1)
```

**基本制約3: 連続性制約**
```python
# 勤務後は翌日非番
for e in range(self.n_employees):
    for d in range(n_days - 1):
        for s in range(self.n_duties):
            model.AddImplication(w[e, d, s], w[e, d + 1, self.OFF_SHIFT_ID])
```

**月またぎ制約**
```python
# 前日勤務なら1日目は必ず非番
if (e, -1) in prev_duties and prev_duties[(e, -1)]:
    model.Add(w[e, 0, self.OFF_SHIFT_ID] == 1)

# 月またぎ二徹制約
if (e, -2) in prev_duties and prev_duties[(e, -2)]:
    if relax_level == 0:
        # 厳格モード: 前々日勤務なら1日目勤務禁止
        for s in range(self.n_duties):
            model.Add(w[e, 0, s] == 0)
    else:
        # 緩和モード: ペナルティとして扱う
        nitetu_var = model.NewBoolVar(f"cross_nitetu_{e}")
        # ペナルティ項に追加
```

**二徹制約（勤務-非番-勤務パターン）**
```python
# i日目勤務 && (i+2)日目勤務 の検出
for e in range(self.n_employees):
    for d in range(n_days - 2):
        nitetu_var = model.NewBoolVar(f"nitetu_{e}_{d}")
        duty_flags = [sum(w[e, day, s] for s in range(self.n_duties)) for day in [d, d+2]]
        
        # 二徹検出: 両方勤務なら nitetu_var = True
        model.Add(duty_flags[0] + duty_flags[1] == 2).OnlyEnforceIf(nitetu_var)
        model.Add(duty_flags[0] + duty_flags[1] <= 1).OnlyEnforceIf(nitetu_var.Not())
```

#### ペナルティ項の構成

```python
objective_terms = []

# 1. 助勤使用ペナルティ
relief_weight = self.weights['RELIEF'] * (10 ** relax_level)
objective_terms.append(relief_weight * sum(relief_work_vars))

# 2. 有休違反ペナルティ  
holiday_weight = self.weights['HOLIDAY']
objective_terms.append(holiday_weight * sum(holiday_violations))

# 3. 二徹ペナルティ
objective_terms.append(self.weights['NITETU'] * sum(nitetu_vars))

# 4. 月またぎ二徹ペナルティ
objective_terms.append(self.weights['CROSS_MONTH'] * sum(cross_month_nitetu_vars))

# 5. 二徹格差ペナルティ（レベル1以降で緩和）
if relax_level == 0 and nitetu_gap != 0:
    objective_terms.append(self.weights['N2_GAP'] * nitetu_gap)

# 6. 希望違反ペナルティ
objective_terms.extend(preference_penalty_terms)

# 目的関数設定
model.Minimize(sum(objective_terms))
```

### 🔄 3.4 `solve_with_relaxation()` - 制約緩和求解

**役割**: 段階的に制約を緩和しながら実行可能解を探索

```python
def solve_with_relaxation(self, n_days, ng_constraints, preferences, holidays, prev_duties=None):
    """段階的制約緩和による求解"""
    
    for relax_level in range(4):  # レベル0-3の4段階
        # レベル3では有休を削減
        holidays_to_use = holidays
        reduction_note = ""
        
        if relax_level == 3:
            holidays_to_use, reduction_note = self.reduce_holidays(holidays)
        
        # モデル構築と求解
        model, w, nitetu_counts, cross_const = self.build_optimization_model(
            n_days, ng_constraints, preferences, holidays_to_use, relax_level, prev_duties
        )
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30  # 30秒制限
        status = solver.Solve(model)
        
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            # 解が見つかった場合の処理
            return relax_level, status, solver, w, nitetu_counts, relax_notes, cross_constraints
    
    # 全レベルで解が見つからない場合
    return None
```

#### 制約緩和の段階

```python
self.relax_messages = {
    0: "✅ 全制約満足",
    1: "⚠️ 二徹バランス緩和（格差許容）", 
    2: "⚠️ 助勤フル解禁（ペナルティ低減）",
    3: "⚠️ 有休の一部を勤務変更（休多→勤務優先）"
}
```

**レベル0（厳格モード）**:
- 全制約を厳密に満足
- 二徹格差ペナルティあり
- 助勤使用は高ペナルティ

**レベル1（二徹バランス緩和）**:
- 二徹格差制約を削除
- 従業員間の二徹回数差を許容

**レベル2（助勤解禁）**:
- 助勤ペナルティを大幅軽減
- より柔軟な人員配置を許可

**レベル3（有休削減）**:
- 最も有休の多い従業員から最大2件削減
- 勤務優先で解を確保

### 📊 3.5 `analyze_cross_month_constraints()` - 月またぎ分析

**役割**: 月またぎ制約の適用状況を分析・レポート

```python
def analyze_cross_month_constraints(self, prev_duties, solver, w, n_days):
    """月またぎ制約の詳細分析"""
    
    violations = []
    constraints_applied = []
    
    for emp_id in range(self.n_employees):
        emp_name = self.id_to_name[emp_id]
        
        # 前日勤務→1日目非番チェック
        if (emp_id, -1) in prev_duties and prev_duties[(emp_id, -1)]:
            if solver.Value(w[emp_id, 0, self.OFF_SHIFT_ID]):
                constraints_applied.append(f"✅ {emp_name}: 前日勤務→1日目非番 (正常)")
            else:
                violations.append(f"❌ {emp_name}: 前日勤務なのに1日目が非番でない")
        
        # 月またぎ二徹チェック
        if (emp_id, -2) in prev_duties and prev_duties[(emp_id, -2)]:
            day1_duty = any(solver.Value(w[emp_id, 0, s]) for s in range(self.n_duties))
            if day1_duty:
                violations.append(f"⚠️ {emp_name}: 月またぎ二徹発生")
            else:
                constraints_applied.append(f"✅ {emp_name}: 月またぎ二徹回避")
```

---

## 4. 制約プログラミングの数学的背景

### 📐 数学的定式化

#### 決定変数
```math
w_{e,d,s} ∈ {0,1}
```
- `e`: 従業員ID (0 ≤ e < n_employees)
- `d`: 日ID (0 ≤ d < n_days)  
- `s`: シフトID (0 ≤ s < n_shifts)
- `w_{e,d,s} = 1` ⟺ 従業員eが日dにシフトsを担当

#### 基本制約

**制約1: 排他性制約**
```math
∑_{s=0}^{n_shifts-1} w_{e,d,s} = 1, ∀e,d
```

**制約2: 割当制約**
```math
∑_{e=0}^{n_employees-1} w_{e,d,s} = 1, ∀d,s ∈ duties
```

**制約3: 連続性制約**
```math
w_{e,d,s} = 1 ⟹ w_{e,d+1,OFF} = 1, ∀e,d,s ∈ duties
```

#### 目的関数

```math
minimize: ∑_{penalties} weight × penalty_count
```

**ペナルティ項**:
- Relief: 助勤使用ペナルティ
- Holiday: 有休違反ペナルティ
- Nitetu: 二徹ペナルティ
- N2_Gap: 二徹格差ペナルティ
- Preference: 希望違反ペナルティ
- Cross_Month: 月またぎ二徹ペナルティ
- Priority: 優先度違反ペナルティ（Phase 1）

### 🧮 制約プログラミング vs 線形プログラミング

#### CP-SAT（制約プログラミング）の利点

**1. 複雑な論理制約の表現**
```python
# 「AならばB」の条件
model.AddImplication(condition_A, condition_B)

# 「排他的OR」の条件
model.AddExactlyOne([var1, var2, var3])
```

**2. 整数変数の効率的処理**
- 0-1変数による組み合わせ最適化
- 分枝限定法による厳密解

**3. 制約充足性の保証**
- Hard制約: 必ず満足
- Soft制約: ペナルティ付きで緩和可能

#### 線形プログラミングとの比較

| 項目 | CP-SAT | 線形プログラミング |
|------|--------|-------------------|
| 変数型 | 整数・0-1変数 | 連続変数（主） |
| 制約表現 | 論理制約、条件分岐 | 線形等式・不等式 |
| 解法 | 分枝限定+制約伝播 | シンプレックス法 |
| 適用問題 | 組み合わせ最適化 | 資源配分問題 |

---

## 5. 制約緩和メカニズム

### 🔧 制約緩和の哲学

実世界の勤務表作成では、**すべての制約を完璧に満足する解が存在しない**場合があります。CompleteScheduleEngineは、**段階的制約緩和**により、実用的な解を必ず提供します。

### 📊 4段階の制約緩和戦略

#### レベル0: 理想的制約（厳格モード）
```python
# 重み設定
weights = {
    'RELIEF': 10,      # 助勤使用は控えめに
    'NITETU': 15,      # 二徹は避ける
    'N2_GAP': 30,      # 二徹格差は厳禁
    'HOLIDAY': 50,     # 有休違反は重大
    'CROSS_MONTH': 20  # 月またぎ二徹は避ける
}

# 二徹格差制約あり
if nitetu_gap != 0:
    objective_terms.append(weights['N2_GAP'] * nitetu_gap)
```

#### レベル1: 二徹バランス緩和
```python
# 二徹格差制約を削除
# → 従業員間の二徹回数に差があっても許容

if relax_level == 0 and nitetu_gap != 0:  # レベル1以降では適用しない
    objective_terms.append(weights['N2_GAP'] * nitetu_gap)
```

#### レベル2: 助勤ペナルティ軽減
```python
# 助勤ペナルティを指数的に軽減
relief_weight = weights['RELIEF'] * (10 ** relax_level)
# レベル2では: 10 * (10^2) = 1000 → より助勤を使いやすく
```

#### レベル3: 有休削減
```python
def reduce_holidays(self, holidays, max_remove=2):
    """最も有休の多い従業員から最大2件削除"""
    
    holiday_by_employee = defaultdict(list)
    for emp_id, day in holidays:
        holiday_by_employee[emp_id].append(day)
    
    if not holiday_by_employee:
        return holidays, ""
    
    # 最も有休が多い従業員を特定
    max_employee = max(holiday_by_employee, key=lambda e: len(holiday_by_employee[e]))
    
    if len(holiday_by_employee[max_employee]) <= max_remove:
        return holidays, ""
    
    # 最大2件を削除
    removed_days = holiday_by_employee[max_employee][:max_remove]
    new_holidays = set(holidays)
    
    for day in removed_days:
        new_holidays.discard((max_employee, day))
    
    reduction_note = f"{self.id_to_name[max_employee]}さんの有休を{max_remove}件削減"
    return new_holidays, reduction_note
```

### 🎯 制約緩和の効果測定

```python
# 制約緩和レベルごとの成功率（例）
success_rates = {
    0: "85%",  # 理想的制約での解決率
    1: "95%",  # 二徹バランス緩和後
    2: "98%",  # 助勤解禁後  
    3: "99%"   # 有休削減後
}
```

---

## 6. データ構造と内部処理

### 🗂️ 主要データ構造

#### 6.1 従業員・シフト管理
```python
class CompleteScheduleEngine:
    def setup_system(self, employee_names):
        # 従業員管理
        self.employees = employee_names
        self.n_employees = len(employee_names)
        self.name_to_id = {name: i for i, name in enumerate(employee_names)}
        self.id_to_name = {i: name for i, name in enumerate(employee_names)}
        
        # シフト管理
        self.duty_names = self.location_manager.get_duty_names()  # ["駅A", "指令", "警乗"]
        self.n_duties = len(self.duty_names)
        self.shift_names = self.duty_names + [self.location_manager.holiday_type["name"]] + ["非番"]
        self.n_shifts = len(self.shift_names)
        self.OFF_SHIFT_ID = self.n_shifts - 1  # 非番シフトのID
```

#### 6.2 制約データ構造
```python
# NG制約: defaultdict(list)
ng_constraints = {
    "田中": [1, 15, 28],  # 田中さんの勤務不可日
    "佐藤": [10, 20]      # 佐藤さんの勤務不可日
}

# 希望設定: dict
preferences = {
    (0, 5, 1): 5,   # 従業員0が6日目に指令を希望（重み5）
    (1, 12, 0): 3   # 従業員1が13日目に駅Aを希望（重み3）
}

# 有休設定: set
holidays = {
    (0, 10),  # 従業員0が11日目に有休
    (2, 25)   # 従業員2が26日目に有休
}

# 前月データ: dict  
prev_duties = {
    (0, -1): True,   # 従業員0が前日勤務
    (0, -2): False,  # 従業員0が前々日非番
    (1, -1): False   # 従業員1が前日非番
}
```

#### 6.3 OR-Tools変数構造
```python
# 決定変数: 3次元辞書
w = {
    (0, 0, 0): BoolVar("w_0_0_0"),  # 従業員0が1日目に駅A
    (0, 0, 1): BoolVar("w_0_0_1"),  # 従業員0が1日目に指令
    (0, 0, 2): BoolVar("w_0_0_2"),  # 従業員0が1日目に警乗
    (0, 0, 3): BoolVar("w_0_0_3"),  # 従業員0が1日目に休暇
    (0, 0, 4): BoolVar("w_0_0_4"),  # 従業員0が1日目に非番
    # ... 全組み合わせ
}

# 補助変数
duty_flags = {
    (0, 0): IntVar(0, 1, "duty_0_0"),  # 従業員0が1日目に勤務するか
    # ...
}

# ペナルティ変数
nitetu_vars = [
    BoolVar("nitetu_0_0"),  # 従業員0の1-3日目二徹
    BoolVar("nitetu_0_1"),  # 従業員0の2-4日目二徹
    # ...
]
```

### ⚡ パフォーマンス最適化

#### 変数数の計算
```python
# 変数数 = 従業員数 × 日数 × シフト数
# 例: 3人 × 30日 × 5シフト = 450変数

total_variables = n_employees * n_days * n_shifts
print(f"決定変数数: {total_variables}")

# 制約数の見積もり
basic_constraints = n_employees * n_days + n_days * n_duties  # 基本制約
continuous_constraints = n_employees * (n_days - 1) * n_duties  # 連続性制約
nitetu_constraints = n_employees * (n_days - 2)  # 二徹制約

total_constraints = basic_constraints + continuous_constraints + nitetu_constraints
print(f"制約数: {total_constraints}")
```

#### メモリ効率化
```python
# 使用済み変数の即座開放
del model, solver, w
gc.collect()

# 大規模問題への対応
solver.parameters.max_time_in_seconds = 30  # タイムアウト設定
solver.parameters.num_search_workers = 4    # 並列探索
```

---

## 7. 実践的な使用例

### 🔧 基本的な使用方法

```python
# 1. インスタンス作成
from schedule_gui_fixed import CompleteScheduleEngine, WorkLocationManager, ConfigurationManager

config_manager = ConfigurationManager()
location_manager = WorkLocationManager(config_manager)
engine = CompleteScheduleEngine(location_manager, config_manager)

# 2. パラメータ設定
employee_names = ["田中", "佐藤", "鈴木"]
n_days = 30

# 3. 制約設定
ng_constraints = {
    "田中": [1, 15],  # 田中さんは2日と16日勤務不可
}

preferences = {}
holidays = {
    ("田中", 10),  # 田中さんは11日有休
    ("佐藤", 25)   # 佐藤さんは26日有休
}

# 4. スケジュール生成
result = engine.solve_schedule(
    n_days=n_days,
    ng_constraints=ng_constraints,
    preferences=preferences,
    holidays=holidays
)

# 5. 結果確認
if result['success']:
    print("✅ スケジュール生成成功")
    print(f"制約緩和レベル: {result['relax_level']}")
    schedule = result['schedule']
    
    # 結果表示
    for emp_name in employee_names:
        print(f"{emp_name}さん: {schedule[emp_name]}")
else:
    print("❌ スケジュール生成失敗")
    print(f"エラー: {result['error']}")
```

### 📊 高度な使用例：月またぎ制約

```python
# 前月末のスケジュール（最後3日分）
prev_schedule = {
    "田中": ["駅A", "非番", "指令"],    # 29日駅A、30日非番、31日指令
    "佐藤": ["非番", "警乗", "非番"],   # 29日非番、30日警乗、31日非番
    "鈴木": ["指令", "非番", "駅A"]     # 29日指令、30日非番、31日駅A
}

# 月またぎ制約を考慮したスケジュール生成
result = engine.solve_schedule(
    n_days=30,
    ng_constraints={},
    preferences={},
    holidays=set(),
    prev_schedule=prev_schedule  # 前月データを追加
)

# 月またぎ制約の分析結果
if result['success']:
    cross_month_analysis = result.get('cross_month_analysis', {})
    print("📋 月またぎ制約分析:")
    
    for constraint in cross_month_analysis.get('constraints_applied', []):
        print(f"  {constraint}")
    
    for violation in cross_month_analysis.get('violations', []):
        print(f"  {violation}")
```

### 🎯 Phase 1機能：優先度設定

```python
# 従業員優先度設定
employee_priorities = {
    "田中": {"駅A": 3, "指令": 2, "警乗": 0},  # 警乗が苦手
    "佐藤": {"駅A": 3, "指令": 3, "警乗": 3},  # オールラウンダー
    "鈴木": {"駅A": 0, "指令": 1, "警乗": 3}   # 駅Aが苦手
}

# 優先度を考慮したスケジュール生成
result = engine.solve_schedule(
    n_days=30,
    ng_constraints={},
    preferences={},
    holidays=set(),
    employee_priorities=employee_priorities  # Phase 1新機能
)

# 優先度ペナルティの確認
if result['success']:
    priority_info = result.get('priority_violations', [])
    for info in priority_info:
        print(f"📊 優先度情報: {info}")
```

---

## 8. トラブルシューティング

### ❌ よくある問題と解決方法

#### 問題1: 解が見つからない（全制約緩和レベルで失敗）

**症状**:
```python
{
    'success': False,
    'error': '解を見つけられませんでした',
    'debug_info': ['制約緩和レベル0-3すべてで失敗']
}
```

**原因と対策**:

1. **過度な制約**
   ```python
   # 問題のあるケース
   ng_constraints = {
       "田中": list(range(1, 31)),  # 全日勤務不可
       "佐藤": list(range(1, 31)),  # 全日勤務不可
   }
   
   # 解決策: 制約を現実的に設定
   ng_constraints = {
       "田中": [1, 15, 28],  # 適度な制約
       "佐藤": [10, 20]
   }
   ```

2. **有休過多**
   ```python
   # 問題: 従業員数に対して有休が多すぎる
   holidays = {("田中", day) for day in range(1, 16)}  # 15日間有休
   
   # 解決策: 現実的な有休設定
   holidays = {("田中", 10), ("田中", 25)}  # 2日間有休
   ```

3. **前月データの不整合**
   ```python
   # 問題: 前月末が全員勤務（1日目が全員非番になり、勤務者不足）
   prev_schedule = {
       "田中": ["駅A", "指令", "警乗"],
       "佐藤": ["指令", "警乗", "駅A"], 
       "鈴木": ["警乗", "駅A", "指令"]
   }
   
   # 解決策: 現実的な前月末設定
   prev_schedule = {
       "田中": ["駅A", "非番", "非番"],
       "佐藤": ["非番", "指令", "非番"],
       "鈴木": ["非番", "非番", "警乗"]
   }
   ```

#### 問題2: 期待通りの結果にならない

**症状**: 解は見つかるが、希望が反映されない

**対策**:

1. **重み調整**
   ```python
   # 重みを確認・調整
   engine.weights['PREF'] = 10  # 希望重視
   engine.weights['NITETU'] = 5  # 二徹許容
   ```

2. **優先度設定の確認**
   ```python
   # Phase 1: 優先度が正しく設定されているか確認
   print("優先度設定:", employee_priorities)
   
   # デバッグ情報で優先度適用状況を確認
   debug_info = result.get('debug_info', [])
   for info in debug_info:
       if '優先度' in info:
           print(f"優先度情報: {info}")
   ```

#### 問題3: パフォーマンス問題

**症状**: 求解に時間がかかる（30秒でタイムアウト）

**対策**:

1. **タイムアウト延長**
   ```python
   # タイムアウトを延長（build_optimization_model内）
   solver.parameters.max_time_in_seconds = 60  # 60秒に延長
   ```

2. **問題サイズの縮小**
   ```python
   # 従業員数、日数、シフト数を確認
   print(f"問題サイズ: {n_employees}人 × {n_days}日 × {n_shifts}シフト")
   print(f"決定変数数: {n_employees * n_days * n_shifts}")
   
   # 必要に応じて規模を縮小
   ```

3. **制約の簡素化**
   ```python
   # 複雑な制約を削減
   # 例: 細かい希望設定を削減、優先度設定の簡素化
   ```

### 🔍 デバッグ機能の活用

#### デバッグ情報の読み方
```python
result = engine.solve_schedule(...)

if 'debug_info' in result:
    for info in result['debug_info']:
        if info.startswith('✅'):
            print(f"成功: {info}")
        elif info.startswith('⚠️'):
            print(f"警告: {info}")
        elif info.startswith('❌'):
            print(f"エラー: {info}")
        elif info.startswith('📊'):
            print(f"統計: {info}")
```

#### カスタムデバッグ出力
```python
# engine内にデバッグモードを追加
class CompleteScheduleEngine:
    def __init__(self, location_manager, config_manager=None, debug=False):
        self.debug = debug
        # ...
    
    def debug_print(self, message):
        if self.debug:
            print(f"[DEBUG] {message}")

# 使用例
engine = CompleteScheduleEngine(location_manager, config_manager, debug=True)
```

---

## 🎯 まとめ

`CompleteScheduleEngine`は、実世界の複雑な勤務調整問題を解決する高度なシステムです。

### 主要な特徴

1. **数学的最適化**: OR-Toolsによる厳密解の探索
2. **制約緩和**: 4段階の段階的緩和による実用解の保証
3. **月またぎ対応**: 前月データを考慮した継続性制約
4. **Phase 1機能**: 従業員優先度による柔軟な調整
5. **豊富なデバッグ**: 詳細な制約分析とトラブルシューティング

### 技術的価値

- **制約プログラミング**の実践的応用例
- **段階的緩和**による現実的問題解決
- **大規模組み合わせ最適化**の効率的実装
- **日本の労働慣行**を考慮したドメイン知識の実装

このエンジンは、単なるスケジュール作成ツールを超えて、**制約プログラミングの教科書的実装**として、また**実用的な最適化システム**として、高い学習価値と実用価値を持っています。

---

*📝 このガイドは、CompleteScheduleEngine（schedule_gui_fixed.py：216-779行）の詳細分析に基づいて作成されており、制約プログラミングの実践的理解を深めることを目的としています。*
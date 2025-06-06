# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Japanese shift scheduling system (勤務表自動作成システム) designed for security guards or similar workers. The system generates optimized work schedules using constraint programming with Google OR-Tools, with features for multiple work locations, holiday management, and Excel output with color coding.

## Key Architecture

### Core Components

1. **Constraint Programming Engine** (`ScheduleEngine` class in `complete_schedule.py`)
   - Uses Google OR-Tools CP-SAT solver
   - Implements complex scheduling constraints (consecutive work limits, double shifts, holidays)
   - Supports weight-based penalty optimization for constraint relaxation

2. **Streamlit GUI** (`schedule_gui*.py` files)
   - Web-based interface for schedule configuration
   - Calendar selection for holidays/preferences
   - Real-time constraint violation handling
   - Excel file download functionality

3. **Excel Output System**
   - Color-coded schedule visualization using xlsxwriter
   - Multiple work location support with custom colors
   - Holiday and off-day highlighting

### Key Constraints Implemented

- **三徹禁止** (No triple consecutive shifts): Workers cannot work 3 days in a row
- **二徹制限** (Double shift limits): Maximum 2 double shifts per month per person
- **月またぎ制約** (Cross-month constraints): Handles schedule continuity across month boundaries
- **非番自動処理** (Automatic off-day assignment): Auto-assigns rest days after shifts
- **有休管理** (Holiday management): Respects requested vacation days

## Configuration Files

- `shift_config.json`: Defines shift types (16h duty, 8h day, 12h night shifts) with colors and constraints
- `work_locations.json`: Configures work locations (駅A, 指令, 警乗) with colors
- `requirements.txt` files in subdirectories contain Python dependencies

## Common Development Commands

### Running the Application
```bash
# Main Streamlit GUI
streamlit run schedule_gui.py
# or
streamlit run complete_schedule.py

# Alternative GUI version
streamlit run schedule_gui0604.py
```

### Dependencies
The system requires:
- `ortools` (Google OR-Tools for constraint programming)
- `streamlit` (Web GUI framework)
- `xlsxwriter` or `openpyxl` (Excel output)
- `pandas` (Data manipulation)

Install dependencies:
```bash
pip install ortools streamlit xlsxwriter openpyxl pandas
```

## File Organization

### Main Application Files
- `complete_schedule.py`: Full integrated system (engine + GUI + Excel export)
- `schedule_gui.py`: Main Streamlit GUI application
- `schedule_gui0604.py`: Alternative GUI version

### Specialized Schedulers
- `shift_schedule_a_group_final*.py`: Group A specific scheduling logic
- `shift_scheduler*.py`: Basic scheduling implementations
- `three_person_shift.py`: 3-person team scheduling
- Files in `勤務表作成の残骸/`: Legacy/experimental scheduling implementations

### Output Files
- `*.csv` files: Schedule outputs in CSV format
- `*.xlsx` files: Excel schedules with color coding
- `shift_2025_06.xlsx`: Example schedule output

## Key Development Notes

### Constraint Programming Approach
The system uses CP-SAT (Constraint Programming Satisfiability) rather than simple optimization. This allows for:
- Hard constraints that must be satisfied
- Soft constraints with penalty weights
- Automatic constraint relaxation when no solution exists

### Japanese Business Logic
- **一徹勤務**: 16-hour overnight duty shifts
- **二徹**: Double consecutive shifts (working 2 days in a row)
- **三徹**: Triple consecutive shifts (prohibited)
- **非番**: Mandatory rest day after duty
- **助勤**: Relief/support workers (used when constraints cannot be satisfied)

### Month Boundary Handling
The system handles complex month-crossing constraints, ensuring that:
- Previous month's final shifts affect current month's starting constraints
- Double shift counting works across month boundaries
- Rest day requirements are maintained between months

## Testing and Validation

The system includes built-in constraint validation and provides detailed feedback when constraints cannot be satisfied. Test with various scenarios:
- Different numbers of workers (3-person teams are common)
- Holiday-heavy months
- Uneven work preferences
- Cross-month boundary conditions
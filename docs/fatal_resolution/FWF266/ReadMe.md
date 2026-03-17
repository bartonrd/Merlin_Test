# Error Code: FWF266

## Summary
FWF266 indicates a fatal workflow failure caused by a missing Line Conductor Model definition in global.csv

## Root Causes
- Missing Line Conductor Model definition in global.csv

## Model Manager Converter Log Example(s)
-F-,FWF266,PH382E$4115222E,Line conductor model was not found in global data.,Record name: Line  Field name: CondModA,Station External Device: PH382E$4115222E,OH_653_A_2PH_653_A_N_2.4KV,,,,ALOLA,,PH382E$4115222E,ENG


## Allowed Resolution Strategy for FWF266

Merlin must follow these steps exactly and may not infer missing behavior.

### Data Source
- File: global.csv
- Format: RFC4180 CSV
- Delimiter: comma
- Header row present
- Columns are referenced by **column name**, not index

### Step 1: Filter by Model Type
Select all records from `global.csv` where:
- `Model_Type` == "Conductor_Model" (exact, case-sensitive match)

If zero records are found, terminate with no action.

---

### Step 2: Extract Base Conductor String
From the error log:
- Parse `Error_Column_7`
- Extract:
  - `base_conductor_string`: substring before the voltage suffix
  - `voltage_value_kv`: numeric voltage in kilovolts

Example:
- Input: `OH_653_A_2PH_653_A_N_2.4KV`
- base_conductor_string = `OH_653_A_2PH_653_A_N_`
- voltage_value_kv = `2.4`

If parsing fails, terminate with no action.

---

### Step 3: Match Conductor Group
From the Step 1 result set, retain records where:
- `Conductor_Group` starts with `base_conductor_string` (prefix match)

If zero records remain, terminate with no action.

---

### Step 4: Identify Closest Voltage
For remaining records:
- Parse voltage from `Conductor_Group`
- Convert all voltages to numeric kilovolts
- Compute absolute difference from `voltage_value_kv`

Select the single record with the smallest absolute difference.
- If tied, select the **higher voltage**

---

### Step 5: Propose New Record
Create a **proposed** new record with:
- All fields copied from the selected record
- `Conductor_ID` appended with lowercase `"a"`
- `Conductor_Group` updated to use `voltage_value_kv`

Do NOT write changes directly.
Return the proposed record in the action_payload.

Example Output:
```csv
Conductor_Model,1,COND_578a,OH_653_A_2PH_653_A_N_2.4KV,TRUE,0.001,0.001,,,,0.1,,,,,,,,,,,,,,,,A,653,1,0.032575805,0.11961053,0.086704627,0.547586002,0,0,2,Normal,1,920,Year Round,,TRUE,Emergency,1,1200,Year Round,,TRUE,,,,,,,,,,,,,,
```

## Disallowed Strategies
Merlin must NOT:
- Disable retries entirely
- Restart services continuously
- Lower validation or safety checks

## Action Payload Rules (FWF266)

Merlin must emit a valid Nodecraft `action_payload` using the fields below.

### Required Shape
```json
{
  "actions": [
    {
      "action": "propose_global_csv_insert",
      "global_csv_line_text": "string",
      "global_csv_line_number": 0
    }
  ],
  "confidence": 0,
  "notes": "string"
}
```

### Field Definitions
- **action**:
  - **Literal** value: `"propose_global_csv_insert"`.
- **global_csv_line_text** *(string)*:
  - The **entire CSV row** to insert (as text).
  - Must preserve column order and count used by existing `Conductor_Model` rows.
  - Only two field changes are permitted relative to the reference row:
    1) `Conductor_ID` is the reference `Conductor_ID` with a trailing `"a"`.
    2) `Conductor_Group` voltage suffix updated to the target voltage (e.g., `..._2.4KV`).
- **global_csv_line_number** *(integer)*:
  - **0‑based** line index at which the new row should be inserted.
  - **Line 0 is the header row.**
  - Must equal `reference_record_index + 1` (i.e., inserted immediately **after** the matched reference record).
- **confidence** *(number in [0.0, 1.0])*:
  - Merlin’s confidence that the proposed line is correct.
- **notes** *(string)*:
  - Brief rationale including the reference index and parsed voltages (e.g., `"closest match at index 766 (4KV); new suffix 2.4KV"`).

### Success Example
```json
{
  "actions": [
    {
      "action": "propose_global_csv_insert",
      "global_csv_line_text": "Conductor_Model,1,COND_578a,OH_653_A_2PH_653_A_N_2.4KV,TRUE,0.001,0.001,,,,0.1,,,,,,,,,,,,,,,,A,653,1,0.032575805,0.11961053,0.086704627,0.547586002,0,0,2,Normal,1,920,Year Round,,TRUE,Emergency,1,1200,Year Round,,TRUE,,,,,,,,,,,,,,",
      "global_csv_line_number": 767
    }
  ],
  "confidence": 0.92,
  "notes": "Closest reference at index 766 (4KV); updated Conductor_Group to 2.4KV; appended 'a' to Conductor_ID"
}
```

### No‑Action Conditions (emit `actions: []`)
Merlin must return **no actions** if any of the following occur:
- No `Conductor_Model` rows found.
- `Error_Column_7` voltage cannot be parsed.
- No `Conductor_Group` prefix match to the base conductor string.
- Ambiguous or malformed voltages prevent closest‑match selection.
- The generated `Conductor_ID` with `"a"` **already exists**.

#### No‑Action Example
```json
{
  "actions": [],
  "confidence": 0.0,
  "notes": "Terminated: Conductor_ID with 'a' already exists"
}
```

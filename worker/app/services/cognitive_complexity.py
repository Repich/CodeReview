from __future__ import annotations

from dataclasses import dataclass
import re

from worker.app.models import SourceUnit


PROC_START_RE = re.compile(r"^\s*(Процедура|Функция)\s+([A-Za-zА-Яа-я0-9_]+)", re.IGNORECASE)
PROC_END_RE = re.compile(r"^\s*Конец(Процедуры|Функции)\b", re.IGNORECASE)

PP_IF_RE = re.compile(r"^\s*#Если\b", re.IGNORECASE)
PP_ELSEIF_RE = re.compile(r"^\s*#ИначеЕсли\b", re.IGNORECASE)
PP_ELSE_RE = re.compile(r"^\s*#Иначе\b", re.IGNORECASE)
PP_ENDIF_RE = re.compile(r"^\s*#КонецЕсли\b", re.IGNORECASE)

IF_RE = re.compile(r"^\s*Если\b", re.IGNORECASE)
ELSEIF_RE = re.compile(r"^\s*ИначеЕсли\b", re.IGNORECASE)
ELSE_RE = re.compile(r"^\s*Иначе\b", re.IGNORECASE)
ENDIF_RE = re.compile(r"^\s*КонецЕсли\b", re.IGNORECASE)

LOOP_RE = re.compile(r"^\s*(Для\s+Каждого|Для|Пока)\b", re.IGNORECASE)
ENDLOOP_RE = re.compile(r"^\s*КонецЦикла\b", re.IGNORECASE)

SWITCH_RE = re.compile(r"^\s*Выбор\b", re.IGNORECASE)
ENDSWITCH_RE = re.compile(r"^\s*КонецВыбора\b", re.IGNORECASE)

TRY_RE = re.compile(r"^\s*Попытка\b", re.IGNORECASE)
EXCEPT_RE = re.compile(r"^\s*Исключение\b", re.IGNORECASE)
ENDTRY_RE = re.compile(r"^\s*КонецПопытки\b", re.IGNORECASE)

TERNARY_RE = re.compile(r"\?\s*\(")
LOGICAL_OP_RE = re.compile(r"\b(И|ИЛИ)\b", re.IGNORECASE)


@dataclass
class ProcedureComplexity:
    file_path: str
    name: str
    start_line: int
    end_line: int
    complexity: int
    loc: int
    avg_per_line: float


def compute_cognitive_complexity(sources: list[SourceUnit]) -> dict:
    procedures: list[ProcedureComplexity] = []
    total_complexity = 0
    total_loc = 0
    for source in sources:
        for proc in _extract_procedures(source):
            complexity, loc = _compute_for_procedure(proc)
            avg = round(complexity / loc, 6) if loc else 0.0
            procedures.append(
                ProcedureComplexity(
                    file_path=proc.file_path,
                    name=proc.name,
                    start_line=proc.start_line,
                    end_line=proc.end_line,
                    complexity=complexity,
                    loc=loc,
                    avg_per_line=avg,
                )
            )
            total_complexity += complexity
            total_loc += loc
    avg_total = round(total_complexity / total_loc, 6) if total_loc else 0.0
    return {
        "cognitive_complexity": {
            "total": total_complexity,
            "total_loc": total_loc,
            "avg_per_line": avg_total,
            "procedures": [
                {
                    "file_path": item.file_path,
                    "name": item.name,
                    "start_line": item.start_line,
                    "end_line": item.end_line,
                    "complexity": item.complexity,
                    "loc": item.loc,
                    "avg_per_line": item.avg_per_line,
                }
                for item in procedures
            ],
        }
    }


@dataclass
class _ProcedureBlock:
    file_path: str
    name: str
    start_line: int
    end_line: int
    lines: list[str]


def _extract_procedures(source: SourceUnit) -> list[_ProcedureBlock]:
    lines = source.content.splitlines()
    if not lines:
        return []
    blocks: list[_ProcedureBlock] = []
    current_name: str | None = None
    current_start = 0
    for idx, raw in enumerate(lines, start=1):
        start_match = PROC_START_RE.match(raw)
        end_match = PROC_END_RE.match(raw)
        if start_match and current_name is None:
            current_name = start_match.group(2)
            current_start = idx
            continue
        if start_match and current_name is not None:
            blocks.append(
                _ProcedureBlock(
                    file_path=source.path,
                    name=current_name,
                    start_line=current_start,
                    end_line=idx - 1,
                    lines=lines[current_start - 1 : idx - 1],
                )
            )
            current_name = start_match.group(2)
            current_start = idx
            continue
        if end_match and current_name is not None:
            blocks.append(
                _ProcedureBlock(
                    file_path=source.path,
                    name=current_name,
                    start_line=current_start,
                    end_line=idx,
                    lines=lines[current_start - 1 : idx],
                )
            )
            current_name = None
            current_start = 0
    if current_name is not None:
        blocks.append(
            _ProcedureBlock(
                file_path=source.path,
                name=current_name,
                start_line=current_start,
                end_line=len(lines),
                lines=lines[current_start - 1 :],
            )
        )
    return blocks


def _compute_for_procedure(proc: _ProcedureBlock) -> tuple[int, int]:
    cleaned_lines = _strip_comments_and_strings(proc.lines)
    nesting = 0
    complexity = 0
    stack: list[str] = []
    loc = 0
    proc_name = proc.name.lower()
    recursion_counted = False

    for raw_line in cleaned_lines:
        line = raw_line.strip()
        if line:
            loc += 1

        if PP_ENDIF_RE.match(line):
            if stack and stack[-1] == "pp_if":
                stack.pop()
                nesting = max(0, nesting - 1)
            continue
        if ENDIF_RE.match(line):
            if stack and stack[-1] == "if":
                stack.pop()
                nesting = max(0, nesting - 1)
            continue
        if ENDLOOP_RE.match(line):
            if stack and stack[-1] == "loop":
                stack.pop()
                nesting = max(0, nesting - 1)
            continue
        if ENDSWITCH_RE.match(line):
            if stack and stack[-1] == "switch":
                stack.pop()
                nesting = max(0, nesting - 1)
            continue
        if ENDTRY_RE.match(line):
            if stack and stack[-1] == "except":
                stack.pop()
                nesting = max(0, nesting - 1)
            continue

        if PP_ELSEIF_RE.match(line):
            if stack and stack[-1] == "pp_if":
                complexity += 1
        if PP_ELSE_RE.match(line):
            if stack and stack[-1] == "pp_if":
                complexity += 1
        if ELSEIF_RE.match(line):
            if stack and stack[-1] == "if":
                complexity += 1
        if ELSE_RE.match(line):
            if stack and stack[-1] == "if":
                complexity += 1

        if EXCEPT_RE.match(line):
            complexity += 1 + nesting
            stack.append("except")
            nesting += 1
            continue
        if IF_RE.match(line):
            complexity += 1 + nesting
            stack.append("if")
            nesting += 1
        elif PP_IF_RE.match(line):
            complexity += 1 + nesting
            stack.append("pp_if")
            nesting += 1
        elif LOOP_RE.match(line):
            complexity += 1 + nesting
            stack.append("loop")
            nesting += 1
        elif SWITCH_RE.match(line):
            complexity += 1 + nesting
            stack.append("switch")
            nesting += 1
        elif TRY_RE.match(line):
            pass

        if line:
            complexity += _count_ternary(line, nesting)
            complexity += _count_logical_sequences(line)

        if not recursion_counted and proc_name and _has_direct_recursion(line, proc_name):
            complexity += 1
            recursion_counted = True

    return complexity, loc


def _count_ternary(line: str, nesting: int) -> int:
    hits = len(TERNARY_RE.findall(line))
    if hits == 0:
        return 0
    return hits * (1 + nesting)


def _count_logical_sequences(line: str) -> int:
    tokens = [match.group(1).upper() for match in LOGICAL_OP_RE.finditer(line)]
    if not tokens:
        return 0
    sequences = 1
    for idx in range(1, len(tokens)):
        if tokens[idx] != tokens[idx - 1]:
            sequences += 1
    return sequences


def _has_direct_recursion(line: str, proc_name: str) -> bool:
    if not line or not proc_name:
        return False
    if PROC_START_RE.match(line):
        return False
    pattern = rf"\b{re.escape(proc_name)}\s*\("
    return re.search(pattern, line, re.IGNORECASE) is not None


def _strip_comments_and_strings(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    in_block_comment = False
    for raw in lines:
        result_chars: list[str] = []
        i = 0
        in_string = False
        while i < len(raw):
            ch = raw[i]
            if in_block_comment:
                if ch == "*" and i + 1 < len(raw) and raw[i + 1] == "/":
                    in_block_comment = False
                    i += 2
                    continue
                i += 1
                continue
            if in_string:
                if ch == '"' and i + 1 < len(raw) and raw[i + 1] == '"':
                    i += 2
                    continue
                if ch == '"':
                    in_string = False
                    i += 1
                    continue
                i += 1
                continue
            if ch == "/" and i + 1 < len(raw) and raw[i + 1] == "/":
                break
            if ch == "/" and i + 1 < len(raw) and raw[i + 1] == "*":
                in_block_comment = True
                i += 2
                continue
            if ch == '"':
                in_string = True
                result_chars.append(" ")
                i += 1
                continue
            result_chars.append(ch)
            i += 1
        cleaned.append("".join(result_chars))
    return cleaned

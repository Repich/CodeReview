from __future__ import annotations

import re
from typing import Iterable

from worker.app.detectors.base import BaseDetector, DetectorContext
from worker.app.detectors.registry import register
from worker.app.models import DetectorFinding
from worker.app.services.query_units import extract_query_units


@register
class SessionParamsClientDetector(BaseDetector):
    norm_id = "SESSION_PARAMS_NOT_FOR_CLIENT_LOGIC"
    detector_id = "detector.session_params_client"
    severity = "major"

    directive_pattern = re.compile(r"&\s*([А-Яа-яA-Za-z]+)")

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        client_context = False
        for line_no, line in self.iter_lines(ctx.source.content):
            stripped = line.strip()
            if stripped.startswith("&"):
                client_context = "НаКлиенте" in stripped and "НаСервере" not in stripped
                continue
            if "ПараметрыСеанса" in line and client_context:
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Параметры сеанса читаются в клиентской процедуре",
                        recommendation="Перенесите работу с параметрами сеанса в серверный код или используйте кэш в форме.",
                        line=line_no,
                        extra={"line": line.strip()},
                    )
                )
        return findings


def _is_form_module(ctx: DetectorContext) -> bool:
    module_type = (ctx.source.module_type or "").lower()
    path_lower = (ctx.source.path or "").lower()
    return "form" in module_type or "/forms/" in path_lower or path_lower.endswith("formmodule.bsl")


@register
class FormServerContextWithoutUsageDetector(BaseDetector):
    norm_id = "FORM_SERVER_CONTEXT_NO_USAGE"
    detector_id = "detector.form_server_context_no_usage"
    severity = "minor"

    directive_server = re.compile(r"&\s*НаСервере\b", re.IGNORECASE)
    directive_no_context = re.compile(r"&\s*НаСервереБезКонтекста\b", re.IGNORECASE)
    proc_re = re.compile(r"^\s*(Процедура|Функция)\b", re.IGNORECASE)
    end_proc_re = re.compile(r"^\s*КонецПроцедуры\b", re.IGNORECASE)
    end_func_re = re.compile(r"^\s*КонецФункции\b", re.IGNORECASE)
    context_re = re.compile(r"\b(Объект|ЭтаФорма|ЭтотОбъект)\s*\.", re.IGNORECASE)

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        if not _is_form_module(ctx):
            return []
        findings: list[DetectorFinding] = []
        pending_directive_line: int | None = None
        in_block = False
        has_context = False
        directive_line: int | None = None
        end_re: re.Pattern[str] | None = None

        for line_no, line in self.iter_lines(ctx.source.content):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("//"):
                continue
            if stripped.startswith("&"):
                if self.directive_server.search(stripped) and not self.directive_no_context.search(stripped):
                    pending_directive_line = line_no
                else:
                    pending_directive_line = None
                continue
            if self.proc_re.match(stripped):
                if pending_directive_line is not None:
                    in_block = True
                    has_context = False
                    directive_line = pending_directive_line
                    pending_directive_line = None
                    end_re = self.end_func_re if stripped.lower().startswith("функция") else self.end_proc_re
                else:
                    in_block = False
                    directive_line = None
                    end_re = None
                continue

            if not in_block:
                continue

            if self.context_re.search(line):
                has_context = True

            if end_re and end_re.match(stripped):
                if not has_context:
                    findings.append(
                        self.create_finding(
                            ctx,
                            message="Вызов обработки клиентского контекста на сервере без необходимости",
                            recommendation="Замените директиву на &НаСервереБезКонтекста, если форма и объект не используются.",
                            line=directive_line or line_no,
                            extra={"directive_line": directive_line, "procedure_end": line_no},
                        )
                    )
                in_block = False
                has_context = False
                directive_line = None
                end_re = None
        return findings


@register
class MetadataReservedWordsDetector(BaseDetector):
    norm_id = "NAME_NO_QUERY_TABLE_WORDS"
    detector_id = "detector.metadata_reserved_words"
    severity = "major"

    reserved = {
        "select",
        "from",
        "where",
        "union",
        "join",
        "вибрать",
        "выбрать",
        "из",
        "где",
    }

    splitter = re.compile(r"[\\/._]")

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        parts = [p.lower() for p in self.splitter.split(ctx.source.path) if p]
        offending = sorted(self.reserved.intersection(parts))
        if not offending:
            return []
        return [
            self.create_finding(
                ctx,
                message="Имя объекта конфликтует с ключевыми словами языка запросов",
                recommendation="Переименуйте объект, чтобы имя не совпадало с SELECT/FROM/WHERE и т.п.",
                line=1,
                extra={"path": ctx.source.path, "offending": offending},
            )
        ]


@register
class QueryUppercaseKeywordsDetector(BaseDetector):
    norm_id = "QUERY_KEYWORDS_UPPER"
    detector_id = "detector.query_upper_keywords"
    severity = "minor"

    keyword_pattern = re.compile(r"\b(выбрать|из|где|объединить|соединение)\b", re.IGNORECASE)
    query_inline_pattern = re.compile(
        r"\b(запрос\.текст|текстзапроса)\s*=|запрос\s*=\s*новый\s+запрос\s*\(",
        re.IGNORECASE,
    )

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        for line_no, line in self.iter_lines(ctx.source.content):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            if not self._is_query_line(stripped):
                continue
            for match in self.keyword_pattern.finditer(line):
                token = match.group(0)
                if token.upper() != token:
                    findings.append(
                        self.create_finding(
                            ctx,
                            message=f"Ключевое слово запроса '{token}' должно быть заглавными буквами",
                            recommendation="Используйте заглавные буквы для ключевых слов языка запросов (ВЫБРАТЬ, ИЗ, ГДЕ...).",
                            line=line_no,
                            extra={"keyword": token},
                        )
                )
                    break
        return findings

    def _is_query_line(self, stripped: str) -> bool:
        if stripped.startswith("|"):
            return True
        if '"' not in stripped:
            return False
        return bool(self.query_inline_pattern.search(stripped))


@register
class FormElementNamingDetector(BaseDetector):
    norm_id = "FORM_LAYOUT_05"
    detector_id = "detector.form_element_naming"
    severity = "minor"

    element_pattern = re.compile(r'Элементы\.(?:Добавить|Найти)\s*\(\s*"([^"]+)"')
    bad_name_pattern = re.compile(r"\d+$")

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        for line_no, line in self.iter_lines(ctx.source.content):
            for match in self.element_pattern.finditer(line):
                name = match.group(1)
                if self.bad_name_pattern.search(name):
                    findings.append(
                        self.create_finding(
                            ctx,
                            message=f'Имя элемента формы "{name}" содержит числовой суффикс',
                            recommendation="Используйте единообразные имена элементов без добавления индексов (например, \"Контрагент\").",
                            line=line_no,
                            extra={"element": name},
                        )
                    )
        return findings


@register
class FormDirectDataWriteDetector(BaseDetector):
    norm_id = "FORM_NO_DIRECT_METADATA_WRITE"
    detector_id = "detector.form_direct_write"
    severity = "major"

    creation_pattern = re.compile(
        r"(Справочники|Документы|Регистры[А-Яа-яA-Za-z]*|ПланыВидовХарактеристик|ПланыСчетов)"
        r"\.[\wА-Яа-яЁё]+\.(СоздатьЭлемент|СоздатьДокумент|СоздатьОбъект|СоздатьНаборЗаписей)",
        re.UNICODE,
    )
    write_pattern = re.compile(
        r"(Справочники|Документы|Регистры[А-Яа-яA-Za-z]*|ПланыВидовХарактеристик|ПланыСчетов)"
        r"\.[\wА-Яа-яЁё]+\.[\wА-Яа-яЁё]*Записать",
        re.UNICODE,
    )

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        if not _is_form_module(ctx):
            return []
        findings: list[DetectorFinding] = []
        for line_no, line in self.iter_lines(ctx.source.content):
            if self.creation_pattern.search(line) or self.write_pattern.search(line):
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Модуль формы напрямую создает или записывает объект метаданных",
                        recommendation="Вынесите создание/запись объектов в общий модуль или сервис, а форма должна только вызывать его.",
                        line=line_no,
                        extra={"line": line.strip()},
                    )
                )
        return findings


@register
class DocumentSaveModeDetector(BaseDetector):
    norm_id = "DOC_SAVE_IN_POST_MODE"
    detector_id = "detector.document_save_mode"
    severity = "major"

    save_pattern = re.compile(r"Записать\s*\((.*?)\)", re.IGNORECASE)

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        module_type = ctx.source.module_type or ""
        if "Documents/" not in ctx.source.path and not module_type.lower().startswith("document"):
            return []
        findings: list[DetectorFinding] = []
        content = ctx.source.content
        for match in self.save_pattern.finditer(content):
            args = match.group(1).strip()
            if not args or "РежимЗаписиДокумента.Проведение" not in args:
                line_no = content[: match.start()].count("\n") + 1
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Запись документа выполняется без режима проведения",
                        recommendation="Документы, требующие отражения в учете, следует записывать с параметром РежимЗаписиДокумента.Проведение.",
                        line=line_no,
                        extra={"call": f"Записать({args})"},
                    )
                )
        return findings


@register
class QueryExplicitAliasesDetector(BaseDetector):
    norm_id = "QUERY_EXPLICIT_ALIASES"
    detector_id = "detector.query_aliases"
    severity = "minor"
    alias_pattern = re.compile(r"(?:^|\s)(КАК|AS)(?=\s)", re.IGNORECASE)
    case_start_pattern = re.compile(r"\bВЫБОР\b", re.IGNORECASE)
    case_end_pattern = re.compile(r"\bКОНЕЦ\b", re.IGNORECASE)
    union_prefix = "ОБЪЕДИНИТЬ"

    header_prefixes = (
        "ВЫБРАТЬ",
        "ИЗ",
        "ГДЕ",
        "СГРУППИРОВАТЬ",
        "УПОРЯДОЧИТЬ",
        "ИТОГИ",
        "ЛЕВОЕ",
        "ПРАВОЕ",
        "ПОЛНОЕ",
        "ВНУТРЕННЕЕ",
        "ОБЪЕДИНИТЬ",
        "ПО",
    )

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        def _strip_inline_comment(value: str) -> str:
            if "//" in value:
                return value.split("//", 1)[0].rstrip()
            return value

        def _line_ends_select_item(value: str) -> bool:
            trimmed = _strip_inline_comment(value).rstrip()
            return trimmed.endswith(",")

        findings: list[DetectorFinding] = []
        in_select = False
        alias_required = True
        skip_alias_for_next_select = False
        case_depth = 0
        case_has_alias = False
        case_has_dot = False
        case_start_line: int | None = None
        case_start_expr: str | None = None
        pending_expr: list[str] = []
        pending_line: int | None = None
        pending_has_dot = False
        pending_has_alias = False

        def flush_pending() -> None:
            nonlocal pending_expr, pending_line, pending_has_dot, pending_has_alias
            if pending_expr and pending_has_dot and not pending_has_alias:
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Поле запроса без псевдонима",
                        recommendation="Добавьте оператор КАК/AS, чтобы явно задать псевдоним для поля.",
                        line=pending_line or 1,
                        extra={"expression": " ".join(pending_expr).strip()},
                    )
                )
            pending_expr = []
            pending_line = None
            pending_has_dot = False
            pending_has_alias = False

        for line_no, line in self.iter_lines(ctx.source.content):
            stripped = line.strip()
            if not stripped.startswith("|"):
                continue
            expr = stripped.lstrip("|").strip()
            if not expr:
                continue
            normalized_expr = " ".join(expr.split())
            expr_upper = normalized_expr.upper()

            if expr_upper.startswith(";"):
                flush_pending()
                in_select = False
                alias_required = True
                skip_alias_for_next_select = False
                case_depth = 0
                case_has_alias = False
                case_has_dot = False
                case_start_line = None
                case_start_expr = None
                continue

            if expr_upper.startswith(self.union_prefix):
                flush_pending()
                skip_alias_for_next_select = True
                if in_select:
                    in_select = False
                case_depth = 0
                case_has_alias = False
                case_has_dot = False
                case_start_line = None
                case_start_expr = None
                continue

            expr_to_check: str | None = None
            if expr_upper.startswith("ВЫБРАТЬ"):
                flush_pending()
                in_select = True
                alias_required = not skip_alias_for_next_select
                skip_alias_for_next_select = False
                remainder = normalized_expr[len("ВЫБРАТЬ") :].strip()
                if remainder:
                    expr_to_check = remainder
            elif expr_upper.startswith(self.header_prefixes):
                if in_select:
                    flush_pending()
                    in_select = False
                    alias_required = True
                case_depth = 0
                case_has_alias = False
                case_has_dot = False
                case_start_line = None
                case_start_expr = None
                continue
            else:
                if not in_select:
                    continue
                expr_to_check = normalized_expr

            if not alias_required:
                flush_pending()
                continue

            if expr_to_check:
                if self.case_start_pattern.search(expr_to_check):
                    if case_depth == 0:
                        case_start_line = line_no
                        case_start_expr = expr_to_check
                    case_depth += 1

                if case_depth > 0:
                    if "." in expr_to_check:
                        case_has_dot = True
                    if self.alias_pattern.search(expr_to_check):
                        case_has_alias = True
                    if self.case_end_pattern.search(expr_to_check):
                        case_depth = max(case_depth - 1, 0)
                        if case_depth == 0:
                            if case_has_dot and not case_has_alias:
                                findings.append(
                                    self.create_finding(
                                        ctx,
                                        message="Поле запроса без псевдонима",
                                        recommendation="Добавьте оператор КАК/AS, чтобы явно задать псевдоним для поля.",
                                        line=case_start_line or line_no,
                                        extra={"expression": case_start_expr or expr},
                                    )
                                )
                            case_has_alias = False
                            case_has_dot = False
                            case_start_line = None
                            case_start_expr = None
                    continue

            if expr_to_check:
                if not pending_expr:
                    pending_line = line_no
                pending_expr.append(expr)
                if "." in expr_to_check:
                    pending_has_dot = True
                if self.alias_pattern.search(expr_to_check):
                    pending_has_alias = True
                if _line_ends_select_item(expr):
                    flush_pending()
        flush_pending()
        return findings


@register
class QueryCommentPatchingDetector(BaseDetector):
    norm_id = "QUERY_NO_COMMENT_PATCHING"
    detector_id = "detector.query_comment_patching"
    severity = "major"

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        for line_no, line in self.iter_lines(ctx.source.content):
            if "/*" not in line:
                continue
            if "СтрЗаменить" in line or "+" in line or "&" in line:
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Используются комментарии для модификации текста запроса",
                        recommendation="Формируйте текст запроса без патчинга через комментарии, задавайте условия явным кодом.",
                        line=line_no,
                        extra={"line": line.strip()},
                    )
                )
        return findings


@register
class LineLengthDetector(BaseDetector):
    norm_id = "TEXT_MAX_LINE_LENGTH"
    detector_id = "detector.line_length"
    severity = "minor"

    max_length = 150

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        query_lines: set[int] = set()
        for unit in extract_query_units(ctx.source):
            query_lines.update(line_no for line_no, _ in unit.line_map)
        for line_no, line in self.iter_lines(ctx.source.content):
            if line_no in query_lines:
                continue
            if len(line.rstrip("\n")) > self.max_length:
                findings.append(
                    self.create_finding(
                        ctx,
                        message=f"Длина строки превышает {self.max_length} символов",
                        recommendation="Разбейте выражение на несколько строк для повышения читаемости.",
                        line=line_no,
                        extra={"length": len(line.rstrip("\n"))},
                    )
                )
        return findings


@register
class QueryMultilineDetector(BaseDetector):
    norm_id = "QUERY_MULTILINE"
    detector_id = "detector.query_multiline"
    severity = "minor"

    inline_assign_pattern = re.compile(r'Запрос\.Текст\s*=\s*"([^"\n]*)"', re.IGNORECASE)
    inline_new_query_pattern = re.compile(r'Новый\s+Запрос\s*\(\s*"([^"\n]*)"\s*\)', re.IGNORECASE)

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        content = ctx.source.content
        for match in list(self.inline_assign_pattern.finditer(content)) + list(
            self.inline_new_query_pattern.finditer(content)
        ):
            text = match.group(1)
            if not text.strip():
                continue
            line_no = content[: match.start()].count("\n") + 1
            findings.append(
                self.create_finding(
                    ctx,
                    message="Текст запроса записан в одну строку",
                    recommendation="Добавьте переводы строк и оформите запрос с отступами.",
                    line=line_no,
                    extra={"query": text[:60]},
                )
            )
        return findings


@register
class SessionParamsCacheDetector(BaseDetector):
    norm_id = "SESSION_PARAMS_NOT_CACHE"
    detector_id = "detector.session_params_cache"
    severity = "major"

    assign_pattern = re.compile(r"ПараметрыСеанса\.[\wА-Яа-яЁё]+\s*=", re.UNICODE)

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        for line_no, line in self.iter_lines(ctx.source.content):
            if self.assign_pattern.search(line):
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Параметры сеанса используются как хранилище данных",
                        recommendation="Не используйте ПараметрыСеанса для кеширования; храните данные в отдельных механизмах.",
                        line=line_no,
                        extra={"line": line.strip()},
                    )
                )
        return findings


@register
class QuerySelectStarDetector(BaseDetector):
    norm_id = "QUERY_GENERAL_01"
    detector_id = "detector.query_select_star"
    severity = "major"

    star_pattern = re.compile(r"ВЫБРАТЬ\s+\*", re.IGNORECASE)

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        for line_no, line in self.iter_lines(ctx.source.content):
            if self.star_pattern.search(line):
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Используется ВЫБРАТЬ * в тексте запроса",
                        recommendation="Выбирайте только необходимые поля вместо ВЫБРАТЬ *.",
                        line=line_no,
                        extra={"line": line.strip()},
                    )
                )
        return findings


def _line_starts_loop(text: str) -> bool:
    stripped = text.strip().lower()
    return ("для" in stripped or "пока" in stripped) and stripped.endswith("цикл")


@register
class QueryInsideLoopDetector(BaseDetector):
    norm_id = "QUERY_GENERAL_02"
    detector_id = "detector.query_inside_loop"
    severity = "major"
    query_pattern = re.compile(r"\bновый\s+запрос\b|запрос\.(?:выполн|текст)", re.IGNORECASE)

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        loop_depth = 0
        for line_no, line in self.iter_lines(ctx.source.content):
            stripped_lower = line.strip().lower()
            if _line_starts_loop(line):
                loop_depth += 1
            elif stripped_lower.startswith("конеццикла") and loop_depth > 0:
                loop_depth -= 1
            if loop_depth <= 0:
                continue
            lowered = line.lower()
            if self.query_pattern.search(lowered):
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Создание или выполнение запроса внутри цикла",
                        recommendation="Подготовьте запрос и данные вне цикла, чтобы минимизировать количество обращений к СУБД.",
                        line=line_no,
                        extra={"line": line.strip()},
                    )
                )
        return findings


@register
class VirtualTableParamsDetector(BaseDetector):
    norm_id = "STD_657"
    detector_id = "detector.virtual_table_params"
    severity = "major"

    virtual_table_pattern = re.compile(
        r"(РегистрНакопления|РегистрСведений)\.[\\wА-Яа-яЁё]+\\."
        r"(Остатки|Обороты|ОстаткиИОбороты|СрезПоследних|СрезПервых)"
        r"\\s*\\(([^)]*)\\)\\s*(?:КАК\\s+([\\wА-Яа-яЁё]+))?",
        re.IGNORECASE,
    )
    condition_prefix = re.compile(r"^(ГДЕ|ПО|И|ИЛИ)\\b", re.IGNORECASE)

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        aliases_without_params: dict[str, int] = {}
        reported_aliases: set[str] = set()

        for line_no, line in self.iter_lines(ctx.source.content):
            stripped = line.strip()
            if not stripped.startswith("|"):
                continue
            expr = stripped.lstrip("|").strip()
            if not expr:
                continue

            expr_upper = expr.upper()
            if expr_upper.startswith(";"):
                aliases_without_params.clear()
                reported_aliases.clear()
                continue

            match = self.virtual_table_pattern.search(expr)
            if match:
                params = (match.group(3) or "").strip().strip(",")
                alias = match.group(4)
                if alias and not params:
                    aliases_without_params[alias] = line_no

            if not aliases_without_params or not self.condition_prefix.match(expr):
                continue

            for alias in list(aliases_without_params.keys()):
                if alias in reported_aliases:
                    continue
                if re.search(rf"\\b{re.escape(alias)}\\.", expr):
                    findings.append(
                        self.create_finding(
                            ctx,
                            message="Условия виртуальной таблицы заданы вне параметров",
                            recommendation=(
                                "Передавайте условия для виртуальной таблицы в ее параметры, "
                                "а не в секции ГДЕ/ПО, чтобы улучшить план выполнения."
                            ),
                            line=line_no,
                            extra={"line": expr, "virtual_table": alias},
                        )
                    )
                    reported_aliases.add(alias)
        return findings


@register
class TodoCommentDetector(BaseDetector):
    norm_id = "COMMENT_NO_TODO_MARKERS"
    detector_id = "detector.todo_comment"
    severity = "minor"

    pattern = re.compile(r"//\s*(?:todo|fixme|xxx|hack|временно|уточнить|\?\?\?)", re.IGNORECASE)

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        for line_no, line in self.iter_lines(ctx.source.content):
            if self.pattern.search(line):
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Найден служебный комментарий TODO/FIXME/Уточнить",
                        recommendation="Удалите служебный комментарий или заведите задачу в трекере — в коде они не допускаются.",
                        line=line_no,
                        extra={"line": line.strip()},
                    )
                )
        return findings

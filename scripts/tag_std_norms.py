#!/usr/bin/env python3
"""Add categories/tags/automation hints to STD_* norms and build summary."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Dict, List, Tuple

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

ROOT = Path(__file__).resolve().parents[1]
NORMS_PATH = ROOT / "norms.yaml"
SUMMARY_PATH = ROOT / "docs" / "norms_audit" / "tagging_summary.md"

RAW_CATEGORY_RULES: Dict[str, Dict] = {
    "code_style": {
        "patterns": [
            r"текст(ы)? модул",
            r"строк",
            r"отступ",
            r"комментар",
            r"функци",
            r"процедур",
        ],
        "tags": ["code-style"],
        "default_hint": "code",
    },
    "messages_notifications": {
        "patterns": [
            r"сообщен",
            r"предупрежден",
            r"уведомлен",
            r"подсказ",
            r"информационн",
            r"msg",
        ],
        "tags": ["messages"],
        "default_hint": "mixed",
    },
    "queries_performance": {
        "patterns": [
            r"\bзапрос",
            r"СКД",
            r"виртуальн(ая|ые) таблиц",
            r"соединен",
            r"индекс",
            r"услови[яе] запроса",
            r"псевдоним",
            r"остатк[иа]",
        ],
        "tags": ["queries"],
        "default_hint": "code",
    },
    "data_model_registers": {
        "patterns": [
            r"регистр",
            r"констант",
            r"предопределенн",
            r"табличн(ая|ые) част",
            r"справочн",
            r"реквизит",
            r"план(ы)? вид",
        ],
        "tags": ["data-model"],
        "default_hint": "code",
    },
    "ui_forms_behavior": {
        "patterns": [
            r"элемент форм",
            r"табличн(ое|ые) поле",
            r"табличн(ая|ые) част",
            r"кнопк",
            r"форм",
            r"поля ввода",
            r"командн(ая|ые) панел",
        ],
        "tags": ["ui", "forms"],
        "default_hint": "mixed",
    },
    "ui_navigation": {
        "patterns": [
            r"навигац",
            r"\bпанел[ья] раздел",
            r"панель функц",
            r"командн(ый|ая) интерфейс",
            r"\bменю",
        ],
        "tags": ["ui"],
        "default_hint": "mixed",
    },
    "reporting_printing": {
        "patterns": [
            r"отчет",
            r"печатн",
            r"макет",
            r"табличн(ый|ого) документ",
            r"компонова",
        ],
        "tags": ["reports"],
        "default_hint": "mixed",
    },
    "transactions_locks": {
        "patterns": [
            r"транзак",
            r"блокиров",
            r"зафиксироватьтранзакцию",
            r"начатьтранзакцию",
            r"управляемый режим блокиров",
        ],
        "tags": ["transactions"],
        "default_hint": "code",
    },
    "background_jobs": {
        "patterns": [r"регламентн", r"фонов", r"расписан", r"планов(ые|ое)", r"очеред[ьи] задан"],
        "tags": ["reg-tasks"],
        "default_hint": "code",
    },
    "security_access": {
        "patterns": [
            r"\bрол[ьяеи]",
            r"доступ",
            r"rls",
            r"безопас",
            r"привилег",
            r"авторизац",
            r"аутентифика",
        ],
        "tags": ["security"],
        "default_hint": "code",
    },
    "localization": {
        "patterns": [
            r"локализа",
            r"язык",
            r"перевод",
            r"форматирован",
            r"валют",
            r"интерфейсн(ые|ых) текст",
        ],
        "tags": ["localization"],
        "default_hint": "mixed",
    },
    "integration_exchange": {
        "patterns": [
            r"обмен дан",
            r"интеграц",
            r"enterprise",
            r"выгруз",
            r"загруз",
            r"wsdl",
            r"web.?сервис",
            r"классифик",
        ],
        "tags": ["integration"],
        "default_hint": "mixed",
    },
    "metadata_design": {
        "patterns": [
            r"метадан",
            r"функциональн(ые|ая) опц",
            r"подсистем",
            r"библиотек",
            r"иерарх",
            r"архитектур",
        ],
        "tags": ["metadata"],
        "default_hint": "mixed",
    },
    "performance_runtime": {
        "patterns": [
            r"длительн",
            r"производительн",
            r"оптимизац",
            r"быстродейств",
            r"кэш",
            r"асинхрон",
        ],
        "tags": ["performance"],
        "default_hint": "code",
    },
    "devops_install": {
        "patterns": [
            r"установк",
            r"обновлен",
            r"разверт",
            r"инсталляц",
            r"лиценз",
            r"администрир",
        ],
        "tags": ["devops"],
        "default_hint": "process",
    },
}

RULE_ORDER = [
    "code_style",
    "queries_performance",
    "data_model_registers",
    "ui_forms_behavior",
    "ui_navigation",
    "reporting_printing",
    "transactions_locks",
    "background_jobs",
    "security_access",
    "localization",
    "integration_exchange",
    "metadata_design",
    "performance_runtime",
    "devops_install",
    "messages_notifications",
]

FALLBACK_CATEGORY = {
    "id": "governance_release",
    "tags": ["governance", "needs-manual-review"],
    "default_hint": "mixed",
}

SCOPE_TAGS: List[Tuple[str, str]] = [
    ("управляемое приложение", "scope:управляемое"),
    ("обычное приложение", "scope:обычное"),
    ("мобильное приложение", "scope:мобильное"),
    ("тонкий клиент", "scope:тонкий"),
    ("толстый клиент", "scope:толстый"),
    ("веб-клиент", "scope:веб"),
]

ADVISORY_PATTERNS = ["методическая рекомендация", "рекомендуется", "полезный совет"]

SECTION_CATEGORY = {
    "Тексты модулей": "code_style",
    "Сообщения пользователю": "messages_notifications",
    "Оформление текстов запросов": "queries_performance",
    "Запросы": "queries_performance",
    "Запросы и SQL": "queries_performance",
    "Транзакции": "transactions_locks",
    "Права доступа": "security_access",
    "Настройка ролей и прав доступа": "security_access",
    "Стандартные роли": "security_access",
    "Функциональные опции": "metadata_design",
    "Общие требования к конфигурации": "metadata_design",
    "Формы и интерфейс": "ui_forms_behavior",
    "Командный интерфейс": "ui_navigation",
    "Сообщения": "messages_notifications",
}


def ensure_key(container: CommentedMap, key: str, value, after_key: str | None = None) -> None:
    if key in container:
        container[key] = value
        return
    if after_key is None or after_key not in container:
        container[key] = value
        return
    keys = list(container.keys())
    idx = keys.index(after_key) + 1
    container.insert(idx, key, value)


def build_category_rules() -> tuple[List[Dict], dict[str, Dict]]:
    compiled = []
    lookup: dict[str, Dict] = {}
    for rule_id in RULE_ORDER:
        rule = RAW_CATEGORY_RULES[rule_id]
        rule_copy = dict(rule)
        rule_copy["id"] = rule_id
        rule_copy["patterns"] = [re.compile(pattern, re.IGNORECASE) for pattern in rule["patterns"]]
        compiled.append(rule_copy)
        lookup[rule_id] = rule_copy
    return compiled, lookup


CATEGORY_RULES, CATEGORY_LOOKUP = build_category_rules()


def pick_category(text: str) -> Dict:
    best_rule = FALLBACK_CATEGORY
    best_score = 0
    for rule in CATEGORY_RULES:
        score = sum(1 for pattern in rule["patterns"] if pattern.search(text))
        if score > best_score:
            best_rule = rule
            best_score = score
    return best_rule


def detect_scope_tags(text_lower: str) -> List[str]:
    matched = [tag for phrase, tag in SCOPE_TAGS if phrase in text_lower]
    if len(matched) == 1:
        return matched
    return []


def detect_advisory(text_lower: str) -> bool:
    return any(pattern in text_lower for pattern in ADVISORY_PATTERNS)


def main() -> None:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 120
    data = yaml.load(NORMS_PATH.read_text(encoding="utf-8"))
    records = data.get("norms") if isinstance(data, CommentedMap) else data
    if not isinstance(records, list):
        raise RuntimeError("norms.yaml должен содержать список норм")

    category_counter: Counter[str] = Counter()
    hint_counter: Counter[str] = Counter()
    process_norms: List[Tuple[str, str]] = []

    for entry in records:
        if not isinstance(entry, CommentedMap):
            continue
        if entry.get("category"):
            continue
        norm_id = entry.get("norm_id")
        if not norm_id:
            continue
        title = entry.get("title", "") or ""
        norm_text = entry.get("norm_text", "") or ""
        combined = f"{title}\n{norm_text}".lower()
        rule: Dict | None = None
        section = entry.get("section")
        if section in SECTION_CATEGORY:
            rule = CATEGORY_LOOKUP.get(SECTION_CATEGORY[section])
        if not rule:
            rule = pick_category(combined)

        ensure_key(entry, "category", rule["id"], after_key="section")

        tags = set(entry.get("tags") or [])
        tags.update(rule["tags"])
        tags.update(detect_scope_tags(combined))
        if detect_advisory(combined):
            tags.add("advisory")

        automation_hint = rule.get("default_hint", "code")
        if automation_hint == "process":
            tags.add("process-only")
        ensure_key(entry, "tags", sorted(tags), after_key="norm_text")

        ensure_key(entry, "automation_hint", automation_hint, after_key="code_applicability")
        entry["code_applicability"] = automation_hint != "process"

    with NORMS_PATH.open("w", encoding="utf-8") as fp:
        yaml.dump(data, fp)

    category_counter = Counter()
    hint_counter = Counter()
    process_norms: List[Tuple[str, str]] = []
    for entry in records:
        category_counter[entry.get("category", "—")] += 1
        hint = entry.get("automation_hint")
        if hint:
            hint_counter[hint] += 1
            if hint == "process":
                process_norms.append((entry.get("norm_id", ""), entry.get("title", "")))

    lines = [
        "# Итоги категоризации STD норм",
        "",
        f"Всего STD норм: {sum(category_counter.values())}",
        "",
        "## Количество по категориям",
    ]
    for cat, count in category_counter.most_common():
        lines.append(f"- {cat}: {count}")
    lines.append("")
    lines.append("## Распределение automation_hint")
    for hint, count in hint_counter.items():
        lines.append(f"- {hint}: {count}")
    lines.append("")
    lines.append("## Нормы, требующие ручной проверки (process)")
    if process_norms:
        for norm_id, title in sorted(process_norms):
            lines.append(f"- {norm_id} — {title}")
    else:
        lines.append("- нет")

    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

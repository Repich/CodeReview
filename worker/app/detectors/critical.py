from __future__ import annotations

import re
from typing import Iterable

from worker.app.detectors.base import BaseDetector, DetectorContext
from worker.app.detectors.registry import register
from worker.app.models import DetectorFinding


def _append_if(condition: bool, findings: list[DetectorFinding], finding: DetectorFinding) -> None:
    if condition:
        findings.append(finding)


@register
class ExternalCodeOnServerDetector(BaseDetector):
    norm_id = "SECURITY_EXTERNAL_CODE_UNSAFE_SERVER"
    detector_id = "detector.external_code"
    severity = "critical"

    suspicious_tokens = (
        "ВнешняяОбработка",
        "ВнешнийОтчет",
        "ПодключитьВнешнююКомпоненту",
        "ПодключитьРасширение",
        ".epf",
        ".erf",
    )

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        if not ctx.source.has_server_sections:
            return []
        findings: list[DetectorFinding] = []
        for line_no, line in self.iter_lines(ctx.source.content):
            if not ctx.source.is_server_line(line_no):
                continue
            lowered = line.lower()
            if any(token.lower() in lowered for token in self.suspicious_tokens):
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Обнаружено подключение внешнего кода на сервере",
                        recommendation="Загрузку внешних обработок выполняйте только через доверенные подсистемы с контролем безопасного режима.",
                        line=line_no,
                        extra={"line": line.strip()},
                    )
                )
        return findings


@register
class ExecEvalServerDetector(BaseDetector):
    norm_id = "SECURITY_EXEC_EVAL_SERVER_RESTRICTED"
    detector_id = "detector.exec_eval"
    severity = "critical"

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        if not ctx.source.has_server_sections:
            return []
        findings: list[DetectorFinding] = []
        pattern = re.compile(r"(?<!\.)(Выполнить|Вычислить)\s*\(")
        for line_no, line in self.iter_lines(ctx.source.content):
            if not ctx.source.is_server_line(line_no):
                continue
            if pattern.search(line):
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Использование Выполнить/Вычислить на сервере",
                        recommendation="Запрещено выполнять динамический код без безопасного режима и строгой фильтрации параметров.",
                        line=line_no,
                        extra={"line": line.strip()},
                    )
                )
        return findings


@register
class ExternalProgramInjectionDetector(BaseDetector):
    norm_id = "SECURITY_LAUNCH_EXTERNAL_PROGRAM_INJECTION"
    detector_id = "detector.external_program"
    severity = "critical"

    command_pattern = re.compile(r"ЗапуститьПриложение|Shell|ЗапуститьПрограмму", re.IGNORECASE)

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        for line_no, line in self.iter_lines(ctx.source.content):
            if not self.command_pattern.search(line):
                continue
            if "+" in line or "%" in line or "СтрШаблон" in line:
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Строка запуска внешнего приложения собирается из непроверенных частей",
                        recommendation="Перед запуском приложения валидируйте параметры и используйте белые списки.",
                        line=line_no,
                        extra={"line": line.strip()},
                    )
                )
        return findings


@register
class DynamicExecutableFilesDetector(BaseDetector):
    norm_id = "SECURITY_NO_DYNAMIC_EXECUTABLE_FILES"
    detector_id = "detector.dynamic_epf"
    severity = "critical"

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        for line_no, line in self.iter_lines(ctx.source.content):
            if (".epf" in line.lower() or ".erf" in line.lower()) and "Записать" in line:
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Выявлена генерация внешней обработки/отчета",
                        recommendation="Запрещено формировать исполняемые внешние файлы динамически.",
                        line=line_no,
                        extra={"line": line.strip()},
                    )
                )
        return findings


@register
class ComAutomationDetector(BaseDetector):
    norm_id = "SECURITY_COM_AUTOMATION_DISABLE_MACROS"
    detector_id = "detector.com_automation"
    severity = "critical"

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        pattern = re.compile(r"Новый\s+COM(Объект|Object)|CreateObject", re.IGNORECASE)
        for line_no, line in self.iter_lines(ctx.source.content):
            if pattern.search(line):
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Использование COM-автоматизации без отключения макросов",
                        recommendation="Используйте безопасные обертки БСП и отключайте макросы по умолчанию.",
                        line=line_no,
                        extra={"line": line.strip()},
                    )
                )
        return findings


@register
class TlsVerifyDetector(BaseDetector):
    norm_id = "SECURITY_TLS_VERIFY_SERVER_AUTH"
    detector_id = "detector.tls_verify"
    severity = "critical"

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        bad_tokens = (
            "ПроверятьПодлинностьСервера = Ложь",
            "VerifyServerCertificate = False",
            "StrictSSL = False",
        )
        for line_no, line in self.iter_lines(ctx.source.content):
            if any(token in line for token in bad_tokens):
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Отключена проверка подлинности сервера в TLS",
                        recommendation="Запрещено отключать проверку сертификата сервера.",
                        line=line_no,
                        extra={"line": line.strip()},
                    )
                )
        return findings


@register
class TransactionPairingDetector(BaseDetector):
    norm_id = "TXN_BEGIN_COMMIT_ROLLBACK_PAIRING"
    detector_id = "detector.txn_pairing"
    severity = "critical"

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        content = ctx.source.content
        if "НачатьТранзакцию" not in content:
            return []
        has_commit = "ЗафиксироватьТранзакцию" in content
        has_rollback = "ОтменитьТранзакцию" in content
        if has_commit and has_rollback:
            return []
        line_no = next(
            (idx for idx, line in self.iter_lines(content) if "НачатьТранзакцию" in line),
            1,
        )
        missing = []
        if not has_commit:
            missing.append("ЗафиксироватьТранзакцию")
        if not has_rollback:
            missing.append("ОтменитьТранзакцию")
        message = f"В транзакции отсутствуют: {', '.join(missing)}"
        return [
            self.create_finding(
                ctx,
                message=message,
                recommendation="Пара Начать/Зафиксировать/Отменить должна использоваться всегда.",
                line=line_no,
                extra={"missing": missing},
            )
        ]


@register
class TransactionWorkloadDetector(BaseDetector):
    norm_id = "TXN_MINIMIZE_DURATION_AND_WORK"
    detector_id = "detector.txn_duration"
    severity = "major"

    loop_pattern = re.compile(r"\b(Для\s+каждого|Пока|Выборка.Следующий)\b", re.IGNORECASE)

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        lines = ctx.source.content.splitlines()
        inside_txn = False
        start_idx = 1
        for idx, line in enumerate(lines, start=1):
            if not inside_txn and "НачатьТранзакцию" in line:
                inside_txn = True
                start_idx = idx
                continue
            if inside_txn and "ЗафиксироватьТранзакцию" in line:
                break
            if inside_txn and self.loop_pattern.search(line):
                return [
                    self.create_finding(
                        ctx,
                        message="В транзакции выполняются длительные циклы",
                        recommendation="Вынесите тяжелые операции из транзакции или разделите их на батчи.",
                        line=idx,
                        extra={"pattern": line.strip(), "transaction_start": start_idx},
                    )
                ]
        return []


@register
class PrivilegedModeDetector(BaseDetector):
    norm_id = "ACCESS_PRIVILEGED_MODE_STRICT_SCOPE"
    detector_id = "detector.privileged_mode"
    severity = "critical"

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        content = ctx.source.content
        if "ПривилегированныйРежим = Истина" not in content:
            return []
        if "ПривилегированныйРежим = Ложь" in content:
            return []
        line_no = next(
            (idx for idx, line in self.iter_lines(content) if "ПривилегированныйРежим = Истина" in line),
            1,
        )
        return [
            self.create_finding(
                ctx,
                message="Привилегированный режим включается без возврата",
                recommendation="Используйте конструкцию Попытка/Исключение и гарантируйте возврат признака.",
                line=line_no,
                extra={},
            )
        ]


@register
class PlainPasswordStorageDetector(BaseDetector):
    norm_id = "SECURITY_PASSWORD_STORAGE_NO_PLAINTEXT"
    detector_id = "detector.password_plaintext"
    severity = "critical"

    pattern = re.compile(r"Пароль\s*=\s*\".+\"", re.IGNORECASE)

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        for line_no, line in self.iter_lines(ctx.source.content):
            if self.pattern.search(line):
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Обнаружено хранение пароля в открытом виде",
                        recommendation="Пользовательские секреты храните в защищенных хранилищах/регистрах сведений.",
                        line=line_no,
                        extra={"line": line.strip()},
                    )
                )
        return findings


@register
class FullOuterJoinDetector(BaseDetector):
    norm_id = "QUERY_NO_FULL_OUTER_JOIN_POSTGRES"
    detector_id = "detector.full_outer_join"
    severity = "major"

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        findings: list[DetectorFinding] = []
        pattern = re.compile(r"ПОЛНОЕ\s+СОЕДИНЕНИЕ|FULL\s+OUTER", re.IGNORECASE)
        for line_no, line in self.iter_lines(ctx.source.content):
            if pattern.search(line):
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Используется FULL OUTER JOIN, который не поддерживается",
                        recommendation="Перепишите запрос, разделив его на левое/правое соединение или используйте объединение.",
                        line=line_no,
                        extra={"line": line.strip()},
                    )
                )
        return findings


@register
class SessionDateUsageDetector(BaseDetector):
    norm_id = "TIME_USE_SESSION_TIME"
    detector_id = "detector.session_date_usage"
    severity = "major"

    pattern = re.compile(r"ТекущаяДата\s*\(", re.UNICODE)

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        if not ctx.source.has_server_sections:
            return []
        findings: list[DetectorFinding] = []
        for line_no, line in self.iter_lines(ctx.source.content):
            if not ctx.source.is_server_line(line_no):
                continue
            if "ТекущаяДатаСеанса" in line:
                continue
            if self.pattern.search(line):
                findings.append(
                    self.create_finding(
                        ctx,
                        message="Используется ТекущаяДата() вместо ТекущаяДатаСеанса()",
                        recommendation="На сервере используйте ТекущаяДатаСеанса(), чтобы учитывать часовой пояс пользователя.",
                        line=line_no,
                        extra={"line": line.strip()},
                    )
                )
        return findings


@register
class ExceptionSwallowDetector(BaseDetector):
    norm_id = "TXN_EXCEPTION_LOG_OR_RERAISE"
    detector_id = "detector.exception_swallow"
    severity = "major"

    safe_tokens = (
        "ВызватьИсключение",
        "ЖурналРегистрации",
        "ЗаписьЖурналаРегистрации",
        "ТребуетсяЖурналРегистрации",
    )

    def detect(self, ctx: DetectorContext) -> Iterable[DetectorFinding]:
        content_lines = ctx.source.content.splitlines()
        findings: list[DetectorFinding] = []
        idx = 0
        while idx < len(content_lines):
            line = content_lines[idx]
            if line.strip().startswith("Исключение"):
                block_start_line = idx + 1
                block_lines: list[str] = []
                j = idx + 1
                while j < len(content_lines) and "КонецПопытки" not in content_lines[j]:
                    block_lines.append(content_lines[j])
                    j += 1
                if j == len(content_lines):
                    break
                block_text = "\n".join(block_lines)
                if not any(token in block_text for token in self.safe_tokens):
                    findings.append(
                        self.create_finding(
                            ctx,
                            message="Исключение обрабатывается без логирования или перекидывания ошибки",
                            recommendation="Логируйте ошибку в журнал регистрации и/или вызовите ВызватьИсключение, чтобы не скрывать проблему.",
                            line=block_start_line,
                            extra={"block": block_text.strip()[:200]},
                        )
                    )
                idx = j
            else:
                idx += 1
        return findings

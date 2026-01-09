# Detector ↔ Norm mapping

| Detector | Norm | Title | Category | Severity | Automation | Tags |
| --- | --- | --- | --- | --- | --- | --- |
| `detector.full_outer_join` | `QUERY_NO_FULL_OUTER_JOIN_POSTGRES` | Не использовать FULL OUTER JOIN в PostgreSQL | queries_performance | major | code | queries, code |
| `detector.privileged_mode` | `ACCESS_PRIVILEGED_MODE_STRICT_SCOPE` | Привилегированный режим с возвратом состояния | security_access | critical | code | security, code |
| `detector.com_automation` | `SECURITY_COM_AUTOMATION_DISABLE_MACROS` | COM-объекты должны использоваться с отключением макросов | security_access | critical | code | security, code |
| `detector.exec_eval` | `SECURITY_EXEC_EVAL_SERVER_RESTRICTED` | Выполнение динамического кода на сервере | security_access | critical | code | security, code |
| `detector.external_code` | `SECURITY_EXTERNAL_CODE_UNSAFE_SERVER` | Запрет загрузки внешнего кода на сервере | security_access | critical | code | security, code |
| `detector.external_program` | `SECURITY_LAUNCH_EXTERNAL_PROGRAM_INJECTION` | Формирование команд запуска из неподконтрольных частей | security_access | critical | code | security, code |
| `detector.dynamic_epf` | `SECURITY_NO_DYNAMIC_EXECUTABLE_FILES` | Генерация исполняемых файлов запрещена | security_access | critical | code | security, code |
| `detector.password_plaintext` | `SECURITY_PASSWORD_STORAGE_NO_PLAINTEXT` | Запрет хранения паролей в открытом виде | security_access | critical | code | security, code |
| `detector.tls_verify` | `SECURITY_TLS_VERIFY_SERVER_AUTH` | Запрет отключать проверку подлинности сервера | security_access | critical | code | security, code |
| `detector.txn_pairing` | `TXN_BEGIN_COMMIT_ROLLBACK_PAIRING` | Пары Begin/Commit/Rollback обязательны | transactions_locks | critical | code | transactions, code |
| `detector.txn_duration` | `TXN_MINIMIZE_DURATION_AND_WORK` | Минимизировать длительность и работу в транзакциях | transactions_locks | major | code | transactions, performance |

### Добавлено по LLM-чек-листу

| Detector | Norm | Title | Category | Severity | Automation | Tags |
| --- | --- | --- | --- | --- | --- | --- |
| `detector.session_date_usage` | `TIME_USE_SESSION_TIME` | На сервере использовать ТекущаяДатаСеанса | timezones | major | code | time, code |
| `detector.exception_swallow` | `TXN_EXCEPTION_LOG_OR_RERAISE` | Не гасить ошибки в блоке Исключение | transactions_locks | major | code | transactions, logging |
| `detector.form_direct_write` | `FORM_NO_DIRECT_METADATA_WRITE` | Форма не записывает объекты напрямую | ui_forms_behavior | major | code | forms, ui |
| `detector.todo_comment` | `COMMENT_NO_TODO_MARKERS` | Служебные TODO/FIXME запрещены | code_style | minor | code | code-style |
## Coverage by category
- security_access: 8 detector(s)
- transactions_locks: 2 detector(s)
- queries_performance: 1 detector(s)

## Categories without detectors (>=10 norms)
- —: 733 norms, 0 detectors
- ui_forms_behavior: 99 norms, 0 detectors
- data_model_registers: 78 norms, 0 detectors
- metadata_design: 24 norms, 0 detectors
- ui_navigation: 14 norms, 0 detectors
- governance_release: 11 norms, 0 detectors

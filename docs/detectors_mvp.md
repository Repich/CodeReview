# MVP детекторы

| # | norm_id | detector_id | Тип | Краткое описание |
|---|---------|-------------|-----|------------------|
| 1 | SECURITY_EXTERNAL_CODE_UNSAFE_SERVER | detector.external_code | security | Поиск загрузки внешних обработок/расширений на сервере. |
| 2 | SECURITY_EXEC_EVAL_SERVER_RESTRICTED | detector.exec_eval | security | Детектирует Выполнить/Вычислить в серверных модулях. |
| 3 | SECURITY_LAUNCH_EXTERNAL_PROGRAM_INJECTION | detector.external_program | security | Контролирует сборку строк запуска внешних программ. |
| 4 | SECURITY_NO_DYNAMIC_EXECUTABLE_FILES | detector.dynamic_epf | security | Запрещает запись внешних файлов .epf/.erf во время работы. |
| 5 | SECURITY_COM_AUTOMATION_DISABLE_MACROS | detector.com_automation | security | Находит создание COM-объектов без безопасных оберток. |
| 6 | SECURITY_TLS_VERIFY_SERVER_AUTH | detector.tls_verify | security | Фиксирует отключение проверки сертификата сервера. |
| 7 | TXN_BEGIN_COMMIT_ROLLBACK_PAIRING | detector.txn_pairing | transaction | Проверяет наличие пар Зафиксировать/Отменить. |
| 8 | TXN_MINIMIZE_DURATION_AND_WORK | detector.txn_duration | transaction | Находит циклы внутри активной транзакции. |
| 9 | ACCESS_PRIVILEGED_MODE_STRICT_SCOPE | detector.privileged_mode | access | Контролирует возврат ПривилегированногоРежима. |
| 10 | SECURITY_PASSWORD_STORAGE_NO_PLAINTEXT | detector.password_plaintext | security | Ловит присваивания пароля строковой константой. |
| 11 | QUERY_NO_FULL_OUTER_JOIN_POSTGRES | detector.full_outer_join | query | Запрещает FULL OUTER JOIN для PostgreSQL. |

Каждый детектор имеет два теста (положительный и отрицательный сценарий) в `worker/tests/test_detectors.py`.

## Приоритетные категории и идеи для следующих детекторов

### 1. UI / формы (`ui_forms_behavior`, 180 норм)

| Норма | Идея детектора | Тесты |
| --- | --- | --- |
| `SESSION_PARAMS_NOT_FOR_CLIENT_LOGIC` — не использовать параметры сеанса в чисто клиентской логике | `detector.session_params_client`: ищет обращения `ПараметрыСеанса.*` внутри процедур/функций с директивами `&НаКлиенте` или в модулях форм. Сообщает, если нет серверной обёртки. | + форма с `&НаКлиенте` методом, где прямо читается `ПараметрыСеанса`. − серверный модуль или клиент, который вызывает безопасный API (например, общий модуль). |
| `FORM_LAYOUT_05`/`FORM_LAYOUT_07` — единообразные имена и расположение элементов | `detector.form_duplicate_names`: анализирует элементы форм в BSL (по методам `Элементы.Добавить` / `Элементы.Найти`) и предупреждает, если создаются элементы с несогласованными именами (например, `Контрагент1`). | + модуль формы, где добавляется элемент `Контрагент1`. − форма, где элементы используют предопределённое имя `Контрагент`. |

**Статус:** реализованы `detector.session_params_client` и `detector.form_element_naming` (см. `worker/app/detectors/ui_queries.py`).

### 2. Данные и регистры (`data_model_registers`, 176 норм)

| Норма | Идея детектора | Тесты |
| --- | --- | --- |
| `NAME_NO_QUERY_TABLE_WORDS` — имена подчинённых объектов не должны совпадать с ключевыми словами языка запросов | `detector.metadata_reserved_words`: по `ctx.source.path` извлекает имя объекта (например, `Catalogs/Select/Ext/ObjectModule.bsl`) и сверяет с перечнем запрещённых ключевых слов (`ВЫБРАТЬ`, `ИЗ`, `ГДЕ`, `SELECT`, `FROM`). | + путь `Catalogs/Select/Ext/ObjectModule.bsl`. − путь `Catalogs/Items/Ext/ObjectModule.bsl`. |
| `DOC_SAVE_IN_POST_MODE` — запись документов сразу в режиме проведения | `detector.doc_save_mode`: в модуле документа ищет вызовы `Записать()` без аргумента или с `РежимЗаписиДокумента.Обычный`. | + `Документ.Записать();` в модуле документа. − `Документ.Записать(РежимЗаписиДокумента.Проведение);`. |

**Статус:** реализован `detector.document_save_mode`.

### 3. Запросы / производительность (`queries_performance`, 111 норм)

| Норма | Идея детектора | Тесты |
| --- | --- | --- |
| `QUERY_KEYWORDS_UPPER` — ключевые слова языка запросов пишутся заглавными | `detector.query_upper_keywords`: извлекает строки внутри `"""`/`''` запросов или объектов `Запрос.Текст` и проверяет ключевые слова (`выбрать`, `из`, `где`). | + текст запроса с `выбрать`. − корректно оформленный запрос с `ВЫБРАТЬ`. |
| `QUERY_EXPLICIT_ALIASES` — столбцы должны иметь псевдонимы | `detector.query_aliases`: парсит SELECT блок и ищет выражения без `КАК`/`AS`. Работает хотя бы для простых случаев (`Поле КАК Поле`). | + `ВЫБРАТЬ Документ.Ссылка` без `КАК`. − `ВЫБРАТЬ Документ.Ссылка КАК Ссылка`. |
| `QUERY_NO_COMMENT_PATCHING` — не модифицировать запросы через комментарии | `detector.query_comment_patching`: ищет `СтрЗаменить(ТекстЗапроса, \"/*...*/\", ...)` либо конкатенации `+"/*"` после задания текста запроса. | + код, где после `Запрос.Текст` идёт `+ \"/*where*/\"`. − статичный текст без модификаций. |

**Статус:** реализованы `detector.query_upper_keywords`, `detector.query_aliases`, `detector.query_comment_patching`.

### 4. Прочие стандарты

| Норма | Идея | Статус |
| --- | --- | --- |
| `TEXT_MAX_LINE_LENGTH` — строки не длиннее 150 | `detector.line_length`: проверяет ширину строк, исключая переносы. | Реализован (`worker/app/detectors/ui_queries.py`). |
| `QUERY_MULTILINE` — запрос оформлен с переводами строк | `detector.query_multiline`: ловит присваивания `Запрос.Текст = "..."` и `Новый Запрос("...")`, где строка без перевода. | Реализован. |
| `SESSION_PARAMS_NOT_CACHE` — не использовать параметры сеанса как кеш | `detector.session_params_cache`: фиксирует присваивания `ПараметрыСеанса.* = ...`. | Реализован. |
| `MULTI_WRITE_REG_01` — набор записей регистра не создаётся в каждой итерации | `detector.register_loop_creation`: отслеживает `СоздатьНаборЗаписей()` внутри циклов `Для Каждого/Пока`. | Реализован (`worker/app/detectors/registers.py`). |
| `MULTI_WRITE_REG_03` — запись набора записей регистра не выполняется внутри цикла | `detector.register_loop_write`: ищет `.Записать()`/`.Прочитать()` регистров внутри циклов. | Реализован. |
| `NAME_NO_OWNER_DUPLICATE` — имя подчинённого объекта не совпадает с владельцем | `detector.child_name_dup_owner`: по пути `Catalogs/*`/`Documents/*` сопоставляет имя владельца и ссылки вида `Реквизиты.Владелец`. | Реализован (эвристика по пути файла). |
| `QUERY_GENERAL_01` — не использовать `ВЫБРАТЬ *` | `detector.query_select_star`: ищет `ВЫБРАТЬ *`/`SELECT *` и требует перечислять поля. | Реализован (`worker/app/detectors/ui_queries.py`). |
| `QUERY_GENERAL_02` — минимизировать количество запросов | `detector.query_inside_loop`: предупреждает о `Новый Запрос`/`Запрос.Выполнить` внутри циклов. | Реализован. |

### Новые детекторы из LLM-чек-листа

| # | norm_id | detector_id | Тип | Краткое описание |
|---|---------|-------------|-----|------------------|
| 12 | `TIME_USE_SESSION_TIME` | `detector.session_date_usage` | timezones | Ловит вызовы `ТекущаяДата()` в серверных модулях и предлагает заменить на `ТекущаяДатаСеанса()`. |
| 13 | `TXN_EXCEPTION_LOG_OR_RERAISE` | `detector.exception_swallow` | transactions | Проверяет блоки `Исключение` на отсутствие логирования или `ВызватьИсключение`, чтобы ошибки не «гасились». |
| 14 | `FORM_NO_DIRECT_METADATA_WRITE` | `detector.form_direct_write` | ui_forms_behavior | Отслеживает попытки модулей форм напрямую создавать/записывать справочники, документы или наборы записей. |
| 15 | `COMMENT_NO_TODO_MARKERS` | `detector.todo_comment` | code_style | Запрещает служебные пометки `TODO/FIXME/Уточнить` в продуктивном коде. |

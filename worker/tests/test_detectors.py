from __future__ import annotations

from worker.app.detectors import critical  # noqa: F401 ensures registration
from worker.app.detectors.base import DetectorContext
from worker.app.detectors.critical import (
    ExternalCodeOnServerDetector,
    ExecEvalServerDetector,
    ExternalProgramInjectionDetector,
    DynamicExecutableFilesDetector,
    ComAutomationDetector,
    TlsVerifyDetector,
    TransactionPairingDetector,
    TransactionWorkloadDetector,
    PrivilegedModeDetector,
    PlainPasswordStorageDetector,
    FullOuterJoinDetector,
    SessionDateUsageDetector,
    ExceptionSwallowDetector,
)
from worker.app.detectors.formatting import (
    EmptyRegionDetector,
    IndentSpacesDetector,
    MultipleBlankLinesDetector,
    TrailingTabsDetector,
)
from worker.app.detectors.ui_queries import (
    DocumentSaveModeDetector,
    FormElementNamingDetector,
    FormDirectDataWriteDetector,
    LineLengthDetector,
    MetadataReservedWordsDetector,
    QueryCommentPatchingDetector,
    QueryExplicitAliasesDetector,
    QueryInsideLoopDetector,
    QueryMultilineDetector,
    QuerySelectStarDetector,
    QueryUppercaseKeywordsDetector,
    SessionParamsCacheDetector,
    SessionParamsClientDetector,
    TodoCommentDetector,
)
from worker.app.detectors.registers import (
    ChildNameMatchesOwnerDetector,
    RegisterLoopRecordsetCreationDetector,
    RegisterLoopRecordsetWriteDetector,
)
from worker.app.models import SourceUnit


def run(
    detector_cls,
    content: str,
    *,
    module_type: str = "CommonModule",
    path: str = "test.bsl",
):
    detector = detector_cls()
    source = SourceUnit(
        path=path,
        name="Test",
        content=content,
        module_type=module_type,
    )
    ctx = DetectorContext(source=source)
    return list(detector.detect(ctx))


def test_external_code_detector_positive():
    content = """Процедура Тест();
ВнешняяОбработка = ЗагрузитьВнешнююОбработку(\"hack.epf\");
КонецПроцедуры"""
    assert run(ExternalCodeOnServerDetector, content)


def test_external_code_detector_negative_for_client_module():
    content = """&НаКлиенте
Процедура Тест()
    ВнешняяОбработка = ЗагрузитьВнешнююОбработку("hack.epf");
КонецПроцедуры"""
    assert not run(ExternalCodeOnServerDetector, content)


def test_exec_eval_detector_positive():
    content = """Функция Х()
    Выполнить(\"Сообщить(1)\");
КонецФункции"""
    assert run(ExecEvalServerDetector, content)


def test_exec_eval_detector_negative_without_keyword():
    assert not run(ExecEvalServerDetector, "Сообщить(\"ok\")")


def test_external_program_injection_positive():
    content = "ЗапуститьПриложение(Команда + Параметры);"
    assert run(ExternalProgramInjectionDetector, content)


def test_external_program_injection_negative():
    assert not run(ExternalProgramInjectionDetector, "ЗапуститьПриложение(\"calc.exe\")")


def test_dynamic_executable_files_positive():
    content = "Файл.Записать(Каталог + \"/tmp.epf\");"
    assert run(DynamicExecutableFilesDetector, content)


def test_dynamic_executable_files_negative():
    assert not run(DynamicExecutableFilesDetector, "Файл.Записать(\"log.txt\")")


def test_com_automation_positive():
    content = "Новый COMОбъект(\"Excel.Application\");"
    assert run(ComAutomationDetector, content)


def test_com_automation_negative():
    content = "Новый COMОбъект(\"ADODB.Command\");"
    assert not run(ComAutomationDetector, content)


def test_tls_verify_positive():
    content = "ПроверятьПодлинностьСервера = Ложь;"
    assert run(TlsVerifyDetector, content)


def test_tls_verify_negative():
    assert not run(TlsVerifyDetector, "ПроверятьПодлинностьСервера = Истина;")


def test_transaction_pairing_missing_commit():
    content = """НачатьТранзакцию();
// что-то
ОтменитьТранзакцию();"""
    findings = run(TransactionPairingDetector, content)
    assert findings and "Зафиксировать" in findings[0].message


def test_transaction_pairing_complete():
    content = """НачатьТранзакцию();
ЗафиксироватьТранзакцию();
ОтменитьТранзакцию();"""
    assert not run(TransactionPairingDetector, content)


def test_transaction_workload_loop_in_txn():
    content = """НачатьТранзакцию();
Для каждого Строка Из Коллекция Цикл
КонецЦикла;
ЗафиксироватьТранзакцию();"""
    assert run(TransactionWorkloadDetector, content)


def test_transaction_workload_without_loop():
    content = """НачатьТранзакцию();
Записать();
ЗафиксироватьТранзакцию();"""
    assert not run(TransactionWorkloadDetector, content)


def test_privileged_mode_missing_reset():
    content = "ПривилегированныйРежим = Истина;"
    assert run(PrivilegedModeDetector, content)


def test_privileged_mode_with_reset():
    content = """ПривилегированныйРежим = Истина;
ПривилегированныйРежим = Ложь;"""
    assert not run(PrivilegedModeDetector, content)


def test_plain_password_positive():
    content = "Пароль = \"secret\";"
    assert run(PlainPasswordStorageDetector, content)


def test_plain_password_negative():
    content = "Пароль = ПолучитьПароль();"
    assert not run(PlainPasswordStorageDetector, content)


def test_full_outer_join_positive():
    content = " ВЫБРАТЬ ... ПОЛНОЕ СОЕДИНЕНИЕ ..."
    assert run(FullOuterJoinDetector, content)


def test_full_outer_join_negative():
    content = " ВЫБРАТЬ ... ЛЕВОЕ СОЕДИНЕНИЕ ..."
    assert not run(FullOuterJoinDetector, content)


def test_session_params_client_positive():
    content = """&НаКлиенте
Процедура Тест()
    Знач = ПараметрыСеанса.Пользователь;
КонецПроцедуры"""
    assert run(SessionParamsClientDetector, content)


def test_session_params_client_negative_for_server_block():
    content = """&НаСервере
Процедура Тест()
    Знач = ПараметрыСеанса.Пользователь;
КонецПроцедуры"""
    assert not run(SessionParamsClientDetector, content)


def test_metadata_reserved_words_positive():
    assert run(
        MetadataReservedWordsDetector,
        "Процедура Тест() КонецПроцедуры",
        path="Catalogs/Select/Ext/ObjectModule.bsl",
    )


def test_metadata_reserved_words_negative():
    assert not run(
        MetadataReservedWordsDetector,
        "Процедура Тест() КонецПроцедуры",
        path="Catalogs/Items/Ext/ObjectModule.bsl",
    )


def test_query_uppercase_keywords_positive():
    content = 'Запрос.Текст = "выбрать Ссылка из Справочник.Тест";'
    assert run(QueryUppercaseKeywordsDetector, content)


def test_query_uppercase_keywords_negative():
    content = 'Запрос.Текст = "ВЫБРАТЬ Ссылка ИЗ Справочник.Тест";'
    assert not run(QueryUppercaseKeywordsDetector, content)


def test_query_uppercase_keywords_negative_non_query_context():
    content = "Функция ДанныеSQL(Соединение, ТекстЗапроса) Экспорт"
    assert not run(QueryUppercaseKeywordsDetector, content)


def test_form_element_naming_positive():
    content = 'Элементы.Добавить("Контрагент1", Тип("ПолеФормы"));'
    assert run(FormElementNamingDetector, content, module_type="FormModule")


def test_form_element_naming_negative():
    content = 'Элементы.Добавить("Контрагент", Тип("ПолеФормы"));'
    assert not run(FormElementNamingDetector, content, module_type="FormModule")


def test_document_save_mode_positive():
    content = "Объект.Записать();"
    assert run(
        DocumentSaveModeDetector,
        content,
        module_type="DocumentModule",
        path="Documents/Act/Ext/ObjectModule.bsl",
    )


def test_document_save_mode_negative():
    content = "Объект.Записать(РежимЗаписиДокумента.Проведение);"
    assert not run(
        DocumentSaveModeDetector,
        content,
        module_type="DocumentModule",
        path="Documents/Act/Ext/ObjectModule.bsl",
    )


def test_query_aliases_positive():
    content = """Запрос.Текст = "ВЫБРАТЬ 
| Документ.Ссылка
| ИЗ Документ.Тест";"""
    assert run(QueryExplicitAliasesDetector, content)


def test_query_aliases_negative():
    content = """Запрос.Текст = "ВЫБРАТЬ 
| Документ.Ссылка КАК Ссылка
| ИЗ Документ.Тест";"""
    assert not run(QueryExplicitAliasesDetector, content)


def test_query_aliases_negative_with_tabs():
    content = """Запрос.Текст = "ВЫБРАТЬ 
| ЗНАЧЕНИЕ(ВидДвиженияНакопления.Приход)\tКАК ВидДвижения
| ИЗ Документ.Тест";"""
    assert not run(QueryExplicitAliasesDetector, content)


def test_query_aliases_negative_where_condition():
    content = """Запрос.Текст = "ВЫБРАТЬ 
| Документ.Ссылка КАК Ссылка
| ИЗ Документ.Тест
| ГДЕ
| Документ.Ссылка = &Ссылка";"""
    assert not run(QueryExplicitAliasesDetector, content)


def test_query_aliases_negative_order_by():
    content = """Запрос.Текст = "ВЫБРАТЬ 
| Документ.Ссылка КАК Ссылка
| ИЗ Документ.Тест
| УПОРЯДОЧИТЬ ПО
| Документ.Ссылка";"""
    assert not run(QueryExplicitAliasesDetector, content)


def test_query_aliases_negative_case_multiline():
    content = """Запрос.Текст = "ВЫБРАТЬ
| ВЫБОР КОГДА &Флаг = 1 ТОГДА
|     НЕОПРЕДЕЛЕНО
| ИНАЧЕ
|     Товары.Упаковка.Наименование
| КОНЕЦ КАК Упаковка
| ИЗ Документ.Тест";"""
    assert not run(QueryExplicitAliasesDetector, content)


def test_query_aliases_negative_union_tail():
    content = """Запрос.Текст = "ВЫБРАТЬ
| Таблица.Ссылка КАК Ссылка
| ИЗ Справочник.Тест КАК Таблица
| ОБЪЕДИНИТЬ ВСЕ
| ВЫБРАТЬ
| Таблица2.Ссылка
| ИЗ Справочник.Тест2 КАК Таблица2";"""
    assert not run(QueryExplicitAliasesDetector, content)


def test_query_comment_patching_positive():
    content = 'Запрос.Текст = Запрос.Текст + "/*where*/";'
    assert run(QueryCommentPatchingDetector, content)


def test_query_comment_patching_negative():
    content = 'Запрос.Текст = "ВЫБРАТЬ Ссылка ИЗ Документ.Тест";'
    assert not run(QueryCommentPatchingDetector, content)


def test_line_length_positive():
    content = "ДлиннаяСтрока = '" + ("x" * 130) + "';"
    assert run(LineLengthDetector, content)


def test_line_length_negative():
    content = "КороткаяСтрока = 'ok';"
    assert not run(LineLengthDetector, content)


def test_query_multiline_positive():
    content = 'Запрос.Текст = "ВЫБРАТЬ Ссылка ИЗ Документ.Тест";'
    assert run(QueryMultilineDetector, content)


def test_query_multiline_negative():
    content = 'Запрос.Текст = "ВЫБРАТЬ \n| Документ.Ссылка\n| ИЗ Документ.Тест";'
    assert not run(QueryMultilineDetector, content)


def test_empty_region_detector_positive():
    content = "#Область Тест\n#КонецОбласти"
    assert run(EmptyRegionDetector, content)


def test_empty_region_detector_negative_with_content():
    content = "#Область Тест\nПроцедура Х()\nКонецПроцедуры\n#КонецОбласти"
    assert not run(EmptyRegionDetector, content)


def test_indent_spaces_detector_positive():
    content = "  Процедура Х()\nКонецПроцедуры"
    assert run(IndentSpacesDetector, content)


def test_indent_spaces_detector_negative_with_tabs():
    content = "\tПроцедура Х()\n\tКонецПроцедуры"
    assert not run(IndentSpacesDetector, content)


def test_trailing_tabs_detector_positive():
    content = "Процедура Х()\t\t\nКонецПроцедуры"
    assert run(TrailingTabsDetector, content)


def test_trailing_tabs_detector_negative_without_tabs():
    content = "Процедура Х()\nКонецПроцедуры"
    assert not run(TrailingTabsDetector, content)


def test_multiple_blank_lines_detector_positive():
    content = "Процедура Х()\n\n\nКонецПроцедуры"
    assert len(run(MultipleBlankLinesDetector, content)) == 2


def test_multiple_blank_lines_detector_negative():
    content = "Процедура Х()\n\nКонецПроцедуры"
    assert not run(MultipleBlankLinesDetector, content)


def test_session_params_cache_positive():
    content = "ПараметрыСеанса.Валюта = Значение;"
    assert run(SessionParamsCacheDetector, content)


def test_session_params_cache_negative_on_read():
    content = "Знач = ПараметрыСеанса.Валюта;"
    assert not run(SessionParamsCacheDetector, content)


def test_query_select_star_positive():
    content = 'Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Тест";'
    assert run(QuerySelectStarDetector, content)


def test_query_select_star_negative():
    content = 'Запрос.Текст = "ВЫБРАТЬ Ссылка ИЗ Справочник.Тест";'
    assert not run(QuerySelectStarDetector, content)


def test_register_loop_creation_positive():
    content = """Для Каждого Стр Из Таблица Цикл
    Набор = РегистрыСведений.Настройки.СоздатьНаборЗаписей();
КонецЦикла;"""
    assert run(RegisterLoopRecordsetCreationDetector, content)


def test_register_loop_creation_negative():
    content = """Набор = РегистрыСведений.Настройки.СоздатьНаборЗаписей();
Для Каждого Стр Из Таблица Цикл
    // работа без создания набора
КонецЦикла;"""
    assert not run(RegisterLoopRecordsetCreationDetector, content)


def test_register_loop_write_positive():
    content = """Для Каждого Стр Из Таблица Цикл
    РегистрыСведений.Настройки.Записать();
КонецЦикла;"""
    assert run(RegisterLoopRecordsetWriteDetector, content)


def test_register_loop_write_negative():
    content = """РегистрыСведений.Настройки.Записать();
Для Каждого Стр Из Таблица Цикл
    Сообщить(Стр);
КонецЦикла;"""
    assert not run(RegisterLoopRecordsetWriteDetector, content)


def test_child_name_matches_owner_positive():
    content = "Реквизиты.Номенклатура = Номенклатура;"
    assert run(
        ChildNameMatchesOwnerDetector,
        content,
        path="Catalogs/Номенклатура/Ext/ObjectModule.bsl",
    )


def test_child_name_matches_owner_negative():
    content = "Реквизиты.Описание = Номенклатура;"
    assert not run(
        ChildNameMatchesOwnerDetector,
        content,
        path="Catalogs/Номенклатура/Ext/ObjectModule.bsl",
    )


def test_query_inside_loop_positive():
    content = """Для Каждого Стр Из Таблица Цикл
    Запрос = Новый Запрос;
КонецЦикла;"""
    assert run(QueryInsideLoopDetector, content)


def test_query_inside_loop_negative():
    content = """Запрос = Новый Запрос;
Для Каждого Стр Из Таблица Цикл
    Сообщить(Стр);
КонецЦикла;"""
    assert not run(QueryInsideLoopDetector, content)


def test_query_inside_loop_negative_set_param():
    content = """Запрос = Новый Запрос;
Для Каждого Стр Из Таблица Цикл
    Запрос.УстановитьПараметр(Стр.Ключ, Стр.Значение);
КонецЦикла;"""
    assert not run(QueryInsideLoopDetector, content)


def test_virtual_table_params_positive():
    content = """Запрос.Текст = "ВЫБРАТЬ
| Номенклатура
| ИЗ
| РегистрНакопления.ТоварыНаСкладах.Остатки() КАК Остатки
| ГДЕ
| Остатки.Склад = &Склад";"""
    assert run(VirtualTableParamsDetector, content)


def test_virtual_table_params_negative_with_params():
    content = """Запрос.Текст = "ВЫБРАТЬ
| Номенклатура
| ИЗ
| РегистрНакопления.ТоварыНаСкладах.Остатки(, Склад = &Склад) КАК Остатки
| ГДЕ
| Остатки.Склад = &Склад";"""
    assert not run(VirtualTableParamsDetector, content)


def test_session_date_usage_positive():
    content = """&НаСервере
Функция Получить()
    Возврат ТекущаяДата();
КонецФункции"""
    assert run(SessionDateUsageDetector, content)


def test_session_date_usage_negative():
    content = """&НаСервере
Функция Получить()
    Возврат ТекущаяДатаСеанса();
КонецФункции"""
    assert not run(SessionDateUsageDetector, content)


def test_exception_swallow_positive():
    content = """Попытка
        НачатьТранзакцию();
    Исключение
        Сообщить(ОписаниеОшибки());
    КонецПопытки;"""
    assert run(ExceptionSwallowDetector, content)


def test_exception_swallow_negative_with_log():
    content = """Попытка
        НачатьТранзакцию();
    Исключение
        ЖурналРегистрации.ДобавитьСообщение("err");
    КонецПопытки;"""
    assert not run(ExceptionSwallowDetector, content)


def test_exception_swallow_negative_with_error_payload():
    content = """Попытка
        НачатьТранзакцию();
    Исключение
        Результат.ТекстОшибки = ОбработкаОшибок.ПодробноеПредставлениеОшибки(ИнформацияОбОшибке());
        Результат.Успешно = Ложь;
    КонецПопытки;"""
    assert not run(ExceptionSwallowDetector, content)


def test_form_direct_data_write_positive():
    content = "Справочники.Номенклатура.СоздатьЭлемент();"
    assert run(FormDirectDataWriteDetector, content, module_type="FormModule", path="Forms/Item/FormModule.bsl")


def test_form_direct_data_write_negative_on_lookup():
    content = "Справочники.Номенклатура.НайтиПоКоду(Код);"
    assert not run(FormDirectDataWriteDetector, content, module_type="FormModule", path="Forms/Item/FormModule.bsl")


def test_todo_comment_positive():
    content = "// TODO: удалить после релиза"
    assert run(TodoCommentDetector, content)


def test_todo_comment_negative():
    content = "// Комментарий для разработчиков"
    assert not run(TodoCommentDetector, content)

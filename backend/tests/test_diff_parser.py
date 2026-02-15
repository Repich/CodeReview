from backend.app.services.diff_parser import parse_crucible_diff


def test_parse_crucible_diff_keeps_single_number_lines_as_changed() -> None:
    payload = """
    1690 1716 КонецФункции
    1691 1717
  < >     1718 Функция POSCreditВанта_СоздатьЗаказ(ПараметрыОтправки)
      1719 //CR-74361 ATurgenev 1.09.2025
      1720
      1721         СтрРезультат = ПараметрыОтправки.СтрРезультат;
      1764 КонецФункции
   1692 1799 Функция POSCredit_ПроверкаСтатуса(КредитнаяЗаявка)
    1693 1800
    1694 1801         Результат = Новый Структура;
""".strip("\n")

    content, ranges = parse_crucible_diff(payload)

    assert ranges == [(3, 7)]
    lines = content.splitlines()
    assert lines[2] == "Функция POSCreditВанта_СоздатьЗаказ(ПараметрыОтправки)"
    assert lines[3] == "//CR-74361 ATurgenev 1.09.2025"
    assert lines[5] == "СтрРезультат = ПараметрыОтправки.СтрРезультат;"
    assert lines[7] == "Функция POSCredit_ПроверкаСтатуса(КредитнаяЗаявка)"


def test_parse_crucible_diff_skips_delete_only_single_number_lines() -> None:
    payload = """
    10 10 Начало
  < 11 УдаленнаяСтрока
    12 ДобавленнаяСтрока
    13 13 Конец
""".strip("\n")

    content, ranges = parse_crucible_diff(payload)

    assert "УдаленнаяСтрока" not in content
    assert "ДобавленнаяСтрока" in content
    assert ranges == [(2, 2)]

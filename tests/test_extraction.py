from app.services.extraction import extract_fields

def test_extracts_date_and_name():
    fields = extract_fields("ФИО: Иванов Иван Иванович\nДата выдачи: 12.05.2025\n№ 123-А")
    assert fields["full_name"].value == "Иванов Иван Иванович"
    assert fields["issue_date"].value == "12.05.2025"
    assert fields["document_number"].value == "123-А"

def test_missing_fields_are_explicit():
    fields = extract_fields("Текст без реквизитов")
    assert fields["full_name"].value is None
    assert fields["issue_date"].confidence == 0

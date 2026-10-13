# Внутренний каталог DOCX-шаблонов

Сюда сервис сохраняет шаблоны, загруженные через `convert_to_template(file_path)`, панель администратора (`/admin` → «Шаблоны DOCX») или команду `python -m dekanat template-add`. Каждая версия лежит отдельным файлом: `<идентификатор>/v1.docx`, `v2.docx`, …; прежние версии не перезаписываются.

Каталог задаётся параметром `storage.templates_dir` в `config/settings.yaml` (по умолчанию `templates`). Содержимое в репозиторий не попадает (`.gitignore`): шаблоны вуза могут содержать служебные реквизиты. Учебный пример — `examples/templates/zayavlenie_o_perevode.docx`.

from pathlib import Path


def test_templates_do_not_show_old_project_name():
    template_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("web/templates").rglob("*.html")
    )

    assert "Dizzy Ducks" not in template_text

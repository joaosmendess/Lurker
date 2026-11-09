from app.sources.base import html_to_text


def test_paragraphs_become_lines_and_entities_are_decoded() -> None:
    assert html_to_text("<p>R&amp;D</p><p>Second</p>") == "R&D\nSecond"


def test_list_items_become_bullets_even_with_nested_paragraphs() -> None:
    html = "<ul><li><p>First</p></li><li>Second</li></ul>"

    assert html_to_text(html) == "- First\n- Second"


def test_script_and_style_content_is_dropped() -> None:
    html = "<style>p {color: red}</style><p>Visible</p><script>alert(1)</script>"

    assert html_to_text(html) == "Visible"


def test_whitespace_is_collapsed() -> None:
    assert html_to_text("<p>  a \t  b  c  </p>") == "a b c"


def test_plain_text_is_kept() -> None:
    assert html_to_text("no html here") == "no html here"

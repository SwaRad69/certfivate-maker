import re
from types import SimpleNamespace

import pytest

from generator import detect_placeholders_in_slide, replace_text_in_slide


class SlidesPresentation:
    """In-memory Slides API supporting selective native matching and UTF-16 edits."""

    def __init__(self, containers, *, native=True, apply_manual=True):
        self.containers = containers
        self.native = native
        self.apply_manual = apply_manual
        self.requests = []

    def presentations(self):
        return self

    def get(self, **_):
        def execute():
            page_elements = []
            for (object_id, cell), chunks in self.containers.items():
                text = {'textElements': [{'textRun': {'content': chunk}} for chunk in chunks]}
                if cell is None:
                    page_elements.append({'objectId': object_id, 'shape': {'text': text}})
                else:
                    row, column = cell
                    cell_data = {'location': {'rowIndex': row, 'columnIndex': column}, 'text': text}
                    table = {'tableRows': [{'tableCells': [cell_data]}]}
                    page_elements.append({'objectId': object_id, 'table': table})
            return {'slides': [{'pageElements': page_elements}]}

        return SimpleNamespace(execute=execute)

    def batchUpdate(self, *, body, **_):
        def execute():
            replies = []
            for request in body['requests']:
                self.requests.append(request)
                kind, action = next(iter(request.items()))
                if kind == 'replaceAllText':
                    changed = 0
                    if self.native:
                        pattern = re.compile(re.escape(action['containsText']['text']), re.IGNORECASE)
                        for key, chunks in self.containers.items():
                            updated_chunks = []
                            for chunk in chunks:
                                chunk, count = pattern.subn(lambda _: action['replaceText'], chunk)
                                updated_chunks.append(chunk)
                                changed += count
                            self.containers[key] = updated_chunks
                    replies.append({'replaceAllText': {'occurrencesChanged': changed}})
                elif self.apply_manual:
                    self._apply_manual(kind, action)
            return {'replies': replies}

        return SimpleNamespace(execute=execute)

    def _apply_manual(self, kind, action):
        cell = action.get('cellLocation')
        location = (action['objectId'], (cell['rowIndex'], cell['columnIndex']) if cell else None)
        data = ''.join(self.containers[location]).encode('utf-16-le')
        if kind == 'deleteText':
            span = action['textRange']
            data = data[:span['startIndex'] * 2] + data[span['endIndex'] * 2:]
        else:
            point = action['insertionIndex'] * 2
            data = data[:point] + action['text'].encode('utf-16-le') + data[point:]
        self.containers[location] = [data.decode('utf-16-le')]


def test_mixed_native_fallback_preserves_repeats_case_and_utf16():
    shape = ('shape-id', None)
    table = ('table-id', (2, 4))
    slides = SlidesPresentation({
        shape: ['A {{Name}} ', '🌟{{n', 'AmE}} and {{', 'ID}}\n'],
        table: ['{{', 'Id}} ({{iD', '}})\n'],
    })
    assert detect_placeholders_in_slide(slides, 'copy') == {'name', 'id'}

    assert replace_text_in_slide(slides, 'copy', {'NAME': 'Café', 'id': '0008'})
    assert ''.join(slides.containers[shape]) == 'A Café 🌟Café and 0008\n'
    assert ''.join(slides.containers[table]) == '0008 (0008)\n'
    assert any('replaceAllText' in request for request in slides.requests)
    assert any('deleteText' in request for request in slides.requests)


def test_unresolved_occurrences_reject_the_row_even_if_native_reports_a_replacement():
    slides = SlidesPresentation({('shape', None): ['{{Name}}', ' {{Na', 'me}}\n']}, apply_manual=False)
    with pytest.raises(ValueError, match=r'Unresolved placeholders: name \(1\)'):
        replace_text_in_slide(slides, 'copy', {'name': 'Ada'}, raise_on_failure=True)
    assert not replace_text_in_slide(slides, 'copy', {'name': 'Ada'})


def test_missing_replacements_are_reported_with_occurrence_counts():
    slides = SlidesPresentation({('shape', None): ['{{Id}} {{ID}}\n']})
    with pytest.raises(ValueError, match=r'Missing replacement values for placeholders: id \(2\)'):
        replace_text_in_slide(slides, 'copy', {'name': 'Ada'}, raise_on_failure=True)
    assert not slides.requests


def test_literal_placeholder_like_values_are_not_processed_again():
    shape = ('shape', None)
    slides = SlidesPresentation({shape: ['{{name}} {{id}} {{empty}}\n']})
    assert replace_text_in_slide(slides, 'copy', {'name': '{{id}}', 'id': '0001', 'empty': ''})
    assert ''.join(slides.containers[shape]) == '{{id}} 0001 \n'
    assert all('replaceAllText' not in request for request in slides.requests)


def test_blank_and_multiline_replacements_preserve_visible_text():
    shape = ('shape', None)
    slides = SlidesPresentation({shape: ['{{x}} and {{', 'y}}\n']})
    assert replace_text_in_slide(slides, 'copy', {'x': '', 'y': 'line 1\r\nline 2'})
    assert ''.join(slides.containers[shape]) == ' and line 1\nline 2\n'

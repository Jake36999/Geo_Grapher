"""A constant's rationale includes a whole contiguous, same-indent comment block."""
from geographer.comment_blocks import constant_comment_lines


def test_full_block_inline_span_and_multiple_bindings():
    text = '# Buffered uploads use this size.\n# Keep it below the transport window.\nBUFFER_SIZE = 8  # bytes\n'
    assert constant_comment_lines(text, [('a', 3, 3), ('b', 3, 3)]) == {
        1: {'a', 'b'}, 2: {'a', 'b'}, 3: {'a', 'b'}}


def test_comment_block_stops_at_blank_statement_and_wrong_indent():
    text = '# unrelated\n\n# belongs to first\nFIRST = 1 # first only\nSECOND = 2\nclass C:\n    # class setting\n    VALUE = 3\n# outside class\n    OTHER = 4\n'
    result = constant_comment_lines(text, [('first', 4, 4), ('second', 5, 5), ('value', 8, 8), ('other', 10, 10)])
    assert result == {3: {'first'}, 4: {'first'}, 5: {'second'}, 7: {'value'}, 8: {'value'}, 10: {'other'}}


def test_multiline_assignment_and_empty_inputs():
    text = '# worker settings\nOPTIONS = (\n    "open",  # allowed\n    "find",\n)\n'
    assert constant_comment_lines(text, [('options', 2, 5)]) == {n: {'options'} for n in range(1, 6)}
    assert constant_comment_lines('', []) == {}


def test_line_iteration_is_independent_of_constant_order():
    text = '# first\nFIRST = 1\n# second\nSECOND = 2\n'
    constants = [('first', 2, 2), ('second', 4, 4)]
    left = constant_comment_lines(text, constants)
    right = constant_comment_lines(text, reversed(constants))
    assert left == right and list(left) == list(right) == [1, 2, 3, 4]

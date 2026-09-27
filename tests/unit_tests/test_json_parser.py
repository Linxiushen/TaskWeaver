import json
from typing import Any, List

import pytest

from taskweaver.utils import json_parser

obj_cases: List[Any] = [
    ["hello", "world"],
    "any_str",
    {
        "test_key": {
            "str_array": ["hello", "world", "test"],
            "another_key": {},
            "empty_array": [[[]], []],
        },
    },
    [True, False, None],
    [1, 2, 3],
    123.345,
    {"val": 123.345},
    [
        {
            "a": {},
            "b": {},
            "c": {},
            "d": {},
            "e": {},
        },
    ],
    {
        "test_key": {
            "str_array": ["hello", "world", "test"],
            "test another key": [
                "hello",
                "world",
                1,
                2.0,
                True,
                False,
                None,
                {
                    "test yet another key": "test value",
                    "test yet  key 2": '\r\n\u1234\ffdfd\tfdfv\b"',
                },
            ],
            True: False,
        },
    },
]


@pytest.mark.parametrize("obj", obj_cases)
def test_json_parser(obj: Any):
    dumped_str = json.dumps(obj)

    # expect error with the JSON is incomplete
    for i in range(len(dumped_str) - 1):
        cur_incomplete_seg = dumped_str[:i]

        try:
            float(cur_incomplete_seg)
            # skip incomplete number that is valid JSON as well
            continue
        except ValueError:
            pass

        with pytest.raises(json_parser.StreamJsonParserError):
            json_parser.parse_json(cur_incomplete_seg)

            # proper parsing exception should raise before this
            raise Exception("Failed to parse incomplete JSON: " + cur_incomplete_seg)

    obj = json_parser.parse_json(json.dumps(obj))
    dumped_str2 = json.dumps(obj)
    assert dumped_str == dumped_str2


str_cases: List[str] = [
    '   { "a": [ true, false, null ] }  ',
    "  \r  \n \t  [  \r \n \t true, false, null \r \n \t ]  \r \n \t  ",
    ' \r \n \t "hello world" \r \n \t ',
]


@pytest.mark.parametrize("str_case", str_cases)
def test_json_parser_str(str_case: str):
    obj = json.loads(str_case)
    dumped_str = json.dumps(obj)
    obj = json_parser.parse_json(str_case)
    dumped_str2 = json.dumps(obj)
    assert dumped_str == dumped_str2


bad_cases: List[str] = [
    " - ",
    "'abc'",
    "\\a",
    "{} {}",
    "[[[]}]",
    '""""',
    "{'abc': 'def'}",
    "[[[[{{{{0}}}}]]]]",
    "              ",
    "",
    "((((()))))",
    '"\\"',
    # incomplete json
    '"abc',
    "[1,2,3",
    '{"abc',
    '{"abc":',
    '{"abc":}',
    '{"abc":1',
    "123,456,789",
    "undefined",
    "None",
    "{true: false}",
]


@pytest.mark.parametrize("bad_case", bad_cases)
def test_json_parser_bad(bad_case: str):
    with pytest.raises(json_parser.StreamJsonParserError):
        json_parser.parse_json(bad_case)


@pytest.mark.parametrize("chunk_size", [1, 2, 7, 64])
def test_surrogate_pairs_in_streamed_keys_and_values(chunk_size: int):
    message = "Ready \U0001f680\U00020000 \U00010000\U0010ffff!"
    obj = {"\U0001f680": [message, {"nested": message}]}
    text = json.dumps(obj)
    chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
    assert json_parser.parse_json(chunks) == obj

    text = json.dumps(message)
    chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
    events = list(json_parser.parse_json_stream(chunks, skip_ws=True))
    assert "".join(event.value_str for event in events) == message
    assert events[-1].value == message
    for event in events:
        event.value_str.encode("utf-8")


@pytest.mark.parametrize(
    "text",
    [
        r'"\ud83d"',
        r'"\ude80"',
        r'"\ud83dA"',
        r'"\ud83d\n"',
        r'"\ud83d\u0041"',
        r'"\ud83d\ud83d\ude80"',
        r'"\ude80\ud83d"',
        r'"\\ud83d\\ude80"',
    ],
)
def test_unpaired_surrogates_match_json_loads(text: str):
    expected = json.loads(text)
    assert json_parser.parse_json(iter(text)) == expected
    events = list(json_parser.parse_json_stream(iter(text), skip_ws=True))
    assert "".join(event.value_str for event in events) == expected

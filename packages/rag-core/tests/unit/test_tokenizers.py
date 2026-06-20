import sys
from typing import cast

from rag_core.tokenizers import (
    EnglishFallbackTokenizer,
    FallbackWrapperTokenizer,
    KoreanFallbackTokenizer,
    TiktokenTokenizer,
    get_tokenizer,
)


def test_factory_resolution() -> None:
    # Check default
    strategy_en = get_tokenizer()
    assert isinstance(strategy_en, FallbackWrapperTokenizer)
    assert isinstance(strategy_en.fallback, EnglishFallbackTokenizer)
    assert isinstance(strategy_en.primary, TiktokenTokenizer)

    # Check Korean
    strategy_ko = get_tokenizer("ko")
    assert isinstance(strategy_ko, FallbackWrapperTokenizer)
    assert isinstance(strategy_ko.fallback, KoreanFallbackTokenizer)
    assert isinstance(strategy_ko.primary, TiktokenTokenizer)

    # Check case insensitivity
    strategy_ko_upper = get_tokenizer("KO")
    assert isinstance(strategy_ko_upper, FallbackWrapperTokenizer)
    assert isinstance(strategy_ko_upper.fallback, KoreanFallbackTokenizer)

    # Check invalid falls back to English fallback
    strategy_invalid = get_tokenizer("fr")
    assert isinstance(strategy_invalid, FallbackWrapperTokenizer)
    assert isinstance(strategy_invalid.fallback, EnglishFallbackTokenizer)


def test_english_success_with_tiktoken() -> None:
    strategy = get_tokenizer()
    text = "Hello, world! This is a test."
    tokens = strategy.encode(text)
    assert len(tokens) > 0
    assert strategy.decode(tokens) == text
    assert strategy.count_tokens(text) == len(tokens)
    assert strategy.truncate(text, 3) == strategy.decode(tokens[:3])


def test_english_fallback_strategy() -> None:
    fallback = EnglishFallbackTokenizer()

    # English count fallback: 0.25 tokens per char, min 1 for non-empty
    assert fallback.count_tokens("abcdefgh") == 2
    assert fallback.count_tokens("") == 0
    assert fallback.count_tokens("a") == 1

    # English encode/decode fallback
    encoded = fallback.encode("hello")
    assert encoded == [104, 101, 108, 108, 111]
    assert fallback.decode(encoded) == "hello"

    # English truncate fallback (4 chars per token)
    assert fallback.truncate("abcdefghijkl", 2) == "abcdefgh"
    assert fallback.truncate("abcdefgh", 10) == "abcdefgh"


def test_korean_success_with_tiktoken() -> None:
    strategy = get_tokenizer("ko")
    text = "안녕하세요, 테스트입니다."
    tokens = strategy.encode(text)
    assert len(tokens) > 0
    assert strategy.decode(tokens) == text
    assert strategy.count_tokens(text) == len(tokens)


def test_korean_fallback_strategy() -> None:
    fallback = KoreanFallbackTokenizer()

    # Korean count fallback: Hangul = 1.5, other = 0.25
    assert fallback.count_tokens("안녕하세요반갑습니다") == 15
    assert fallback.count_tokens("abcd안녕") == 4
    assert fallback.count_tokens("") == 0

    # Korean encode/decode fallback
    encoded = fallback.encode("안녕")
    assert fallback.decode(encoded) == "안녕"

    # Korean truncate fallback
    assert fallback.truncate("안녕하세요", 3) == "안녕"
    assert fallback.truncate("안녕하세요", 4) == "안녕"
    assert fallback.truncate("안녕하세요", 5) == "안녕하"
    assert fallback.truncate("안녕하세요", 10) == "안녕하세요"


def test_fallback_wrapper_runtime_failure() -> None:
    # Test that FallbackWrapperTokenizer correctly handles runtime errors in primary tokenizer
    class BrokenTokenizer(TiktokenTokenizer):
        def count_tokens(self, text: str) -> int:
            raise RuntimeError("Primary failed")

        def encode(self, text: str) -> list[int]:
            raise RuntimeError("Primary failed")

        def decode(self, tokens: list[int]) -> str:
            raise RuntimeError("Primary failed")

        def truncate(self, text: str, max_tokens: int) -> str:
            raise RuntimeError("Primary failed")

    broken_primary = BrokenTokenizer()
    fallback = KoreanFallbackTokenizer()
    wrapper = FallbackWrapperTokenizer(primary=broken_primary, fallback=fallback)

    # Runtime fallback checks
    assert wrapper.count_tokens("abcd안녕") == 4
    assert wrapper.encode("안녕") == [ord("안"), ord("녕")]
    assert wrapper.decode([ord("안"), ord("녕")]) == "안녕"
    assert wrapper.truncate("안녕하세요", 3) == "안녕"


def test_invalid_input_handling() -> None:
    strategy = get_tokenizer()
    assert strategy.count_tokens(cast(str, None)) == 0
    assert strategy.encode(cast(str, None)) == []
    assert strategy.truncate(cast(str, None), 5) == ""
    assert strategy.decode(cast(list[int], None)) == ""


def test_fallback_decode_error_handling() -> None:
    fallback = EnglishFallbackTokenizer()
    # sys.maxunicode + 1 (1114112) is out of range for chr()
    out_of_range_unicode = sys.maxunicode + 1
    invalid_tokens = [104, 101, out_of_range_unicode, 108, 111]
    decoded = fallback.decode(invalid_tokens)
    assert decoded == "he\ufffdlo"


def test_fallback_wrapper_circuit_breaker() -> None:
    count_calls = 0
    encode_calls = 0

    class CountingBrokenTokenizer(TiktokenTokenizer):
        def count_tokens(self, text: str) -> int:
            nonlocal count_calls
            count_calls += 1
            raise RuntimeError("Primary count failed")

        def encode(self, text: str) -> list[int]:
            nonlocal encode_calls
            encode_calls += 1
            raise RuntimeError("Primary encode failed")

    primary = CountingBrokenTokenizer()
    fallback = EnglishFallbackTokenizer()
    wrapper = FallbackWrapperTokenizer(primary=primary, fallback=fallback)

    # Initial states
    assert not wrapper._count_tokens_broken
    assert not wrapper._encode_broken

    # First count_tokens call: triggers failure, sets count-specific flag
    assert wrapper.count_tokens("abc") == 1
    assert wrapper._count_tokens_broken
    assert not wrapper._encode_broken  # Other methods are not affected
    assert count_calls == 1

    # Second count_tokens call: bypasses primary count
    assert wrapper.count_tokens("abc") == 1
    assert count_calls == 1

    # First encode call: triggers failure, sets encode-specific flag
    assert wrapper.encode("abc") == [97, 98, 99]
    assert wrapper._encode_broken
    assert encode_calls == 1

    # Second encode call: bypasses primary encode
    assert wrapper.encode("abc") == [97, 98, 99]
    assert encode_calls == 1

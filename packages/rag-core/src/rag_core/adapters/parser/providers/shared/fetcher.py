import anyio

from rag_core.adapters.parser.interface import ParserInput
from rag_core.adapters.parser.providers.shared.network_security import (
    _validate_ssrf,
    get_safe_http_client,
)


async def get_input_bytes(parser_input: ParserInput) -> bytes:
    """Safely retrieves or downloads the raw content bytes from ParserInput.

    Mitigates SSRF if downloading from a remote HTTP(S) URL.
    """
    if parser_input.content is not None:
        return parser_input.content

    if parser_input.source:
        if parser_input.source.startswith(("http://", "https://")):
            _validate_ssrf(parser_input.source)
            client = get_safe_http_client()
            response = await client.get(parser_input.source, timeout=15.0)
            response.raise_for_status()
            return response.content
        else:
            path = anyio.Path(parser_input.source)
            return await path.read_bytes()

    raise ValueError("ParserInput has neither content nor source.")

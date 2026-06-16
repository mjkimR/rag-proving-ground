import asyncio
import datetime
import hashlib
import json
import time
from pathlib import Path

import click
from loguru import logger
from rag_core.adapters.parser import SUPPORTED_PDF_PROVIDERS
from rag_core.adapters.parser.instance import get_parser
from rag_core.adapters.parser.interface import ParserInput
from rag_core.parsers import KnowledgeParsingConfig, knowledge_parsing_config_hash


async def parse_single_pdf(
    pdf_path: Path,
    provider: str,
    force: bool,
    native_max_chars: int,
) -> None:
    click.echo(f"Processing: {pdf_path.name}")
    try:
        pdf_bytes = pdf_path.read_bytes()
    except Exception as e:
        logger.error(f"Failed to read file {pdf_path}: {e}")
        return

    content_hash = hashlib.sha256(pdf_bytes).hexdigest()

    # Construct parsing config and get hash
    config = KnowledgeParsingConfig(
        provider=provider,
        native_max_page_chars=native_max_chars,
    )
    config_hash = knowledge_parsing_config_hash(config)

    # Cache directory: {pdf_folder}/{pdf_stem}/{parser_provider}/{parsing_config_hash}/
    pdf_stem = pdf_path.stem
    cache_dir = pdf_path.parent / pdf_stem / provider / config_hash
    parsed_data_path = cache_dir / "parsed_data.json"
    meta_path = cache_dir / "meta.json"

    # Check cache
    if not force and parsed_data_path.exists() and meta_path.exists():
        click.echo(f"  -> Cache HIT (Config Hash: {config_hash})")
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            click.echo(f"     Parsed at: {meta.get('converted_at')}")
            click.echo(f"     Duration: {meta.get('parse_duration_sec'):.2f}s")
            return
        except Exception as e:
            logger.warning(f"Failed to read cache metadata for {pdf_path.name}, parsing anyway: {e}")

    click.echo(f"  -> Cache MISS. Running parser '{provider}'...")

    # Initialize parser input
    parser_input = ParserInput(
        content=pdf_bytes,
        filename=pdf_path.name,
        content_type="application/pdf",
    )

    try:
        parser = get_parser(provider=provider)
    except Exception as e:
        logger.error(f"Failed to initialize parser provider '{provider}': {e}")
        return

    start_time = time.perf_counter()
    try:
        result = await parser.parse(parser_input)
    except Exception as e:
        logger.exception(f"Failed to parse {pdf_path.name}: {e}")
        if provider == "docling":
            click.echo(
                "Warning: If docling is not running, start it using: 'just up docling'",
                err=True,
            )
        return
    duration = time.perf_counter() - start_time

    click.echo(f"  -> Successfully parsed in {duration:.2f} seconds.")

    try:
        cache_data = parser.to_cache_data(result)
    except Exception as e:
        logger.error(f"Failed to serialize parser result to cache data: {e}")
        return

    # Ensure cache directory exists
    cache_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "parsing_config": config.model_dump(mode="json", exclude_none=True),
        "content_hash": content_hash,
        "hash_algorithm": "sha256",
        "filename": pdf_path.name,
        "filesize_bytes": len(pdf_bytes),
        "parse_duration_sec": duration,
        "converted_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }

    try:
        with open(parsed_data_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2, sort_keys=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2, sort_keys=True)
        click.echo(f"  -> Saved results to cache: {cache_dir}")
    except Exception as e:
        logger.error(f"Failed to save cached results for {pdf_path.name}: {e}")


async def parse_all_pdfs(
    pdf_dir: Path,
    provider: str,
    force: bool,
    native_max_chars: int,
) -> None:
    pdf_files = sorted(list(pdf_dir.glob("*.pdf")))
    if not pdf_files:
        click.echo(f"No PDF files found in directory: {pdf_dir}")
        return

    click.echo(f"Found {len(pdf_files)} PDF files in {pdf_dir}.")
    for pdf_file in pdf_files:
        await parse_single_pdf(
            pdf_path=pdf_file,
            provider=provider,
            force=force,
            native_max_chars=native_max_chars,
        )


@click.command()
@click.option(
    "--pdf-dir",
    "-d",
    default="datasets/pdfs",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Directory containing PDF files to parse.",
)
@click.option(
    "--provider",
    "-p",
    default="docling",
    type=click.Choice(SUPPORTED_PDF_PROVIDERS),
    help="Parser provider name.",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Bypass local cache and force re-parsing.",
)
@click.option(
    "--native-max-chars",
    default=2000,
    type=int,
    help="Max characters per synthetic page in the native text parser.",
)
def main(
    pdf_dir: Path,
    provider: str,
    force: bool,
    native_max_chars: int,
) -> None:
    """Parse PDF files and store output locally in structured cache directories."""
    if provider == "native_text":
        raise click.UsageError(
            "The 'native_text' provider is not designed to parse binary PDF files. Please use 'docling'."
        )

    asyncio.run(
        parse_all_pdfs(
            pdf_dir=pdf_dir,
            provider=provider,
            force=force,
            native_max_chars=native_max_chars,
        )
    )


if __name__ == "__main__":
    main()

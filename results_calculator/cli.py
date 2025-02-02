import logging

import typer


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the entire application."""
    log_level = logging.DEBUG if verbose else logging.INFO

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Setup console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    logger.handlers = []  # Remove any existing handlers
    logger.addHandler(console_handler)


app = typer.Typer(
    pretty_exceptions_show_locals=False, no_args_is_help=True, callback=setup_logging
)

# Add verbose flag to all commands
app_options = {
    "verbose": typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging",
        is_eager=True,  # Ensure this is processed before other options
    )
}

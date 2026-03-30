"""X-Claw CLI — Click-based command interface."""

import click

from xclaw.cli.core import setup
from xclaw.cli._silence import silence_third_party, ensure_cuda_dll_dirs
from xclaw.cli.commands.look import look
from xclaw.cli.commands.action import click_cmd, type_cmd, press, scroll, wait, hotkey, drag, move, cursor, hold


@click.group()
def cli():
    """X-Claw Visual Agent CLI"""
    setup()
    silence_third_party()
    ensure_cuda_dll_dirs()


cli.add_command(look)
cli.add_command(click_cmd)
cli.add_command(type_cmd)
cli.add_command(press)
cli.add_command(scroll)
cli.add_command(wait)
cli.add_command(hotkey)
cli.add_command(drag)
cli.add_command(move)
cli.add_command(cursor)
cli.add_command(hold)

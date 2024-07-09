import click


def log_modify_file(file_path):
    click.secho(f"  📁 Modifying File: {file_path}", fg="yellow")


def log_cli_command(command):
    click.secho(f'  ⬆️  CLI command: {" ".join(command)}', fg="bright_cyan")


def log_cli_response(result):
    click.secho(f"  ⬇️  CLI result:", fg="bright_cyan")
    click.secho(f"{result.strip()}", fg="bright_black")


def log_task(step):
    click.secho(f"📋 {step}", fg="green", bold=True)


def log_skip_task(step):
    click.secho(f"📋 {step}", fg="green", bold=True)


def log_success(step):
    click.secho(f"✅ {step}", fg="green", bold=True)


def log_info(message):
    click.secho(f"  ℹ {message}", fg="bright_black")


def log_error(message):
    click.secho(f"❌ {message}", fg="red", bold=True)

from pathlib import Path

import typer
from pydantic import BaseModel
from ruamel.yaml import YAML

from .data import get_chip_package_and_core
from .tableator import Tableator

yaml = YAML()


app = typer.Typer()


class _Spec(BaseModel):
    class Requirement(BaseModel):
        name: str
        peripheral: str | None = None
        kind: str | None = None
        signals: list[str] | None = None

    chip: str
    package: str
    requirements: list[Requirement]
    reserved_pins: list[str] = []


@app.command()
def main(reqs: Path | None = None, chip: str | None = None, package: str | None = None):
    if reqs is None:
        reqs = Path("reqs.yml")

    if reqs.suffix == ".json":
        _reqs = _Spec.model_validate_json(reqs.read_text())
    elif reqs.suffix in (".yaml", ".yml"):
        _reqs = _Spec.model_validate(yaml.load(reqs.read_text()))
    else:
        raise ValueError(f"Unsupported spec extension: {reqs.suffix}")

    # Allows overriding the chip and package from the command line
    # to experiment with different chips and packages
    if chip is not None:
        _reqs.chip = chip
    if package is not None:
        _reqs.package = package

    package, core = get_chip_package_and_core(_reqs.chip, _reqs.package)

    tableator = Tableator(package, core)
    for requirement in _reqs.requirements:
        tableator.add_req(
            requirement_name=requirement.name,
            peripheral_name=requirement.peripheral,
            peripheral_kind=requirement.kind,
            peripheral_signal_names=requirement.signals,
        )

    for pin in _reqs.reserved_pins:
        tableator.reserve_pin(pin)

    tableator.solve()


if __name__ == "__main__":
    app()

import json
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from .utils import find_one

CACHE_DIR = Path.cwd() / ".pinocchiout_cache" / "chip_data"


class Stm32Model(BaseModel):
    class Package(BaseModel):
        class Pin(BaseModel):
            signals: list[str]

        name: str
        package: str
        pins: list[Pin]

    class Core(BaseModel):
        class Peripheral(BaseModel):
            class Registers(BaseModel):
                kind: str

            class Pin(BaseModel):
                pin: str
                signal: str

            name: str
            registers: Registers
            pins: list[Pin] | None = None

        peripherals: list[Peripheral]

    packages: list[Package]
    cores: list[Core]


class Manifest(BaseModel):
    class RecordInfo(BaseModel):
        name: str
        download_url: str

    records: list[RecordInfo]

    @classmethod
    def from_data(cls, data: list) -> "Manifest":
        return cls(records=[cls.RecordInfo(**record) for record in data])


_data_cache: dict[str, Any] = {}


def _get_data(filename: str, url: str) -> Any:
    if filename not in _data_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        file_path = CACHE_DIR / filename

        if file_path.is_file():
            with file_path.open(encoding="utf-8") as f:
                data = json.load(f)
        else:
            response = httpx.get(url)
            response.raise_for_status()
            data = response.json()
            with file_path.open("w", encoding="utf-8") as f:
                json.dump(data, f)

        _data_cache[filename] = data

    return _data_cache[filename]


def get_manifest() -> Manifest:
    return Manifest.from_data(_get_data("manifest.json", "https://api.github.com/repos/embassy-rs/stm32-data-generated/contents/data/chips"))


def get_chip_package_and_core(chip_name: str, package_name: str) -> tuple[Stm32Model.Package, Stm32Model.Core]:
    manifest = get_manifest()
    for record in manifest.records:
        if not record.name.startswith(chip_name):
            continue

        data = _get_data(record.name, record.download_url)
        model = Stm32Model(**data)

        try:
            package = find_one(lambda p: p.package.startswith(package_name), model.packages)
        except KeyError:
            continue

        return package, model.cores[0]

    raise ValueError(f"No package found for {chip_name} and {package_name}")

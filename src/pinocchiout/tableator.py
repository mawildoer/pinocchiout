"""Recommended end-use Python-API for Pinocchio."""

import re
from dataclasses import dataclass

import rich
import z3
from rich.table import Table

from .data import Stm32Model
from .solver import PinSolver
from .utils import coerce_pattern, find_one


class Tableator:
    @dataclass
    class _Row:
        peripheral_ref: z3.DatatypeRef
        signal_spec: re.Pattern
        signal_ref: z3.DatatypeRef

    def __init__(self, package: Stm32Model.Package, core: Stm32Model.Core):
        self.data: list[Tableator._Row] = []
        self.package = package
        self.core = core
        self.solver = PinSolver(package, core)

    def add_req(
        self,
        requirement_name: str,
        peripheral_name: str | re.Pattern | None = None,
        peripheral_kind: str | None = None,
        peripheral_signal_names: list[str | re.Pattern] | None = None,
    ) -> None:
        peripheral_ref, signal_refs = self.solver.add_peripheral_requirement(
            requirement_name=requirement_name,
            peripheral_name=peripheral_name,
            peripheral_kind=peripheral_kind,
            peripheral_signal_names=peripheral_signal_names,
        )
        for peripheral_signal_name, signal_ref in zip(peripheral_signal_names or [], signal_refs, strict=True):
            self.data.append(
                self._Row(
                    peripheral_ref=peripheral_ref,
                    signal_spec=coerce_pattern(peripheral_signal_name),
                    signal_ref=signal_ref,
                ),
            )

    def reserve_pin(self, pin_name: str) -> None:
        self.solver.reserve_pin(pin_name)

    def solve(self) -> None:
        solution = self.solver.solve()

        table = Table("requirement", "peripheral", "signal", "pin")
        for row in self.data:
            requirement_name = str(row.peripheral_ref)
            peripheral_name = str(solution[row.peripheral_ref])
            pin_name = str(solution[row.signal_ref])

            peripheral_model = find_one(lambda p: p.name == peripheral_name, self.core.peripherals)
            peripheral_pin_model = find_one(
                lambda p: p.pin == pin_name and row.signal_spec.match(p.signal), peripheral_model.pins
            )
            signal_name = peripheral_pin_model.signal
            table.add_row(requirement_name, peripheral_name, signal_name, pin_name)

        rich.print(table)

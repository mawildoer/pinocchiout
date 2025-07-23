"""Recommended end-use Python-API for Pinocchio."""

import re
from dataclasses import dataclass
from typing import Iterator

import rich
import z3
from rich.table import Table

from .data import Stm32Model
from .solver import PinSolver
from .utils import coerce_pattern, find_one


class Tableator:
    @dataclass
    class _Row:
        requirement_name: str
        peripheral_ref: z3.DatatypeRef | None
        signal_spec: re.Pattern | None
        pin_ref: z3.DatatypeRef

    def __init__(self, package: Stm32Model.Package, core: Stm32Model.Core):
        self.data: list[Tableator._Row] = []
        self.package = package
        self.core = core
        self.solver = PinSolver(package, core)
        self.solution = None

    def add_req(
        self,
        requirement_name: str,
        peripheral_name: str | re.Pattern | None = None,
        peripheral_kind: str | None = None,
        peripheral_signal_names: list[str | re.Pattern] | None = None,
        *,
        consume_peripheral: bool = True,
    ) -> None:
        peripheral_ref, signal_refs = self.solver.add_peripheral_requirement(
            requirement_name=requirement_name,
            peripheral_name=peripheral_name,
            peripheral_kind=peripheral_kind,
            peripheral_signal_names=peripheral_signal_names,
            consume_peripheral=consume_peripheral,
        )
        for peripheral_signal_name, signal_ref in zip(peripheral_signal_names or [], signal_refs, strict=True):
            self.data.append(
                self._Row(
                    requirement_name=requirement_name,
                    peripheral_ref=peripheral_ref,
                    signal_spec=coerce_pattern(peripheral_signal_name),
                    pin_ref=signal_ref,
                ),
            )

    def reserve_pin(self, requirement_name: str, pin: str | re.Pattern) -> z3.DatatypeRef:
        pin_ref = self.solver.reserve_pin(requirement_name, pin)
        self.data.append(self._Row(
            requirement_name=requirement_name,
            peripheral_ref=None,
            signal_spec=None,
            pin_ref=pin_ref,
        ))
        return pin_ref

    def get_solution(self) -> z3.ModelRef:
        if self.solution is None:
            self.solution = self.solver.solve()
        return self.solution

    def iter_solution(self) -> Iterator[tuple[str, str, str, str]]:
        solution = self.get_solution()
        for row in self.data:
            requirement_name = row.requirement_name
            pin_name = str(solution[row.pin_ref])

            if row.peripheral_ref is None:
                peripheral_name = "~"
                signal_name = "~"
            else:
                peripheral_name = str(solution[row.peripheral_ref])
                peripheral_model = find_one(lambda p: p.name == peripheral_name, self.core.peripherals)
                peripheral_pin_model = find_one(
                    lambda p: p.pin == pin_name and row.signal_spec.match(p.signal), peripheral_model.pins
                )
                signal_name = peripheral_pin_model.signal

            yield requirement_name, peripheral_name, signal_name, pin_name

    def solve(self) -> None:
        table = Table("requirement", "peripheral", "signal", "pin")
        for requirement_name, peripheral_name, signal_name, pin_name in self.iter_solution():
            table.add_row(requirement_name, peripheral_name, signal_name, pin_name)

        rich.print(table)

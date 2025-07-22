"""Pinout solver for STM32 microcontrollers."""
import re
import typing
from typing import Callable, Iterable  # noqa: UP035

import z3

from .data import Stm32Model
from .utils import coerce_pattern, uniquify


def _make_z3_enum(name: str, elements: Iterable[str]) -> tuple[z3.DatatypeSortRef, dict]:
    _elements = list(elements)
    enum, enum_elements = z3.EnumSort(name, _elements)
    enum_members = dict(zip(_elements, enum_elements, strict=True))

    return enum, enum_members


def _is_one_of_predicate[T](value: T, iterable: Iterable[T]) -> z3.BoolRef:
    return typing.cast("z3.BoolRef", z3.Or(*[value == x for x in iterable]))


class PinSolver:
    """Solve for the best pins to use for a given set of requirements."""

    class InvalidPeripheralError(Exception):
        """Raised when a peripheral is not viable for a requirement."""

    class NoSignalError(InvalidPeripheralError):
        """Raised when a pin is not viable for a requirement."""

    class NoSolutionError(Exception):
        """Raised when no solution is found."""

    def __init__(self, package: Stm32Model.Package, core: Stm32Model.Core):
        self.package = package
        self.core = core
        self.peripheral_enum_sort, self.peripheral_enum_members = _make_z3_enum(
            "peripherals",
            (peripheral.name for peripheral in core.peripherals),
        )
        self.pin_enum_sort, self.pin_enum_members = _make_z3_enum(
            "pins",
            (s for pin in package.pins for s in pin.signals),
        )

        self.solver = z3.Solver()

        self._consumed_requirement_names = set()
        self._consumed_signal_names = set()

        self._peripheral_refs = []
        self._pin_refs = []


    def add_peripheral_requirement(
        self,
        requirement_name: str,
        peripheral_name: str | re.Pattern | None = None,
        peripheral_kind: str | None = None,
        peripheral_signal_names: list[str | re.Pattern] | None = None,
    ) -> tuple[z3.DatatypeRef, list[z3.DatatypeRef]]:
        """Add a requirement for a peripheral."""
        requirement_name = uniquify(requirement_name, self._consumed_requirement_names)

        peripheral_ref = z3.Const(requirement_name, self.peripheral_enum_sort)

        peripheral_signal_patterns = [coerce_pattern(name) for name in peripheral_signal_names or []]

        pin_refs = []
        for signal_name in peripheral_signal_names or []:
            unique_name = uniquify(f"{requirement_name}-{signal_name}", self._consumed_signal_names)
            self._consumed_signal_names.add(unique_name)
            const = z3.Const(unique_name, self.pin_enum_sort)
            pin_refs.append(const)

        peripheral_predicates = []
        for p_candidate in self.core.peripherals:
            if peripheral_name and coerce_pattern(peripheral_name).match(p_candidate.name) is None:
                continue

            if peripheral_kind and p_candidate.registers.kind != peripheral_kind:
                continue

            candidate_predicates = [peripheral_ref == self.peripheral_enum_members[p_candidate.name]]
            for ref, name, pattern in zip(pin_refs, peripheral_signal_names or [], peripheral_signal_patterns, strict=True):
                if candidate_pins := self._match_pins(
                    lambda p: pattern.match(p.signal) is not None, p_candidate
                ):
                    candidate_predicates.append(_is_one_of_predicate(ref, candidate_pins))
                else:
                    print(f"No signal named {name} found on {p_candidate.name} for {requirement_name}")
                    break  # no pins found for this signal
            else:
                peripheral_predicates.append(z3.And(*candidate_predicates))

        if not peripheral_predicates:
            raise self.InvalidPeripheralError(requirement_name)

        self._peripheral_refs.append(peripheral_ref)
        self._pin_refs.extend(pin_refs)
        self.solver.add(z3.Or(*peripheral_predicates))

        return peripheral_ref, pin_refs

    def reserve_pin(self, pin: str) -> None:
        """Reserve a pin for use in the solution."""
        self._pin_refs.append(self.pin_enum_members[pin])

    def _match_pins(
        self,
        matcher: Callable[[Stm32Model.Core.Peripheral.Pin], bool],
        periperhal: Stm32Model.Core.Peripheral,
    ) -> list[z3.DatatypeRef]:
        return [self.pin_enum_members[pin.pin] for pin in periperhal.pins or [] if matcher(pin)]

    def _force_unique_resources(self) -> None:
        """Demand physical resources are unique."""
        self.solver.add(z3.Distinct(*self._peripheral_refs))
        self.solver.add(z3.Distinct(*self._pin_refs))

    def solve(self) -> z3.ModelRef:
        """Solve the constraints and return a model if a solution is found."""
        self._force_unique_resources()

        if self.solver.check() != z3.sat:
            raise self.NoSolutionError()

        return self.solver.model()

"""Pinout solver for STM32 microcontrollers."""

import re
import typing
from typing import Callable, Iterable  # noqa: UP035

import groupie
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

    class InvalidConfigError(Exception):
        """Raised when a peripheral is not viable for a requirement."""

    class PeripheralDoesNotMatchKindError(InvalidConfigError):
        """Raised when a peripheral does not match the kind of requirement."""

        def __init__(self, requirement_name: str, peripheral_name: str, kind: str):
            self.requirement_name = requirement_name
            self.peripheral_name = peripheral_name
            self.kind = kind

        def __str__(self):
            return f"Peripheral {self.peripheral_name} does not match kind {self.kind} for requirement {self.requirement_name}"

    class PeripheralDoesNotMatchNameError(InvalidConfigError):
        """Raised when a peripheral does not match the name of requirement."""

        def __init__(self, requirement_name: str, peripheral_name: str):
            self.requirement_name = requirement_name
            self.peripheral_name = peripheral_name

        def __str__(self):
            return f"Peripheral {self.peripheral_name} does not match name {self.requirement_name}"

    class NoSignalError(InvalidConfigError):
        """Raised when a pin is not viable for a requirement."""

        def __init__(self, requirement_name: str, peripheral_name: str, signal_name: str):
            self.requirement_name = requirement_name
            self.peripheral_name = peripheral_name
            self.signal_name = signal_name

        def __str__(self):
            return f"No signal named {self.signal_name} found on {self.peripheral_name} for {self.requirement_name}"

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
        *,
        consume_peripheral: bool = True,
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
        collector = groupie.Collector(self.InvalidConfigError)
        for p_candidate in self.core.peripherals:
            with collector:
                if peripheral_name and coerce_pattern(peripheral_name).match(p_candidate.name) is None:
                    raise self.PeripheralDoesNotMatchNameError(requirement_name, p_candidate.name)

                if peripheral_kind and p_candidate.registers.kind != peripheral_kind:
                    raise self.PeripheralDoesNotMatchKindError(requirement_name, p_candidate.name, peripheral_kind)

                candidate_predicates = [peripheral_ref == self.peripheral_enum_members[p_candidate.name]]
                for ref, name, pattern in zip(
                    pin_refs, peripheral_signal_names or [], peripheral_signal_patterns, strict=True
                ):
                    with collector:
                        if candidate_pins := self._match_pins(
                            lambda p: pattern.match(p.signal) is not None, p_candidate
                        ):
                            candidate_predicates.append(_is_one_of_predicate(ref, candidate_pins))
                        else:
                            raise self.NoSignalError(requirement_name, p_candidate.name, name)

                peripheral_predicates.append(z3.And(*candidate_predicates))

        if not peripheral_predicates:
            raise collector.make()

        if consume_peripheral:
            self._peripheral_refs.append(peripheral_ref)

        self._pin_refs.extend(pin_refs)
        self.solver.add(z3.Or(*peripheral_predicates))

        return peripheral_ref, pin_refs

    def reserve_pin(self, requirement_name: str, pin: str | re.Pattern) -> z3.DatatypeRef:
        """Reserve a pin for use in the solution."""
        pattern = coerce_pattern(pin)
        req_name = uniquify(requirement_name, self._consumed_requirement_names)
        ref = z3.Const(req_name, self.pin_enum_sort)
        self.solver.add(
            z3.Or(
                ref == p_enum
                for p_name, p_enum in self.pin_enum_members.items()
                if pattern.match(p_name)
            )
        )
        self._pin_refs.append(ref)

        return ref

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

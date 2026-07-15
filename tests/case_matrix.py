"""Compact execution for pure input-equivalence test matrices."""

import functools
import inspect


def case_matrix(argnames, argvalues, *, ids=None):
    """Run a fixture-free input matrix as one focused pytest item.

    This is intentionally narrower than ``pytest.mark.parametrize``.  It is
    for pure equivalence classes that do not need a fresh fixture lifecycle;
    tests with fixtures must keep normal pytest parametrization.
    """

    if isinstance(argnames, str):
        names = tuple(name.strip() for name in argnames.split(","))
    else:
        names = tuple(argnames)
    cases = tuple(argvalues)

    def decorate(function):
        signature = inspect.signature(function)
        fixture_names = set(signature.parameters) - set(names) - {"self"}
        if fixture_names:
            raise TypeError(
                "case_matrix only supports fixture-free tests; found: "
                + ", ".join(sorted(fixture_names))
            )
        missing = set(names) - set(signature.parameters)
        if missing:
            raise TypeError(
                "case_matrix arguments are absent from the test signature: "
                + ", ".join(sorted(missing))
            )

        remaining_parameters = [
            parameter
            for name, parameter in signature.parameters.items()
            if name not in names
        ]

        @functools.wraps(function)
        def run_matrix(*args, **kwargs):
            failures = []
            for index, raw_values in enumerate(cases):
                values = (
                    (raw_values,) if len(names) == 1 else tuple(raw_values)
                )
                if len(values) != len(names):
                    raise ValueError(
                        "case_matrix value count does not match argument count"
                    )
                case = dict(zip(names, values))
                try:
                    function(*args, **kwargs, **case)
                except Exception as exc:  # pragma: no branch - failure path
                    if callable(ids):
                        label = ids(raw_values)
                    elif ids is not None:
                        label = ids[index]
                    else:
                        label = repr(raw_values)
                    failures.append(
                        "{}: {}: {}".format(
                            label, type(exc).__name__, str(exc)
                        )
                    )

            if failures:
                raise AssertionError(
                    "case matrix failures:\n- " + "\n- ".join(failures)
                )

        run_matrix.__signature__ = signature.replace(
            parameters=remaining_parameters
        )
        return run_matrix

    return decorate

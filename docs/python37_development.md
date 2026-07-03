# Python 3.7 Development

This project defaults to Python 3.7 for local development and test runs.
Use the released `sqlglot==26.9.0`; do not use a local sqlglot checkout.

Create the shared conda environment:

```bash
make env-create
```

The default environment name is `dw-refactor-py37`. Because it is a named
conda environment, the main checkout and all git worktrees use the same Python
runtime.

On Apple Silicon machines, Python 3.7 packages may require the osx-64 solver:

```bash
CONDA_SUBDIR=osx-64 make env-create
```

Update the environment after dependency changes:

```bash
make env-update
```

Run tests with the Python 3.7 environment:

```bash
make test
```

Check the interpreter and required modules without running the full suite:

```bash
make doctor
```

If you need to use a different already-created environment, override the
interpreter explicitly:

```bash
make test PYTHON=/absolute/path/to/python
```

Do not run bare `pytest` in this repository. `pytest` uses whichever executable
appears first on `PATH`, which may be Homebrew Python or another global
installation. The project entrypoints use `python -m pytest` through the
selected interpreter instead.

The Makefile runs repository commands with `PYTHONPATH=src` so the local
`dw_refactor_agent` package is importable under the `src/` layout. Avoid adding
unrelated local checkouts such as `/Users/yulihua/Projects/sqlglot` to
`PYTHONPATH`; they can still shadow pinned dependencies.

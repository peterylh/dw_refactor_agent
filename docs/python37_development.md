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

By default, the Makefile runs commands through the named conda environment and
then executes `$CONDA_PREFIX/bin/python` inside that environment. This keeps the
default portable across machines with different conda install paths, while
avoiding `PATH` shadowing from tools such as pyenv shims or Homebrew Python.

Check the interpreter and required modules without running the full suite:

```bash
make doctor
```

If you need to use a different named conda environment, override the environment
name:

```bash
make test CONDA_ENV=my-py37-env
```

If you need to use a non-conda interpreter or a specific already-created Python,
override the interpreter explicitly:

```bash
make test PYTHON=/absolute/path/to/python
```

If your shell has unrelated conda variables active while using a non-conda
interpreter, disable the conda prefix check:

```bash
make test PYTHON=/absolute/path/to/python EXPECTED_CONDA_ENV=
```

Do not run bare `pytest` in this repository. `pytest` uses whichever executable
appears first on `PATH`, which may be Homebrew Python or another global
installation. The project entrypoints use `python -m pytest` through the
selected interpreter instead.

The Makefile runs repository commands with `PYTHONPATH=src` so the local
`dw_refactor_agent` package is importable under the `src/` layout. Avoid adding
unrelated local checkouts such as `/Users/yulihua/Projects/sqlglot` to
`PYTHONPATH`; they can still shadow pinned dependencies.

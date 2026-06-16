# Python 3.7 Development

This project defaults to Python 3.7 for local development and test runs.
Use the released `sqlglot==26.9.0`; do not use a local sqlglot checkout.

Create a project-local environment:

```bash
CONDA_SUBDIR=osx-64 \
XDG_CACHE_HOME="$PWD/.cache" \
CONDA_PKGS_DIRS="$PWD/.conda-pkgs" \
conda env create --prefix "$PWD/.conda-py37" -f environment-py37.yml
```

On non-Apple-Silicon machines, `CONDA_SUBDIR=osx-64` is usually unnecessary.

Run tests with the Python 3.7 environment:

```bash
PYTHONPATH= ./.conda-py37/bin/python -m pytest -q -m 'not api'
```

The empty `PYTHONPATH=` prevents editable or local checkouts such as
`/Users/yulihua/Projects/sqlglot` from shadowing the pinned package.

# Convert LaravelCollective HTML to Spatie HTML Facade

This script automates migrating from the `Collective\Html\HtmlFacade` (LaravelCollective) to the `Spatie\Html\HtmlFacade` using the `html()` helper.

## Features

- **Automatic replacement** of HTML link calls:
    - `Html::link(...)` → `html()->a(...)`
    - `Html::linkRoute(...)` → `html()->a()->route(...)->html(...)`
    - All other `Html` facade methods → `html()->method(...)`
- **Form conversion**:
    - `Form::open([...])` → `html()->form()->...->open()` with attribute chaining
    - `Form::close()` → `html()->form()->close()`
    - Field helpers (`hidden`, `email`, `password`, `submit`, `select`, `radio`, `checkbox`, `textarea`, `number`, `file`, `date`, `time`, `url`, `search`) become `html()->field(...)` calls with chained attributes
- **Robust argument parsing** that handles nested parentheses, arrays, and string literals without breaking
- **Recursively processes** all `*.php` and `*.blade.php` files in the specified directory

## Requirements

- Python 3.7 or higher
- Standard library modules: `os`, `re`, `sys`, `typing`

## Installation

1. Clone this repository or download the script file (`script.py`).
2. Make the script executable (optional):
   ```bash
   python3 script.py

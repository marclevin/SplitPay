# Introduction
SplitPay is a simple command-line utility for managing shared expenses.
It lets you create groups, add members, record expenses, and track who
owes what, all from your terminal.  
PostgreSQL is used for data storage, SQLAlchemy for ORM, and Alembic for
schema migrations.

---

## Prerequisites

- **Python** 3.11+  
- **PostgreSQL** 14+ (local installation or Docker container)  
- **pip** for installing Python packages

---

## Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/marclevin/SplitPay.git
   cd SplitPay
   ```
2. **Create a virtual environment**

   ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```
4. **Create a `.env` file in the root directory of the project with the following content:**
    ```plaintext
    DB_USERNAME=your_pg_username
    DB_PASSWORD=your_pg_password
    DB_NAME=splitpay
    DB_HOST=localhost  # optional; defaults to localhost
    ```
5. **Initialize the database (Can use a Docker instance as well)**
    ```bash
    alembic upgrade head
    ```
## Usage
All interactions happen through `cli.py`, which uses [Typer](https://typer.tiangolo.com/)
```bash
python cli.py --help            # Top‑level help
python cli.py group --help      # Help for group commands
python cli.py member --help     # Help for member commands
```
### Common Commands
- **Create a group and set it as active**:
    ```bash
    python cli.py group create "Group Name"
    ```
- **Add a member to the active group**:
    ```bash
    python cli.py member add "Member Name"
    ```
- **Record an expense in the active group**:
    ```bash
    python cli.py expense add
   ```
- **View who owes what in the active group**:
    ```bash
    python cli.py split show
    ```
Each command has its own set of options and flags, which you can explore
by running the help command for that specific command.

## Development notes
- **Testing**: Uses `unitest` for unit tests. Run tests with:
    ```bash
    python -m unittest discover -s tests
    ```
- **Coverage**: We use `coverage.py` to measure test coverage. Run:
    ```bash
    coverage run -m unittest discover -s tests
    coverage report -m
    ```
- **Temporary session**: Temporary session data (which group is active) is stored in `.eco_session.` Deleting this file resets the current session.


  

   




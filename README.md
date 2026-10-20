<div align="center">

# 💰 Finance Bot

### Turn a bank statement PDF into a clear spending dashboard

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-Aiven-4479A1?logo=mysql&logoColor=white)
![Status](https://img.shields.io/badge/Status-Runs%20locally-lightgrey)

</div>

---

## Overview

Upload a bank statement PDF and get an instant breakdown of your spending, automatically categorized, with charts and downloadable reports. Runs locally on your machine.

## Features

- 📄 Extracts transactions and account details directly from a bank statement PDF
- 🏷️ Categorizes each transaction using 500+ keyword rules plus fuzzy matching for unknown merchants
- 🤝 Separates person-to-person transfers from real merchant spending
- 📊 Web dashboard with spending summary, category breakdown, and charts
- 📑 Downloadable Excel and PDF reports
- 🗂️ Statement history in a sidebar: reopen or delete past statements
- ☁️ Every statement is saved to a MySQL database

## Tech Stack

Python · FastAPI · HTML/CSS/JS · MySQL · pandas · pdfplumber · reportlab · matplotlib · rapidfuzz

## How Categorization Works

1. Checks the merchant name against 500+ known keywords
2. Falls back to fuzzy matching for anything not in the list
3. "Payment from/for" patterns without a merchant match are labeled Person Transfer
4. Anything left over is marked Uncategorized

## Project Structure

1. Checks the merchant name against 500+ known keywords
2. Falls back to fuzzy matching for anything not in the list
3. "Payment from/for" patterns without a merchant match → labeled Person Transfer
4. Anything left over → Uncategorized

finance-bot/
├── src/
│ ├── data_loader.py # Loads and cleans the statement
│ ├── pdf_parser.py # Extracts transactions + account info from PDF
│ ├── categorizer.py # Assigns categories
│ ├── categories.py # Keyword list
│ ├── visualizer.py # Builds charts
│ ├── report_generator.py # Builds Excel/PDF reports
│ ├── database.py # Database models
│ ├── db_operations.py # Saves data to the database
│ └── api.py # FastAPI app
├── static/ # Frontend (landing page, app UI)
├── certs/ # DB SSL certificate (if your MySQL host requires it)
├── main.py # CLI entry point
└── requirements.txt


## Getting Started

```bash
git clone https://github.com/kalpeshb2004/Personal-AI-Finance-Assistance.git
cd Personal-AI-Finance-Assistance
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=your_db_host
DB_PORT=your_db_port
DB_NAME=your_db_name


Create the database tables:

```bash
python src/database.py
```

**Run the web app:**

```bash
uvicorn src.api:app --reload
```

Then open `http://127.0.0.1:8000`

**Or run from the command line:**

```bash
python main.py --file "path/to/statement.pdf"
```

## Roadmap

- [ ] Login/signup
- [ ] Editable transaction categories
- [ ] Budgeting and savings goals
- [ ] Deployment

---

<div align="center">Made by <a href="https://github.com/kalpeshb2004">Kalpesh Bhure</a></div>



import os
import shutil

import pandas as pd
from fastapi import Cookie, Depends, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.auth import (
    create_token,
    get_current_user,
    get_optional_user,
    hash_password,
    verify_password,
)
from src.categorizer import categorize_dataframe
from src.data_loader import load_and_clean
from src.database import SessionLocal, Statement, Transaction, User, get_db
from src.db_operations import save_to_database
from src.pdf_parser import extract_account_details
from src.report_generator import generate_pdf_report
from src.visualizer import plot_category_bar, plot_category_pie

# ---------- App banao (SIRF EK BAAR) ----------
app = FastAPI(title="Personal Finance Bot API")

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files serve karo
app.mount("/static", StaticFiles(directory="static"), name="static")

UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------- Public pages ----------

@app.get("/")
def root():
    return FileResponse("static/landing.html")


@app.get("/login")
def login_page():
    return FileResponse("static/login.html")


@app.get("/signup")
def signup_page():
    return FileResponse("static/signup.html")


# ---------- Protected page ----------

@app.get("/app")
def app_page(user: User | None = Depends(get_optional_user)):
    if not user:
        return RedirectResponse("/login")
    return FileResponse("static/index.html", headers={"Cache-Control": "no-store"})


# ---------- Auth API ----------

class SignupIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def set_session(response: Response, user_id: int):
    response.set_cookie(
        key="access_token",
        value=create_token(user_id),
        httponly=True,
        samesite="lax",
        secure=False,  # deploy ke baad True karna
        max_age=60 * 60 * 24,
    )


@app.post("/api/signup")
def signup(data: SignupIn, response: Response, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered. Log in instead.")
    user = User(
        name=data.name.strip(),
        email=email,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    set_session(response, user.id)
    return {"ok": True}


@app.post("/api/login")
def login(data: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    set_session(response, user.id)
    return {"ok": True}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"ok": True}


@app.get("/api/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "name": user.name, "email": user.email}


# ---------- Data routes (login required) ----------

REPORT_FILES = {
    "category_pie.png",
    "category_bar.png",
    "finance_report.pdf",
    "finance_report.xlsx",
}


@app.get("/reports/{filename}")
def report_file(filename: str, current_user: User = Depends(get_current_user)):
    if filename not in REPORT_FILES:
        raise HTTPException(status_code=404, detail="File not found")
    path = os.path.join("reports", filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, headers={"Cache-Control": "no-store"})


@app.get("/download-report")
def download_report(current_user: User = Depends(get_current_user)):
    file_path = "reports/finance_report.pdf"
    if os.path.exists(file_path):
        return FileResponse(file_path, filename="finance_report.pdf", media_type="application/pdf")
    raise HTTPException(status_code=404, detail="Report not found")


@app.post("/upload")
async def upload_statement(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        df = load_and_clean(file_path)
    except Exception:
        raise HTTPException(
            status_code=422,
            detail="Could not read this PDF. Make sure it's a valid bank statement.",
        )

    if df.empty or len(df) == 0:
        raise HTTPException(status_code=422, detail="No transactions found in this statement.")

    try:
        df = categorize_dataframe(df)

        plot_category_pie(df)
        plot_category_bar(df)

        account_details = extract_account_details(file_path)
        generate_pdf_report(df, account_details)
        save_to_database(current_user.id, account_details, df, file.filename)

        spend_df = df[(df["Withdrawal"] > 0) & (df["Category"] != "Person Transfer")]
        total_spend = float(spend_df["Withdrawal"].sum())
        category_totals = spend_df.groupby("Category")["Withdrawal"].sum().to_dict()

        transfer_df = df[df["Category"] == "Person Transfer"]
        total_sent = float(transfer_df["Withdrawal"].sum())
        total_received = float(transfer_df["Deposit"].sum())

        return {
            "success": True,
            "account_details": account_details,
            "summary": {
                "total_spend": total_spend,
                "person_transfer_sent": total_sent,
                "person_transfer_received": total_received,
                "total_transactions": len(df),
            },
            "category_breakdown": category_totals,
            "transactions": df[
                ["Date", "Description", "Category", "Withdrawal", "Deposit", "Balance"]
            ]
            .astype(str)
            .to_dict(orient="records"),
        }

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while processing this statement. Please try again.",
        )


@app.get("/history")
def get_history(current_user: User = Depends(get_current_user)):
    session = SessionLocal()
    try:
        statements = (
            session.query(Statement)
            .filter(Statement.user_id == current_user.id)
            .order_by(Statement.uploaded_at.desc())
            .all()
        )

        result = []
        for stmt in statements:
            total_spend = (
                session.query(func.coalesce(func.sum(Transaction.withdrawal), 0))
                .filter(Transaction.statement_id == stmt.id)
                .filter(Transaction.category != "Person Transfer")
                .filter(Transaction.withdrawal > 0)
                .scalar()
            )

            result.append(
                {
                    "statement_id": stmt.id,
                    "file_name": stmt.file_name,
                    "uploaded_at": stmt.uploaded_at.strftime("%d %b %Y, %I:%M %p"),
                    "user_name": stmt.holder_name or current_user.name,
                    "total_transactions": stmt.total_transactions,
                    "total_spend": float(total_spend or 0),
                }
            )

        return {"history": result}
    finally:
        session.close()


@app.get("/statement/{statement_id}")
def get_statement(statement_id: int, current_user: User = Depends(get_current_user)):
    session = SessionLocal()
    try:
        statement = (
            session.query(Statement)
            .filter(Statement.id == statement_id, Statement.user_id == current_user.id)
            .first()
        )
        if not statement:
            raise HTTPException(status_code=404, detail="Statement not found")

        transactions = (
            session.query(Transaction).filter(Transaction.statement_id == statement_id).all()
        )

        # DB rows se pandas DataFrame banao (jaisa fresh upload mein banta hai)
        rows = []
        for t in transactions:
            rows.append(
                {
                    "Date": t.date,
                    "Description": t.description,
                    "CleanMerchant": t.clean_merchant,
                    "Category": t.category,
                    "Withdrawal": t.withdrawal,
                    "Deposit": t.deposit,
                    "Balance": t.balance,
                }
            )
        df = pd.DataFrame(rows)

        account_details = {
            "Name": statement.holder_name,
            "AccountNo": statement.account_no,
            "BankName": statement.bank_name,
            "Branch": statement.branch,
            "IFSC": statement.ifsc,
            "Address": statement.address,
        }

        # Charts + PDF isi statement ke data se dobara banao
        plot_category_pie(df)
        plot_category_bar(df)
        generate_pdf_report(df, account_details)

        spend_df = df[(df["Withdrawal"] > 0) & (df["Category"] != "Person Transfer")]
        total_spend = float(spend_df["Withdrawal"].sum())
        category_totals = spend_df.groupby("Category")["Withdrawal"].sum().to_dict()

        transfer_df = df[df["Category"] == "Person Transfer"]
        total_sent = float(transfer_df["Withdrawal"].sum())
        total_received = float(transfer_df["Deposit"].sum())

        return {
            "success": True,
            "account_details": account_details,
            "summary": {
                "total_spend": total_spend,
                "person_transfer_sent": total_sent,
                "person_transfer_received": total_received,
                "total_transactions": len(df),
            },
            "category_breakdown": category_totals,
        }
    finally:
        session.close()


@app.delete("/statement/{statement_id}")
def delete_statement(statement_id: int, current_user: User = Depends(get_current_user)):
    session = SessionLocal()
    try:
        statement = (
            session.query(Statement)
            .filter(Statement.id == statement_id, Statement.user_id == current_user.id)
            .first()
        )
        if not statement:
            raise HTTPException(status_code=404, detail="Statement not found")

        # Pehle transactions delete karo (foreign key constraint ki wajah se, pehle child rows)
        session.query(Transaction).filter(Transaction.statement_id == statement_id).delete()

        # Fir statement delete karo
        session.query(Statement).filter(Statement.id == statement_id).delete()

        session.commit()
        return {"success": True, "message": f"Statement {statement_id} deleted"}
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        raise HTTPException(status_code=500, detail="Could not delete this statement.")
    finally:
        session.close()
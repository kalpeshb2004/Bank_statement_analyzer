from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import shutil
import os
import pandas as pd

from src.data_loader import load_and_clean
from src.categorizer import categorize_dataframe
from src.visualizer import plot_category_pie, plot_category_bar
from src.report_generator import generate_pdf_report
from src.pdf_parser import extract_account_details
from src.db_operations import save_to_database

from src.database import SessionLocal, User, Statement, Transaction

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
app.mount("/reports", StaticFiles(directory="reports"), name="reports")

UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------- Routes ----------

@app.get("/")
def root():
    return FileResponse("static/index.html")


@app.get("/download-report")
def download_report():
    file_path = "reports/finance_report.pdf"
    if os.path.exists(file_path):
        return FileResponse(file_path, filename="finance_report.pdf", media_type="application/pdf")
    raise HTTPException(status_code=404, detail="Report not found")


@app.post("/upload")
async def upload_statement(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        df = load_and_clean(file_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail="Could not read this PDF. Make sure it's a valid bank statement.")
    
    if df.empty or len(df) == 0:
        raise HTTPException(status_code=422, detail="No transactions found in this statement.")
    
    try:
        df = categorize_dataframe(df)
        
        plot_category_pie(df)
        plot_category_bar(df)
        
        account_details = extract_account_details(file_path)
        generate_pdf_report(df, account_details)
        save_to_database(account_details, df, file.filename)
        
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
            "transactions": df[["Date", "Description", "Category", "Withdrawal", "Deposit", "Balance"]].astype(str).to_dict(orient="records"),
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail="Something went wrong while processing this statement. Please try again.")

@app.get("/history")
def get_history():
    session = SessionLocal()
    try:
        statements = (
            session.query(Statement, User)
            .join(User, Statement.user_id == User.id)
            .order_by(Statement.uploaded_at.desc())
            .all()
        )
        
        result = []
        for stmt, user in statements:
            spend = (
                session.query(Transaction)
                .filter(Transaction.statement_id == stmt.id)
                .filter(Transaction.category != "Person Transfer")
                .filter(Transaction.withdrawal > 0)
                .all()
            )
            total_spend = sum(t.withdrawal for t in spend)
            
            result.append({
                "statement_id": stmt.id,
                "file_name": stmt.file_name,
                "uploaded_at": stmt.uploaded_at.strftime("%d %b %Y, %I:%M %p"),
                "user_name": user.name,
                "total_transactions": stmt.total_transactions,
                "total_spend": total_spend,
            })
        
        return {"history": result}
    finally:
        session.close()

@app.get("/statement/{statement_id}")
def get_statement(statement_id: int):
    session = SessionLocal()
    try:
        statement = session.query(Statement).filter(Statement.id == statement_id).first()
        if not statement:
            raise HTTPException(status_code=404, detail="Statement not found")
        
        user = session.query(User).filter(User.id == statement.user_id).first()
        transactions = session.query(Transaction).filter(Transaction.statement_id == statement_id).all()
        
        # DB rows se pandas DataFrame banao (jaisa fresh upload mein banta hai)
        rows = []
        for t in transactions:
            rows.append({
                "Date": t.date,
                "Description": t.description,
                "CleanMerchant": t.clean_merchant,
                "Category": t.category,
                "Withdrawal": t.withdrawal,
                "Deposit": t.deposit,
                "Balance": t.balance,
            })
        df = pd.DataFrame(rows)
        
        account_details = {
            "Name": user.name,
            "AccountNo": user.account_no,
            "BankName": user.bank_name,
            "Branch": user.branch,
            "IFSC": user.ifsc,
            "Address": user.address,
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
def delete_statement(statement_id: int):
    session = SessionLocal()
    try:
        statement = session.query(Statement).filter(Statement.id == statement_id).first()
        if not statement:
            raise HTTPException(status_code=404, detail="Statement not found")
        
        # Pehle transactions delete karo (foreign key constraint ki wajah se, pehle child rows)
        session.query(Transaction).filter(Transaction.statement_id == statement_id).delete()
        
        # Fir statement delete karo
        session.query(Statement).filter(Statement.id == statement_id).delete()
        
        session.commit()
        return {"success": True, "message": f"Statement {statement_id} deleted"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
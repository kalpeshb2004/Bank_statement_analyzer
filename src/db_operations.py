from src.database import SessionLocal, Statement, Transaction


def save_to_database(user_id, account_details, df, file_name):
    """Statement ko logged-in user (user_id) ke naam se save karta hai.

    Bank account ki details (naam, account no, IFSC...) ab har statement ke
    saath save hoti hain, kyunki ek user alag-alag accounts ke statements
    upload kar sakta hai.
    """
    session = SessionLocal()

    try:
        statement = Statement(
            user_id=user_id,
            file_name=file_name,
            total_transactions=len(df),
            holder_name=account_details.get("Name"),
            account_no=account_details.get("AccountNo"),
            bank_name=account_details.get("BankName"),
            branch=account_details.get("Branch"),
            ifsc=account_details.get("IFSC"),
            address=account_details.get("Address"),
        )
        session.add(statement)
        session.flush()  # statement.id generate karwao

        for _, row in df.iterrows():
            txn = Transaction(
                statement_id=statement.id,
                date=row["Date"],
                description=row["Description"],
                clean_merchant=row["CleanMerchant"],
                category=row["Category"],
                withdrawal=row["Withdrawal"],
                deposit=row["Deposit"],
                balance=row["Balance"],
                match_type=row.get("MatchType", ""),
            )
            session.add(txn)

        session.commit()
        print(f"Saved to DB: User ID {user_id}, Statement ID {statement.id}, {len(df)} transactions")
        return statement.id

    except Exception as e:
        session.rollback()
        print(f"Database save error: {e}")
        raise
    finally:
        session.close()
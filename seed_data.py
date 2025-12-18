import csv
from datetime import datetime

from db import db
from models import Customer, Message
from uregency_analyzer import get_urgency_score

CSV_PATH = "data/GeneralistRails_Project_MessageData.csv"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def seed_from_csv():
    print("Starting database seeding")

    total_rows = 0
    inserted_messages = 0
    created_customers = 0

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        total_rows = len(reader)

        print(f"CSV loaded with {total_rows} rows")

        for idx, row in enumerate(reader, start=1):
            customer_id = int(row["User ID"])
            message_body = row["Message Body"].strip()
            timestamp = datetime.strptime(row["Timestamp (UTC)"], TIMESTAMP_FORMAT)

            # ---- Customer ----
            customer = db.session.get(Customer, customer_id)
            if not customer:
                customer = Customer(id=customer_id)
                db.session.add(customer)
                created_customers += 1

            # ---- Urgency scoring ----
            urgency_score = get_urgency_score(message_body, use_llm=True)

            # ---- Message ----
            message = Message(
                customer_id=customer_id,
                message_body=message_body,
                timestamp=timestamp,
                urgency_score=urgency_score,
                status="open"
            )

            db.session.add(message)
            inserted_messages += 1

            # ---- Progress log ----
            if idx % 10 == 0 or idx == total_rows:
                print(
                    f"Processed {idx}/{total_rows} | "
                    f"Messages: {inserted_messages} | "
                    f"Customers: {created_customers}"
                )

    db.session.commit()
    print("Seeding completed successfully")

    return {
        "rows": total_rows,
        "messages": inserted_messages,
        "customers": created_customers,
    }

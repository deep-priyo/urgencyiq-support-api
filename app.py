import os
from flask import Flask,request, jsonify
from datetime import datetime

from flask_cors import CORS
from sqlalchemy import desc

from seed_data import seed_from_csv
from uregency_analyzer import get_urgency_score
from models import Customer, Message, AgentReply
from db import db

app = Flask(__name__)
CORS(app)


DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
else:
    # Local development fallback
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DB_PATH = os.path.join(BASE_DIR, "instance", "app.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"


app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

@app.route("/api/messages/send", methods=["POST"])
def create_message():
    # ---------- READ INPUT (JSON or FORM) ----------
    if request.is_json:
        data = request.get_json()
        user_id = data.get("user_id")
        message_text = data.get("message")
    else:
        user_id = request.form.get("user_id")
        message_text = request.form.get("message")

    # ---------- VALIDATION ----------
    if not user_id or not message_text:
        return jsonify({
            "error": "user_id and message are required"
        }), 400

    user_id = int(user_id)
    message_text = message_text.strip()

    # ---------- CUSTOMER ----------
    customer = db.session.get(Customer, user_id)
    if not customer:
        customer = Customer(id=user_id)
        db.session.add(customer)

    # ---------- URGENCY ----------
    urgency = get_urgency_score(message_text, use_llm=True)

    # ---------- MESSAGE ----------
    message = Message(
        customer_id=user_id,
        message_body=message_text,
        timestamp=datetime.utcnow(),
        urgency_score=urgency,
        status="open"
    )

    db.session.add(message)
    db.session.commit()

    # ---------- RESPONSE ----------
    return jsonify({
        "success": True,
        "message_id": message.id,
        "urgency": urgency
    }), 201

@app.route("/api/messages/<int:message_id>/reply", methods=["POST"])
def reply_to_message(message_id):
    if request.is_json:
        data = request.get_json()
        agent_name = data.get("agent_name")
        reply_text = data.get("reply")
    else:
        agent_name = request.form.get("agent_name")
        reply_text = request.form.get("reply")

    if not agent_name or not reply_text:
        return jsonify({
            "error": "agent_name and reply are required"
        }), 400

    reply = AgentReply(
        message_id=message_id,
        agent_name=agent_name.strip(),
        reply_text=reply_text.strip()
    )

    db.session.add(reply)
    db.session.commit()

    return jsonify({"success": True}), 201

@app.route("/api/messages/<int:message_id>/resolve", methods=["POST"])
def resolve_message(message_id):
    message = db.session.get(Message, message_id)

    if not message:
        return jsonify({"error": "Message not found"}), 404

    message.status = "resolved"
    db.session.commit()

    return jsonify({"success": True})
@app.route("/api/messages", methods=["GET"])
def get_messages():
    sort = request.args.get("sort", "urgency")
    user_id = request.args.get("user_id")
    search = request.args.get("search")
    status = request.args.get("status", "open")

    query = Message.query.filter(Message.status == status)

    if user_id:
        query = query.filter(Message.customer_id == int(user_id))

    if search:
        query = query.filter(Message.message_body.ilike(f"%{search}%"))

    if sort == "time":
        query = query.order_by(desc(Message.timestamp))
    else:
        query = query.order_by(
            desc(Message.urgency_score),
            desc(Message.timestamp)
        )

    messages = query.all()

    response = []
    for m in messages:
        response.append({
            "id": m.id,
            "customer_id": m.customer_id,
            "message": m.message_body,
            "timestamp": m.timestamp.isoformat(),
            "urgency": m.urgency_score,
            "status": m.status,
            "replies": [
                {
                    "agent_name": r.agent_name,
                    "reply": r.reply_text,
                    "timestamp": r.timestamp.isoformat()
                }
                for r in m.replies
            ]
        })

    return jsonify(response)


@app.route("/admin/seed", methods=["POST"])
def seed_database():
    try:
        result = seed_from_csv()
        return jsonify({
            "success": True,
            "seeded": result
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        print("Tables created successfully")

    app.run(debug=True)

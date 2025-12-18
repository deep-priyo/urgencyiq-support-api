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
    DB_DIR = os.path.join(BASE_DIR, "instance")

    # Create instance directory if it doesn't exist
    os.makedirs(DB_DIR, exist_ok=True)

    DB_PATH = os.path.join(DB_DIR, "app2.db")
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
            "assigned_to": m.assigned_to,  # NEW
            "assigned_at": m.assigned_at.isoformat() if m.assigned_at else None,  # NEW
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

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})


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


@app.route("/api/customers/<int:customer_id>", methods=["GET"])
def get_customer_info(customer_id):
    customer = db.session.get(Customer, customer_id)

    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    # Get customer's message history
    messages = Message.query.filter_by(customer_id=customer_id).all()

    return jsonify({
        "id": customer.id,
        "total_messages": len(messages),
        "open_messages": sum(1 for m in messages if m.status == "open"),
        "resolved_messages": sum(1 for m in messages if m.status == "resolved"),
        "avg_urgency": sum(m.urgency_score for m in messages) / len(messages) if messages else 0,
        "first_contact": min(m.timestamp for m in messages).isoformat() if messages else None,
        "last_contact": max(m.timestamp for m in messages).isoformat() if messages else None,
    })


@app.route("/api/messages/<int:message_id>/assign", methods=["POST"])
def assign_message(message_id):
    """Assign a message to an agent"""
    data = request.get_json() if request.is_json else request.form
    agent_name = data.get("agent_name")

    if not agent_name:
        return jsonify({"error": "agent_name is required"}), 400

    message = db.session.get(Message, message_id)

    if not message:
        return jsonify({"error": "Message not found"}), 404

    # Assign the message
    message.assigned_to = agent_name.strip()
    message.assigned_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "success": True,
        "assigned_to": message.assigned_to,
        "assigned_at": message.assigned_at.isoformat()
    })


@app.route("/api/messages/<int:message_id>/unassign", methods=["POST"])
def unassign_message(message_id):
    """Unassign a message from an agent"""
    message = db.session.get(Message, message_id)

    if not message:
        return jsonify({"error": "Message not found"}), 404

    message.assigned_to = None
    message.assigned_at = None
    db.session.commit()

    return jsonify({"success": True})


if __name__ == "__main__":
    with app.app_context():
        print("Creating database tables if not present...")
        db.create_all()
        print("Database ready")

    app.run(host="0.0.0.0", port=5000)

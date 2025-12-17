from datetime import datetime
from db import db

class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    message_body = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime)
    urgency_score = db.Column(db.Float)
    status = db.Column(db.String(20), default="open")

    replies = db.relationship("AgentReply", backref="message", lazy=True)



class AgentReply(db.Model):
    __tablename__ = "agent_replies"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(
        db.Integer,
        db.ForeignKey("messages.id"),
        nullable=False
    )
    agent_name = db.Column(db.String(50), nullable=False)
    reply_text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

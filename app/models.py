from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
import datetime

Base = declarative_base()


class Group(Base):
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    members = relationship("Member", back_populates="group", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="group", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="group", cascade="all, delete-orphan")


class Member(Base):
    __tablename__ = 'members'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"))
    color = Column(String, nullable=True)  # Optional color for display purposes

    group = relationship("Group", back_populates="members")
    expenses_paid = relationship("Expense", back_populates="payer", foreign_keys='Expense.paid_by_id')
    splits = relationship("ExpenseSplit", back_populates="member")
    payments_sent = relationship("Payment", back_populates="payer", foreign_keys='Payment.from_id')
    payments_received = relationship("Payment", back_populates="recipient", foreign_keys='Payment.to_id')


class Expense(Base):
    __tablename__ = 'expenses'

    id = Column(Integer, primary_key=True)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(Date, default=datetime.date.today)

    paid_by_id = Column(Integer, ForeignKey("members.id"))
    group_id = Column(Integer, ForeignKey("groups.id"))

    payer = relationship("Member", back_populates="expenses_paid")
    group = relationship("Group", back_populates="expenses")
    splits = relationship("ExpenseSplit", back_populates="expense")


class ExpenseSplit(Base):
    __tablename__ = 'expense_splits'

    id = Column(Integer, primary_key=True)
    expense_id = Column(Integer, ForeignKey("expenses.id"))
    member_id = Column(Integer, ForeignKey("members.id"))
    share_amount = Column(Float, nullable=False)

    expense = relationship("Expense", back_populates="splits")
    member = relationship("Member", back_populates="splits")


class Payment(Base):
    __tablename__ = 'payments'

    id = Column(Integer, primary_key=True)
    from_id = Column(Integer, ForeignKey("members.id"))
    to_id = Column(Integer, ForeignKey("members.id"))
    amount = Column(Float, nullable=False)
    date = Column(Date, default=datetime.date.today)
    group_id = Column(Integer, ForeignKey("groups.id"))

    payer = relationship("Member", foreign_keys=[from_id], back_populates="payments_sent")
    recipient = relationship("Member", foreign_keys=[to_id], back_populates="payments_received")
    group = relationship("Group", back_populates="payments")

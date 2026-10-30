from sqlalchemy import (Column, Integer, String, Boolean, DateTime,ForeignKey, Numeric, Enum as SQLEnum, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .database import Base

class AccountTypeEnum(enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"
    CASH = "CASH"
    SAVINGS = "SAVINGS"
    INVESTMENT = "INVESTMENT"
    WALLET = "WALLET"
    OTHER = "OTHER"

class ConceptTypeEnum(enum.Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"

class TransactionTypeEnum(enum.Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"

class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    legal_name = Column(String)
    tax_id = Column(String)
    email = Column(String)
    phone = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    users = relationship("CompanyUser", back_populates="company")
    accounts = relationship("Account", back_populates="company")
    concepts = relationship("Concept", back_populates="company")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    email_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    companies = relationship("CompanyUser", back_populates="user")
    transactions = relationship("Transaction", back_populates="captured_by_user")

class CompanyUser(Base):
    __tablename__ = "company_users"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    company = relationship("Company", back_populates="users")
    user = relationship("User", back_populates="companies")

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    account_type = Column(SQLEnum(AccountTypeEnum), nullable=False)
    name = Column(String, nullable=False)
    bank_name = Column(String)
    account_number = Column(String)
    clabe = Column(String)
    card_last_digits = Column(String)
    short_description = Column(String)
    long_description = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    company = relationship("Company", back_populates="accounts")
    concepts = relationship("AccountConcept", back_populates="account")
    transactions = relationship("Transaction", back_populates="account")

class Concept(Base):
    __tablename__ = "concepts"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    concept_type = Column(SQLEnum(ConceptTypeEnum), nullable=False)
    name = Column(String, nullable=False)
    short_description = Column(String)
    long_description = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    company = relationship("Company", back_populates="concepts")
    accounts = relationship("AccountConcept", back_populates="concept")

class AccountConcept(Base):
    __tablename__ = "account_concepts"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    concept_id = Column(Integer, ForeignKey("concepts.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    account = relationship("Account", back_populates="concepts")
    concept = relationship("Concept", back_populates="accounts")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    concept_id = Column(Integer, ForeignKey("concepts.id"))
    transaction_type = Column(SQLEnum(TransactionTypeEnum), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    transaction_date = Column(DateTime, default=datetime.utcnow)
    captured_at = Column(DateTime, default=datetime.utcnow)
    captured_by = Column(Integer, ForeignKey("users.id"))
    short_description = Column(String)
    long_description = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    account = relationship("Account", back_populates="transactions")
    concept = relationship("Concept")
    captured_by_user = relationship("User", back_populates="transactions")

# Implementación de roles

class Role(Base):
    __tablename__="roles"
    id = Column(Integer, primary_key=True, index=True)
    code= Column(String(50), unique=True, nullable=False)
    name= Column(String(100), nullable=False)
    description= Column(String(255))
    is_active = Column(Boolean, nullable=False, default=True)

class Permission(Base):
    __tablename__ = "permissions"
    id = Column(Integer, primary_key=True, index=True)
    code= Column(String(50), unique=True, nullable=False)
    name= Column(String(100), nullable=False)
    description= Column(String(255))
    is_active = Column(Boolean, nullable=False, default=True)



# Relación entre roles y permisos 

class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, index=True)

    role_id = Column(
        Integer,
        ForeignKey("roles.id"),
        nullable=False
    )

    permission_id = Column(
        Integer,
        ForeignKey("permissions.id"),
        nullable=False
    )

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("role_id","permission_id",name="uq_role_permission"
        ),
    )

    role = relationship("Role")
    permission = relationship("Permission")


# Relación entre membresías y roles 

class CompanyUserRole(Base):
    __tablename__ = "company_user_roles"

    id = Column(Integer, primary_key=True, index=True)

    company_user_id = Column(
        Integer,
        ForeignKey("company_users.id"),
        nullable=False
    )

    role_id = Column(
        Integer,
        ForeignKey("roles.id"),
        nullable=False
    )

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("company_user_id","role_id",name="uq_company_user_role"
        ),
    )

    company_user = relationship("CompanyUser")
    role = relationship("Role")

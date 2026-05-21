from enum import Enum

class ProviderStatus(str, Enum):
    approved = "approved"
    pending  = "pending"
    rejected = "rejected"

class UserRole(str, Enum):
    provider = "provider"
    customer = "customer"
    admin = "admin"
    
class BookingStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    DISPUTED = "disputed"

class PaymentMethod(str, Enum):
    CASH = "cash"
    CARD = "card"
    DIGITAL_WALLET = "digital_wallet"
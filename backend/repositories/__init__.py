from backend.repositories.base import GenericRepository
from backend.repositories.lead_repository import LeadRepository
from backend.repositories.client_repository import ClientRepository
from backend.repositories.property_repository import PropertyRepository
from backend.repositories.deal_repository import DealRepository
from backend.repositories.document_repository import DocumentRepository
from backend.repositories.task_repository import TaskRepository
from backend.repositories.communication_repository import CommunicationRepository
from backend.repositories.notification_repository import NotificationRepository
from backend.repositories.user import UserRepository

__all__ = [
    "GenericRepository",
    "LeadRepository",
    "ClientRepository",
    "PropertyRepository",
    "DealRepository",
    "DocumentRepository",
    "TaskRepository",
    "CommunicationRepository",
    "NotificationRepository",
    "UserRepository",
]
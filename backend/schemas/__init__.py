from backend.schemas.lead import LeadCreate, LeadUpdate, LeadResponse
from backend.schemas.client import ClientCreate, ClientUpdate, ClientResponse
from backend.schemas.property import PropertyCreate, PropertyUpdate, PropertyResponse
from backend.schemas.deal import DealCreate, DealUpdate, DealResponse
from backend.schemas.task import TaskCreate, TaskUpdate, TaskResponse

__all__ = [
    "LeadCreate", "LeadUpdate", "LeadResponse",
    "ClientCreate", "ClientUpdate", "ClientResponse",
    "PropertyCreate", "PropertyUpdate", "PropertyResponse",
    "DealCreate", "DealUpdate", "DealResponse",
    "TaskCreate", "TaskUpdate", "TaskResponse",
]

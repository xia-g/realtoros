"""Main API router — aggregates all route modules."""

from fastapi import APIRouter

from backend.api.clients import router as clients_router
from backend.api.properties import router as properties_router
from backend.api.deals import router as deals_router
from backend.api.users import router as users_router
from backend.api.routes.leads import router as leads_router
from backend.api.routes.tasks import router as tasks_router
from backend.api.routes.documents import router as documents_router
from backend.api.routes.notifications import router as notifications_router
from backend.api.routes.system_jobs import router as system_jobs_router
from backend.api.routes.knowledge import router as knowledge_router
from backend.api.routes.knowledge_sessions import router as sessions_router
from backend.api.routes.platform_settings import router as platform_router
from backend.api.routes.auth import router as auth_router
from backend.api.routes.companies import router as companies_router
from backend.api.routes.uploads import router as uploads_router
from backend.api.routes.obligations import router as obligations_router
from backend.api.routes.promote_to_deal import router as promote_router, requirements_router, timeline_router
from backend.api.routes.deal_resolution import router as resolution_router
from backend.accounting.api.routes import router as accounting_router
from backend.accounting.ledger.api.routes import router as ledger_router
from backend.accounting.tax.api.routes import router as tax_router
from backend.accounting.report.routes import router as report_router
from backend.accounting.reconciliation.routes import router as reconciliation_router
from backend.accounting.control.routes import router as control_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(clients_router, prefix="/clients", tags=["Clients"])
api_router.include_router(properties_router, prefix="/properties", tags=["Properties"])
api_router.include_router(deals_router, prefix="/deals", tags=["Deals"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(leads_router, prefix="/leads", tags=["Leads"])
api_router.include_router(tasks_router, prefix="/tasks", tags=["Tasks"])
api_router.include_router(documents_router, prefix="/documents", tags=["Documents"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(system_jobs_router, prefix="/jobs", tags=["System Jobs"])
api_router.include_router(knowledge_router, prefix="/knowledge", tags=["Knowledge"])
api_router.include_router(sessions_router, prefix="/agent/sessions", tags=["Knowledge Sessions"])
api_router.include_router(platform_router, prefix="/platform", tags=["Platform"])
api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(companies_router, prefix="", tags=["Companies"])
api_router.include_router(uploads_router, prefix="", tags=["Uploads"])
api_router.include_router(obligations_router, prefix="", tags=["Obligations"])
api_router.include_router(promote_router, prefix="", tags=["Document→Deal"])
api_router.include_router(requirements_router, prefix="", tags=["Deal Requirements"])
api_router.include_router(timeline_router, prefix="", tags=["Deal Timeline"])
api_router.include_router(resolution_router, prefix="", tags=["Deal Resolution"])
api_router.include_router(accounting_router, prefix="", tags=["Accounting"])
api_router.include_router(ledger_router, prefix="", tags=["Ledger"])
api_router.include_router(tax_router, prefix="", tags=["Tax"])
api_router.include_router(report_router, prefix="", tags=["Reports"])
api_router.include_router(reconciliation_router, prefix="", tags=["Reconciliation"])
api_router.include_router(control_router, prefix="", tags=["Control"])

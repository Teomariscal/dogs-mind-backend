# Importar modelos para que SQLAlchemy los registre en Base.metadata.
# Orden importante: Delegation antes que User porque User.delegation_id es FK
# hacia delegations.id (SQLAlchemy resuelve la referencia por nombre de tabla,
# pero ayuda mantener el orden topológico para legibilidad).
from app.models.delegation import Delegation
from app.models.user import User
from app.models.payment import Payment
from app.models.safety_log import SafetyLog
from app.models.usage_log import UsageLog
from app.models.dog import Dog
from app.models.case import Case, CaseEntry, DailyFollowupEntry, CaseDailyTask, TheoryQuestion, DailyTip

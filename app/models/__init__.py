# Importar modelos para que SQLAlchemy los registre en Base.metadata
from app.models.user import User
from app.models.payment import Payment
from app.models.safety_log import SafetyLog
from app.models.usage_log import UsageLog
from app.models.dog import Dog
from app.models.case import Case, CaseEntry, DailyFollowupEntry, CaseDailyTask, TheoryQuestion, DailyTip

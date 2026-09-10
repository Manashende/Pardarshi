"""
Importing this package registers every model with Base.metadata. Any
code that touches the DB — Alembic's env.py, FastAPI startup, test
scripts — should `import app.models` (or import this package indirectly)
before doing anything with SQLAlchemy sessions, or foreign-key
resolution between models will fail with NoReferencedTableError even
though nothing is actually wrong with the models themselves.
"""
from app.models.user import User, UserRole
from app.models.device import Device
from app.models.exam_centre import ExamCentre
from app.models.question import Question
from app.models.exam_event import ExamEvent, ExamEventStatus
from app.models.paper_variant import PaperVariant
from app.models.variant_assignment import VariantAssignment
from app.models.custodian import Custodian, CustodianType
from app.models.share_submission import ShareSubmission, SubmissionType
from app.models.access_attempt import AccessAttempt
from app.models.print_job import PrintJob
from app.models.ledger_entry import LedgerEntry, LedgerEventType
from app.models.custodian_variant_share import CustodianVariantShare
from app.models.centre_operator_assignment import CentreOperatorAssignment
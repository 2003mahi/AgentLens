from fastapi import Depends  # type: ignore
from backend.app.db.session import get_db
from backend.app.core.auth import AuthContext, get_current_auth, verify_workspace_access

AuthDep = Depends(get_current_auth)
DbDep = Depends(get_db)

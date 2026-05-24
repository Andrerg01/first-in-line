"""Facade module for dedup functionality.

This module re-exports the public dedup API from smaller implementation
modules so existing imports remain stable while the logic stays modular.
"""

from app.services.dedup_admin_service import (  # noqa: F401
    check_and_flag_duplicate,
    flag_duplicate,
    get_conflicts,
    merge_events,
    run_retroactive_scan,
)
from app.services.dedup_scoring import (  # noqa: F401
    DUPLICATE_THRESHOLD,
    SimilarityResult,
    _address_similarity,
    _date_similarity,
    _name_similarity,
    normalize_business_name,
    score_pair,
)

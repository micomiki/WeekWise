# Initial test plan

- API authentication required for private lists; registration unique email; login valid/invalid
- Cross-account access to courses/assignments rejected
- Course creation rejects empty title; archived course retains assignments
- Assignment requires timezone-aware deadline; effort may be unknown
- Course/assignment listing persists after server restart and uses correct ordering
- Browser: registration, login, course creation, assignment creation, deadline list, mobile, dark mode, keyboard

Tests already implemented: `backend/tests/test_foundation.py`. Browser checks are **planned, not claimed to pass**.

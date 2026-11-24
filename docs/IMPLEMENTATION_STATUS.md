# Weekwise implementation and story traceability

This is a **development foundation**, not a completed Sprint, Release or formal student study.

| Story | Status | Notes |
| --- | --- | --- |
| US-01 Navigate Overview, My Work, Planner | Partially implemented | Today/My Work responsive; Planner and Connect preview only. Check keyboard/mobile in browser. |
| US-02 Keep information | Partially implemented | DB saves accounts/courses/assignments and data survives restart, but migrations and backup not implemented. Different DB architecture from original single-user local plan. |
| US-03 Organize courses | Partially implemented | Add, list and archive; UI editing added; browser verification pending. |
| US-04 Track assignments | Partially implemented | Add with valid zoned deadline and optional effort; UI editing and detail view added; browser verification pending. |
| US-05 See approaching deadlines | Partially implemented | Sorted upcoming/overdue in Today and My Work; detail dialog added; E2E pending. |
| US-06–US-12 | Not started | Sprint 2 task/planning/backup scope. |
| US-13–US-17 | Not started | Sprint 3 connect/guidance scope. |
| US-18–US-20 | Optional backlog | No implementation. |

## Architecture decision addendum — proposed

1. Weekwise can run alone, using its own API and database.
2. Add standalone accounts because a hosted multiuser app differs from the original local-only single-user MVP. Account data is separate per user.
3. Integrate with University LMS later using federated identity or secure linking, not shared credentials or direct database access.
4. Import LMS academic data read-only while preserving personal user-owned courses and assignments.
5. Record the added scope, assumptions, risks and estimates in team backlog refinement. Do not retrospectively change original delivered baseline or claim formal team acceptance.

## Sprint 1 next tasks

- US-03 verify rename and archive in real browser
- US-04 verify editing and detail dialog in real browser
- US-05 browser E2E, deadline ordering and empty-state verification
- Database migrations and production-ready authentication hardening as explicit engineering work
- Actual Sprint Planning / review notes and CI checks by team

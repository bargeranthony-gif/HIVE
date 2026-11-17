# HAIE v0.1 Initial Test Plan

1. Verify identity persistence across separate store instances.
2. Verify experiences and social contacts persist.
3. Verify duplicate experience IDs are rejected by SQLite.
4. Verify fewer than three evidence records cannot support a revision.
5. Verify evidence from another identity is rejected.
6. Verify revisions remain pending until explicitly accepted.
7. Verify rejected revisions do not change personality.
8. Verify trait changes are bounded and restricted to approved trait names.
9. Verify accepted revisions cannot be accepted a second time.
10. Verify forgetting a subject removes associated social experiences.
11. Verify the prototype uses only its isolated database.
12. Run the existing HIVE production test suite separately.

No production integration is authorized by this prototype.

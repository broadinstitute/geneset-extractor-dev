# IDG source assessment

The historical CFDE GMTs are validation targets, never generation inputs.

`IDG_Drug_Targets_2022` from Enrichr was previously verified to reproduce the
2022 CFDE artifact exactly: 888 of 888 named sets and 14,021 of 14,021
memberships. The DIG model therefore acquires and deterministically parses the
named upstream resource rather than reconstructing it from DrugCentral.

`ARCHS4_IDG_Coexp` from Enrichr was previously verified to reproduce all 352
biological legacy sets and all 105,248 memberships exactly. The current
response has one zero-membership record. DIG applies the general rule of
omitting any GMT record without members; it does not special-case a term.
Recomputing correlations from ARCHS4 data would introduce avoidable version and
algorithm uncertainty.

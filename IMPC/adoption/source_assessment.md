# IMPC HZ1 source assessment

HZ1 is a scientific reimplementation of the December 2022 KOMP2 library. Its assertions input is the exact historical IMPC Data Release 18 `ALL` table identified from the Ma'ayanLab Enrichr notebook. The legacy GMT remains validation-only.

The historical internal mouse-to-human mapping table is not publicly pinned. HZ1 uses the public, stable Harmonizome `mappingFile_2017.txt` for deterministic case-normalized human-symbol canonicalization. This produces scientifically comparable direct phenotype sets, but may differ from the historical library; no target-derived gene or term exceptions are permitted.

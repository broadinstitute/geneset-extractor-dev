# GEO Bulk RNA Gene Sets

This library downloads public NCBI GEO files without authentication, derives explicit two-group bulk RNA differential-expression signatures through `dig-gene-set-extractors`, and retains source-file provenance.

The enabled validation batch contains ninety explicit two-group comparisons:

- `GSE152418`: acute COVID-19 PBMCs versus healthy controls;
- `GSE114765`: N-acetyl cysteine-treated versus untreated activated human CD8 T cells;
- `GSE152546`: NSD3 knockdown versus control in MDA-MB-231 breast cancer cells.
- `GSE157103`: hospitalized COVID-19 versus non-COVID-19 leukocyte profiles;
- `GSE247417`: heat shock versus untreated HeLa cells, adjusted for CLK2 genotype.
- `GSE109182`: IL-1 beta versus control in primary epidermal keratinocytes, adjusted for batch and cell line;
- `GSE117106`: RUVBL2 knockdown versus untreated THP1 cells, adjusted for time point;
- `GSE164637`: doxorubicin versus vehicle in patient-derived cardiomyocytes, adjusted for genotype.
- `GSE178521`: PRMT5 knockdown versus control in NCI-H460 lung adenocarcinoma cells;
- `GSE198478`: butyrate versus vehicle control in T84 intestinal epithelial cells;
- `GSE75440`: NORAD knockout versus wild type in HCT116 colorectal cancer cells.
- `GSE182759`: 15.5K knockdown versus shRNA control in HEK293T cells;
- `GSE214212`: CHD6 knockdown versus shRNA control in C4-2 prostate cancer cells;
- `GSE132245`: CPI-203 versus DMSO in OCI-AML3 cells, adjusted for p53 knockdown status;
- `GSE123861`: SIN3A knockdown versus control in HEK293T cells;
- `GSE160819`: DROSHA knockdown versus CRISPR control in K562 cells;
- `GSE102237`: hydroxyurea/nocodazole-arrested versus untreated 226LDM breast cells;
- `GSE225644`: PAI-039 versus vehicle in human coronary artery smooth muscle cells.
- `GSE182261`: NIK knockdown versus shRNA control in lung-metastatic LM05 breast cancer cells;
- `GSE256536`: LINC00894 knockdown versus control in BE(2)-M17 neuroblast cells;
- `GSE237011`: FASN knockdown versus control in primary human chondrocytes;
- `GSE151774`: dasatinib-treated versus untreated Nalm6-stimulated CD19 CAR T cells;
- `GSE198434`: aspirin versus DMSO in human colonic organoids;
- `GSE128191`: Nutlin-3a versus DMSO in human neural crest cells.
- `GSE254681`: SMANTIS knockout versus non-targeting control in THP-1-derived osteoclast-like cells;
- `GSE178352`: MAL3-101 versus DMSO in triple-negative breast cancer cells, adjusted for cell line;
- `GSE78853`: nortriptyline versus ethanol vehicle in adult hepatic stellate cell myofibroblasts;
- `GSE86219`: Nutlin versus DMSO in MCF7 polysome-associated RNA, adjusted for batch;
- `GSE125086`: cycloheximide versus vehicle in HeLa cells at 24 hours.
- `GSE60391`: CPSF2 knockdown versus non-silencing control in human cells.
- `GSE216870`: Saikosaponin A versus DMSO in HepG2 cells;
- `GSE217526`: parthenolide versus DMSO in MGC-803 gastric cancer cells;
- `GSE218282`: DECR2 knockdown versus control in prostate cancer cells, adjusted for cell line;
- `GSE220643`: celecoxib plus TGF-beta versus TGF-beta in biliary epithelial cells;
- `GSE221217`: PI5P4K perturbation versus scramble control in MCF10A cells;
- `GSE221409`: ISRIB-supported versus original trophoblast stem-cell medium;
- `GSE245941`: JUNB knockdown versus control in CAPAN1 pancreatic cancer cells;
- `GSE247175`: venetoclax plus hexamethylene amiloride versus DMSO in MV4-11 AML cells;
- `GSE247883`: RSL3 versus DMSO in A549 cells;
- `GSE248935`: CD146 knockdown versus control in PC9-BrM3 cells.
- `GSE224742`: SLC1A5 knockdown versus control in T98G glioma cells;
- `GSE227181`: trans-resveratrol versus untreated human stem-cell-derived neurons;
- `GSE233112`: doxorubicin plus IN10018 versus DMSO in SK-OV-3 cells;
- `GSE233647`: RU486 plus docetaxel versus DMSO in PC3 docetaxel-resistant cells;
- `GSE235595`: KMT9 inhibitor KMI169 versus DMSO in PC-3M cells;
- `GSE241523`: DLGAP5 knockdown versus control in T24 bladder cancer cells.
- `GSE207472`: DHT versus vehicle in MDA-MB-453 breast cancer cells;
- `GSE208353`: DNAJC6-mutant versus CRISPR-corrected dopaminergic neurons;
- `GSE209911`: NCSTN knockdown versus control in HaCaT keratinocytes;
- `GSE210150`: crizotinib versus control in CCC-HEH-2 cardiomyocyte cells;
- `GSE213559`: PRPF8 knockdown versus control in H9 embryonic stem cells;
- `GSE227541`: nasopharyngeal carcinoma versus healthy nasal tissue.
- `GSE244672`: RAG1-edited versus unedited hematopoietic stem and progenitor cells;
- `GSE242667`: anti-LCN2 antibody-treated versus untreated HeLa xenograft tumors;
- `GSE235075`: miR-192 overexpression versus control in gastric cancer cells, adjusted for cell line;
- `GSE203070`: FOXL2/NR5A1-induced granulosa-like cells versus fibroblast controls;
- `GSE226653`: all-trans retinoic acid versus control in monocyte-derived macrophages;
- `GSE230773`: scaffold versus monolayer culture in myxoid liposarcoma cells, adjusted for cell line;
- `GSE223426`: epithelial ovarian cancer versus normal ovary;
- `GSE222862`: long-lived plasma cells versus resting B cells;
- `GSE234446`: R848-treated versus untreated plasmacytoid dendritic cells.
- `GSE193382`: CCN3 knockdown versus control in Hs578T breast cancer cells;
- `GSE195803`: CBL0137 versus DMSO in A673 Ewing sarcoma cells;
- `GSE195804`: CBL0137 versus DMSO in SKNMC Ewing sarcoma cells;
- `GSE196226`: G9a inhibition versus DMSO during T-cell differentiation;
- `GSE198630`: celastrol versus DMSO in colorectal cancer cells, adjusted for cell line;
- `GSE201646`: YAP knockout versus wild type in EC9706 cells;
- `GSE208711`: LIMp27 knockdown versus siRNA control in WiDr cells;
- `GSE210080`: pectolinarigenin versus DMSO in high-lipid Huh-7 cells;
- `GSE211118`: radiation versus control across lung cell lines, adjusted for cell line;
- `GSE212201`: MIF knockdown versus wild type in PANC-1 cells, adjusted for oxygen condition;
- `GSE215335`: UT-143 versus vehicle in 22RV1 cells;
- `GSE217132`: PFKFB4 knockout versus wild type in MDA-MB-231 cells;
- `GSE221871`: physiological versus nutritive flow in proximal tubule epithelial cells.
- `GSE143365`: ITNK versus T-cell transcriptional state;
- `GSE143957`: circANRIL knockdown versus siRNA control during senescence;
- `GSE145249`: PPM1G knockout versus control in HCT116 cells;
- `GSE148171`: tuberculosis versus healthy PBMC;
- `GSE150807`: enzalutamide-resistant versus parental LNCaP cells;
- `GSE151083`: enzalutamide-resistant versus control C42-B cells;
- `GSE159531`: enzalutamide-resistant versus parental VCaP cells;
- `GSE160336`: dCBP-1 versus DMSO in MM.1S cells;
- `GSE160990`: TGF-beta plus alisertib versus TGF-beta in MDA-MB-231 cells;
- `GSE195696`: TET2 knockdown versus control during endothelial-to-mesenchymal transition;
- `GSE200462`: HIV long-term nonprogressors versus regular progressors;
- `GSE201174`: CAR versus wild-type macrophages during neuroblastoma co-culture;
- `GSE202724`: decellularized spinal-cord matrix versus collagen astrocyte culture;
- `GSE206374`: BHLHE40 overexpression versus vector control in Jurkat cells;
- `GSE210336`: Bifidobacterium longum versus PBS in neonatal and adult T cells;
- `GSE212248`: biallelic RB1 mutation versus wild type in iPSC-derived microglia.

The first study excludes one convalescent sample through its explicit group-value configuration. The other enabled studies use NCBI-standardized count matrices whose columns are stable GSM accessions. Failed QC candidates remain disabled in the dataset table: `GSE191314`, `GSE161969`, `GSE70084`, `GSE209655`, `GSE228524`, `GSE129522`, `GSE115137`, `GSE188251`, `GSE220537`, `GSE227682`, `GSE232596`, `GSE202571`, `GSE235757`, `GSE239939`, `GSE232638`, `GSE193971`, `GSE146640`, `GSE151280`, `GSE159618`, `GSE161631`, `GSE216125`, and `GSE221945` produced no gene sets meeting the predeclared thresholds, while `GSE179747`, `GSE76453`, `GSE229339`, `GSE233159`, `GSE205274`, `GSE149413`, `GSE155530`, and `GSE164058` produced marginal or one-direction sets that failed QC.

From the parent workspace:

```bash
geneset-extractor-dev/GEO_BULK/run/build_geo_bulk_genesets.sh \
--datasets GSE152418,GSE114765,GSE152546,GSE157103,GSE247417,GSE109182,GSE117106,GSE164637,GSE178521,GSE198478,GSE75440,GSE182759,GSE214212,GSE132245,GSE123861,GSE160819,GSE102237,GSE225644,GSE182261,GSE256536,GSE237011,GSE151774,GSE198434,GSE128191,GSE254681,GSE178352,GSE78853,GSE86219,GSE125086,GSE60391,GSE216870,GSE217526,GSE218282,GSE220643,GSE221217,GSE221409,GSE245941,GSE247175,GSE247883,GSE248935,GSE224742,GSE227181,GSE233112,GSE233647,GSE235595,GSE241523,GSE207472,GSE208353,GSE209911,GSE210150,GSE213559,GSE227541,GSE244672,GSE242667,GSE235075,GSE203070,GSE226653,GSE230773,GSE223426,GSE222862,GSE234446,GSE193382,GSE195803,GSE195804,GSE196226,GSE198630,GSE201646,GSE208711,GSE210080,GSE211118,GSE212201,GSE215335,GSE217132,GSE221871,GSE143365,GSE143957,GSE145249,GSE148171,GSE150807,GSE151083,GSE159531,GSE160336,GSE160990,GSE195696,GSE200462,GSE201174,GSE202724,GSE206374,GSE210336,GSE212248 \
  --models GB1
```

No repository login or API token is required. Downloads are cached under `inputs/GEO_BULK/`, outside both Git repositories. Add `--offline` to prohibit downloads after the cache has been populated.

The configured `auto` differential-expression backend uses an available R backend when present and otherwise records a fallback to the dependency-light approximate backend. Use `--backend lightweight` only for an explicit smoke run.

See `planning/pipeline_inputs.md` for input and output details.

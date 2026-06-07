

.mode column
.headers on

select * 
from gene_set gs, provenance pro
where gs.gene_set_id = pro.gene_set_id
and gs.gene_set_id = 1;


# a15.10 – Intelligent utfylling av mappe-roller

Mapper-dialogen har nå handlingen **Fyll ut forslag**.

Forslag beregnes i `app.storage_layouts`, ikke i GUI-et. Dermed kan samme
policy senere brukes av discovery, CLI og andre profiler.

For `IKAMR standard` kan en eksplisitt valgt Source root for eksempel gi:

- Source root = valgt hovedmappe
- Source extraction = `<root>/content/sip/content`
- Work root = `<root>`
- Work content = `<root>/content`
- Work operations = `<root>/repository_operations`
- Archive root = `<root>/aip`

Hvis en faktisk Source extraction allerede er kjent og passer profilen, har
den prioritet. Dette bevarer virkelige varianter som ekstra `content`-nivå.

Handlingen fyller tomme felt direkte. Hvis eksisterende felt avviker fra
forslaget, må brukeren eksplisitt velge om disse også skal erstattes.

# clusters/oci-k3s/

`raiz.yaml` é a Application raiz (app-of-apps): o único apply manual. Ela reconcilia `apps/`
(AppProject `tcc` + ApplicationSet `tcc`), que gera `catalogo-{api,front}-{hml,prd}`.

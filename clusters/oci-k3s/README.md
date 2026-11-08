# clusters/oci-k3s/

`raiz.yaml` é a Application raiz (app-of-apps): o único apply manual. Ela reconcilia `apps/`:
AppProject `tcc`, ApplicationSet `tcc` (uma Application por pasta `apps/<app>/<amb>`) e o Reloader.

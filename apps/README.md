# apps/

Um diretório por aplicação e ambiente (`apps/<app>/hml`, `apps/<app>/prd`), com o overlay Kustomize
derivado de `golden-path/base`. O `ci.yml` de cada app escolhe o overlay pela branch.
É o **único** lugar em que a esteira de CI de uma aplicação escreve (commit da tag da imagem).

Formato mínimo de `apps/<app>/<ambiente>/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: <app>
resources:
  - ../../../golden-path/base
images:
  - name: ghcr.io/<owner>/<app>
    newTag: sha-000000000000   # atualizado pela esteira
```

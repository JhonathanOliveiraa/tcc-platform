# apps/

Um diretório por aplicação, com o overlay Kustomize derivado de `golden-path/base`.
É o **único** lugar em que a esteira de CI de uma aplicação escreve (commit da tag da imagem).

Formato mínimo de `apps/<app>/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: <app>
resources:
  - ../../golden-path/base
images:
  - name: ghcr.io/<owner>/<app>
    newTag: sha-000000000000   # atualizado pela esteira
```

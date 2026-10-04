# Pending workflows

These GitHub Actions workflows are ready but could not be pushed to `.github/workflows/`
because the credentials used to push lacked the `workflow` scope.

To activate them, move the files (except this README) into `.github/workflows/`:

```bash
git mv .github/pending-workflows/*.yml .github/workflows/
git rm .github/pending-workflows/README.md
```

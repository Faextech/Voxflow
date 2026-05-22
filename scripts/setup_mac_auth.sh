#!/bin/bash
# Autentica GitHub (Faextech) e Railway no Mac — rode no terminal do Cursor
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

echo "=== Ferramentas instaladas ==="
echo "  gh:      $(gh --version | head -1)"
echo "  railway: $(railway --version 2>/dev/null || echo 'não encontrado')"
echo "  git:     $(git --version)"
echo ""

echo "=== 1/2 — Login GitHub (conta Faextech) ==="
echo "Escolha: GitHub.com → HTTPS → Login with a web browser"
gh auth login -h github.com -p https -w
gh auth setup-git
echo ""

echo "=== 2/2 — Login Railway (conta Faextech) ==="
railway login
echo ""

echo "=== Teste push ==="
cd "$(dirname "$0")/.."
git remote -v
echo ""
read -r -p "Fazer git push origin main agora? (s/n) " resp
if [[ "$resp" == "s" || "$resp" == "S" ]]; then
  git push -u origin main
  echo "✓ Push concluído!"
else
  echo "Quando quiser: git push -u origin main"
fi

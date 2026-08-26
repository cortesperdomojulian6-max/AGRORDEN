# AGRORDEN - Inicio rápido
# Ejecuta: .\start.ps1

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkCyan
Write-Host "  AGRORDEN · Orden del hato" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkCyan

Write-Host "`n[1/2] Iniciando PostgreSQL..." -ForegroundColor Yellow
& .\scripts\db_start.ps1
Start-Sleep -Seconds 5

Write-Host "`n[2/2] Iniciando dashboard en http://localhost:8501 ..." -ForegroundColor Yellow
Write-Host "Presiona Ctrl+C para detener.`n" -ForegroundColor Gray

python -m streamlit run app/dashboard.py --server.port 8501
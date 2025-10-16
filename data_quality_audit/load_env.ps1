# PowerShell script to load environment variables from .env file
# Usage: .\load_env.ps1

if (Test-Path .env) {
    Write-Host "Loading environment variables from .env file..." -ForegroundColor Green

    Get-Content .env | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, 'Process')
            Write-Host "  Set $name" -ForegroundColor Gray
        }
    }

    Write-Host "Environment variables loaded successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now run: python main.py" -ForegroundColor Cyan
} else {
    Write-Host "ERROR: .env file not found!" -ForegroundColor Red
    Write-Host "Please create a .env file from .env.example first:" -ForegroundColor Yellow
    Write-Host "  1. Copy .env.example to .env" -ForegroundColor Yellow
    Write-Host "  2. Edit .env with your actual credentials" -ForegroundColor Yellow
    Write-Host "  3. Run this script again" -ForegroundColor Yellow
}

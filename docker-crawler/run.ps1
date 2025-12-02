# Docker Crawler - Run Script
# Usage: .\run.ps1 [command]

param(
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"

function Show-Help {
    Write-Host @"
Docker Crawler - Commands:

  .\run.ps1 build     - Build all Docker images
  .\run.ps1 start     - Start all services (Splash, Redis, PostgreSQL, Extractor)
  .\run.ps1 stop      - Stop all services
  .\run.ps1 crawl     - Run crawler with default domains
  .\run.ps1 crawl-file <file> - Run crawler with domains from file
  .\run.ps1 logs      - View crawler logs
  .\run.ps1 export    - Export results to CSV
  .\run.ps1 status    - Check service status
  .\run.ps1 clean     - Remove all containers and volumes

"@
}

function Build-Images {
    Write-Host "Building Docker images..."
    docker-compose build
}

function Start-Services {
    Write-Host "Starting services..."
    docker-compose up -d splash redis postgres extractor
    Write-Host "Waiting for services to be ready..."
    Start-Sleep -Seconds 10
    docker-compose ps
}

function Stop-Services {
    Write-Host "Stopping services..."
    docker-compose down
}

function Run-Crawler {
    param([string]$DomainsFile = "domains.txt")
    
    Write-Host "Running crawler with domains from: $DomainsFile"
    docker-compose run --rm crawler scrapy crawl impressum -a domains_file=/app/$DomainsFile
}

function Show-Logs {
    docker-compose logs -f crawler
}

function Export-Results {
    Write-Host "Exporting results..."
    docker-compose exec postgres psql -U crawler -d crawler -c "\COPY (SELECT * FROM results) TO '/tmp/export.csv' WITH CSV HEADER"
    docker-compose cp postgres:/tmp/export.csv ./data/export.csv
    Write-Host "Results exported to data/export.csv"
}

function Show-Status {
    docker-compose ps
    Write-Host "`nDatabase stats:"
    docker-compose exec postgres psql -U crawler -d crawler -c "SELECT COUNT(*) as total, COUNT(company_name) as with_company, COUNT(street) as with_address FROM results;"
}

function Clean-All {
    Write-Host "Removing all containers and volumes..."
    docker-compose down -v
}

switch ($Command) {
    "build"      { Build-Images }
    "start"      { Start-Services }
    "stop"       { Stop-Services }
    "crawl"      { Run-Crawler }
    "crawl-file" { Run-Crawler -DomainsFile $args[0] }
    "logs"       { Show-Logs }
    "export"     { Export-Results }
    "status"     { Show-Status }
    "clean"      { Clean-All }
    default      { Show-Help }
}

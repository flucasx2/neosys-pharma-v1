param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9_.-]+$')][string]$PgHost,
    [Parameter(Mandatory=$true)][ValidateRange(1,65535)][int]$PgPort,
    [Parameter(Mandatory=$true)][string]$PgUser,
    [Parameter(Mandatory=$true)][ValidateLength(1,63)][ValidatePattern('^neosys_consolidation_migrations_[a-z0-9_]+$')][string]$DatabaseName,
    [switch]$CreerBaseJetable,
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
# Utiliser PGPASSWORD/pgpass localement ; aucun secret n'est inscrit dans le script.
$connectionArgs = @('-X', '-v', 'ON_ERROR_STOP=1', '-h', $PgHost, '-p', "$PgPort", '-U', $PgUser)
& psql @connectionArgs -d postgres -c 'select version(), current_database(), current_user, inet_server_addr(), inet_server_port();'
if ($LASTEXITCODE -ne 0) { throw 'Identité serveur inaccessible : arrêt.' }
$found = & psql @connectionArgs -d postgres -Atc "select datname from pg_database where datname = '$DatabaseName';"
if ($LASTEXITCODE -ne 0) { throw 'Impossible de vérifier l’absence de base.' }
if ($found) { throw 'La base existe déjà : refus de réutilisation, suppression ou migration.' }
if (-not $CreerBaseJetable) { Write-Output 'Inspection terminée. Relancer avec -CreerBaseJetable après vérification de ce serveur.'; exit 0 }
$marker = 'NEOSYS_CONSOLIDATION_MIGRATIONS_DISPOSABLE'
& psql @connectionArgs -d postgres -c "CREATE DATABASE $DatabaseName;"
if ($LASTEXITCODE -ne 0) { throw 'Création refusée ; aucune autre base utilisée.' }
& psql @connectionArgs -d postgres -c "COMMENT ON DATABASE $DatabaseName IS '$marker';"
if ($LASTEXITCODE -ne 0) { throw 'Marqueur impossible ; base conservée sans exécuter les tests.' }
$oldUrl = $env:TEST_CONSOLIDATION_MIGRATION_URL
$oldConfirmation = $env:CONSOLIDATION_CONFIRM_DATABASE
$oldDatabaseUrl = $env:DATABASE_URL
try {
    $escapedUser = [uri]::EscapeDataString($PgUser)
    $env:TEST_CONSOLIDATION_MIGRATION_URL = "postgresql+psycopg://${escapedUser}@${PgHost}:${PgPort}/${DatabaseName}"
    $env:CONSOLIDATION_CONFIRM_DATABASE = $DatabaseName
    $env:DATABASE_URL = $env:TEST_CONSOLIDATION_MIGRATION_URL
    # Chemin Alembic uniquement : test natif sur base vide, nom et marqueur vérifiés.
    & $Python -m pytest -q -s tests/test_consolidation_migrations.py::test_migration_moyens_postgresql_natif
    if ($LASTEXITCODE -ne 0) { throw 'Contrôle PostgreSQL en échec. Conserver les logs et la base ; aucune suppression automatique.' }
    Write-Output "Recette native exécutée ; base $DatabaseName conservée pour inspection."
} finally {
    $env:TEST_CONSOLIDATION_MIGRATION_URL = $oldUrl
    $env:CONSOLIDATION_CONFIRM_DATABASE = $oldConfirmation
    $env:DATABASE_URL = $oldDatabaseUrl
}

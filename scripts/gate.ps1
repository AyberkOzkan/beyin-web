# Gate: runs every check of the project in one working tree and prints only what failed.
# Run it before a commit. A code agent's sandbox usually cannot start Edge, so run it outside one:
# only there do the browser tests run.
#   exit 0  all checks passed
#   exit 1  some checks fail; the output is short enough to hand back to the code agent
#   exit 3  the checks could not run as intended (no Python, browser tests skipped)
# Keep this file ASCII-only: Windows PowerShell 5.1 reads a script without a BOM as ANSI.
param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [ValidateSet('all', 'node', 'python')][string]$Only = 'all'
)
$ErrorActionPreference = 'Continue'
# A shell started before Python was installed still carries the old PATH.
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Set-Location $Root

$failed = $false
$unavailable = $false

if ($Only -ne 'python') {
    if (Test-Path 'tests\js') {
        $out = @(node --test tests/js 2>&1 | ForEach-Object { "$_" })
        $code = $LASTEXITCODE
        $counts = ($out | Where-Object { $_ -match '^\S (tests|pass|fail) \d+' } | ForEach-Object { $_.Substring(2) }) -join ', '
        "node: $counts"
        if ($code -ne 0) {
            $failed = $true
            $start = 0
            for ($i = 0; $i -lt $out.Count; $i++) { if ($out[$i] -match 'failing tests') { $start = $i; break } }
            '--- node --test tests/js: failures ---'
            $out[$start..($out.Count - 1)] | Where-Object { $_.Trim() -ne '' } | Select-Object -First 90
        }
    } else {
        'node: no tests/js directory'
    }
}

if ($Only -ne 'node') {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        'python: the py launcher is not on PATH'
        $unavailable = $true
    } else {
        # Verbose, so that a skipped test can be told apart by its module.
        $out = @(py -3 -m unittest discover -v -s tests -t . 2>&1 | ForEach-Object { "$_" })
        $code = $LASTEXITCODE
        $ran = $out | Where-Object { $_ -cmatch '^Ran \d+ tests?' } | Select-Object -Last 1
        $verdict = $out | Where-Object { $_ -cmatch '^(OK|FAILED)' } | Select-Object -Last 1
        "python: $ran -> $verdict"
        if ($code -ne 0) {
            $failed = $true
            $start = 0
            for ($i = 0; $i -lt $out.Count; $i++) { if ($out[$i] -cmatch '^={20,}') { $start = $i; break } }
            '--- python -m unittest discover -s tests -t .: failures ---'
            # Selenium appends the browser's native stack to every error; it says nothing about the page.
            $out[$start..($out.Count - 1)] |
                Where-Object { $_ -notmatch '^\s+(GetHandleVerifier|\(No symbol\)|BaseThreadInitThunk|RtlUserThreadStart|Microsoft::|sqlite3_|Stacktrace:)' -and $_ -ne 'System.Management.Automation.RemoteException' -and $_.Trim() -ne '' } |
                ForEach-Object { if ($_.Length -gt 400) { $_.Substring(0, 400) + ' ...' } else { $_ } } |
                Select-Object -First 160
        } elseif ("$verdict" -match 'skipped') {
            $skips = @($out | Where-Object { $_ -match '\.\.\. skipped ' })
            if (@($skips | Where-Object { $_ -match 'tests\.e2e\.' }).Count -gt 0 -or $skips.Count -eq 0) {
                'python: browser tests were skipped. They need selenium and a cached Edge driver;'
                'refresh the driver with: py -3 -c "from selenium import webdriver; webdriver.Edge().quit()"'
                $unavailable = $true
            } else {
                # Tests of the other platform (the POSIX launcher on Windows) skip themselves on purpose.
                'python: skipped outside the browser tests:'
                $skips | ForEach-Object { '  ' + ($_ -replace '^(\S+) \((\S+)\) \.\.\. skipped ', '$2: ') } | Select-Object -First 12
            }
        }
    }
}

if ($failed) { 'gate: FAILED'; exit 1 }
if ($unavailable) { 'gate: UNAVAILABLE'; exit 3 }
'gate: passed'
exit 0

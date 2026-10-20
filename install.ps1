# Install, update or roll back the Dewy toolchain on Windows x86_64.
#
#   irm https://dewy-lang.org/install.ps1 | iex
#   & ([scriptblock]::Create((irm https://dewy-lang.org/install.ps1))) -Release TAG
#   powershell -ExecutionPolicy Bypass -File install.ps1 [-Release TAG] [-Prefix DIR] [-NoModifyPath]
#
# Works in Windows PowerShell 5.1 and PowerShell 7 and changes no execution
# policy. Without -Release it installs the release named by
# https://dewy-lang.org/toolchain-channel.txt. The layout and transaction
# match install.sh, under PREFIX (default $HOME\.dewy):
#   toolchains\<release>\    immutable verified toolchains (bin\, lib\, RELEASE)
#   toolchains\current       two lines: the active and the previous release
#   bin\dewy.cmd, bin\dewy-core.cmd   launchers; `dewy update`, `dewy rollback`
#   libexec\dewy-install.ps1 the verified installer of the active release
# Everything is downloaded and verified (Get-FileHash) before anything
# changes; the toolchain is staged under PREFIX\toolchains, smoke-tested,
# renamed into place and activated by atomically replacing toolchains\current.
# Only the user PATH changes. DEWY_INSTALL_CHANNEL_URL and
# DEWY_INSTALL_DOWNLOAD_URL (a URL or a local directory) select a mirror.

& {
param([object[]]$argv)
if ($null -eq $argv) { $argv = @() }
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2
$ProgressPreference = 'SilentlyContinue'

$TagPattern = '^dewy-[0-9]+\.[0-9]+\.[0-9]+-dev\.[0-9]{8}\.([0-9a-f]{12})$'
$NamePattern = '^[A-Za-z0-9][A-Za-z0-9._-]*$'
$MemberPattern = '^dewy-core(/[A-Za-z0-9_+@-][A-Za-z0-9._+@-]*)*/?$'
$Platform = 'windows-x86_64'
$Asset = "dewy-core-$Platform.tar.gz"
$State = @{ Staging = $null; Lock = $null }

function Fail([string]$message) { throw [System.InvalidOperationException]::new($message) }
function Test-IOException($record) {
    $e = $record.Exception
    while ($null -ne $e) {
        if ($e -is [System.IO.IOException] -or $e -is [System.UnauthorizedAccessException]) { return $true }
        $e = $e.InnerException
    }
    return $false
}
function Info([string]$message) { Write-Host $message }

function Show-Usage {
    Info @'
Install the Dewy toolchain.

Usage: install.ps1 [-Release TAG] [-Prefix DIR] [-NoModifyPath]

  -Release TAG     install this release (dewy-0.0.0-dev.YYYYMMDD.<commit>)
                   instead of the one the dewy-lang.org channel names
  -Prefix DIR      install into DIR instead of $HOME\.dewy
  -NoModifyPath    do not add DIR\bin to the user PATH

Afterwards `dewy update [--release TAG]` installs a newer toolchain and
`dewy rollback` switches back to the previous one.
'@
}

function Get-Download([string]$url, [string]$destination) {
    try {
        if ($url -match '^https?://') {
            if ($PSVersionTable.PSVersion.Major -lt 6) {
                [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
            }
            Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $destination
        } else {
            $path = $url
            if ($path -match '^file:') { $path = ([Uri]$path).LocalPath }
            Copy-Item -LiteralPath $path -Destination $destination
        }
    } catch {
        Fail "could not download ${url}: $($_.Exception.Message)"
    }
}

function Get-Sha256([string]$path) {
    (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant()
}

function Assert-Sum([string]$path, [string]$expected, [string]$name) {
    $actual = Get-Sha256 $path
    if ($actual -cne $expected) { Fail "checksum mismatch for $name (expected $expected, got $actual); nothing was changed" }
}

# Printable ASCII and LF only: channel and checksum files are data, never code.
function Read-PlainLines([string]$path) {
    $bytes = [IO.File]::ReadAllBytes($path)
    if ($bytes.Length -eq 0 -or $bytes[$bytes.Length - 1] -ne 10) { return $null }
    foreach ($b in $bytes) { if ($b -ne 10 -and ($b -lt 32 -or $b -gt 126)) { return $null } }
    $text = [Text.Encoding]::ASCII.GetString($bytes, 0, $bytes.Length - 1)
    return , $text.Split([char]10)
}

function Find-Sum([string]$path, [string]$name) {
    $lines = Read-PlainLines $path
    if ($null -eq $lines) { return $null }
    foreach ($line in $lines) {
        if ($line -cnotmatch '^([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._-]*)$') { return $null }
        if ($Matches[2] -ceq $name) { return $Matches[1] }
    }
    return $null
}

# toolchain-channel.txt, format 1 (see docs/DEVELOPMENT.md).
function Read-Channel([string]$path) {
    $lines = Read-PlainLines $path
    if ($null -eq $lines -or $lines.Count -lt 4 -or $lines.Count -gt 64) { return $null }
    if ($lines[0] -cne 'dewy-toolchain-channel 1') { return $null }
    if ($lines[1] -cnotmatch '^release (.+)$') { return $null }
    $tag = $Matches[1]
    if ($tag -cnotmatch $TagPattern) { return $null }
    if ($lines[$lines.Count - 1] -cne 'end') { return $null }
    $sums = @{}
    for ($i = 2; $i -lt $lines.Count - 1; $i++) {
        if ($lines[$i] -cnotmatch '^sha256 ([0-9a-f]{64}) ([A-Za-z0-9][A-Za-z0-9._-]*)$') { return $null }
        if ($sums.ContainsKey($Matches[2])) { return $null }
        $sums[$Matches[2]] = $Matches[1]
    }
    return @{ Tag = $tag; Sums = $sums }
}

function Invoke-Native([string]$exe, [string[]]$arguments) {
    $saved = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = @(& $exe @arguments 2>&1 | ForEach-Object { "$_" })
        return @{ Code = $LASTEXITCODE; Output = $output }
    } finally {
        $ErrorActionPreference = $saved
    }
}

# Every member must be a regular file or directory below dewy-core/ with a
# plain name; links, absolute paths and .. are rejected before extraction.
function Expand-Toolchain([string]$archive, [string]$out) {
    $tar = Join-Path $env:SystemRoot 'System32\tar.exe'
    $names = Invoke-Native $tar @('-tzf', $archive)
    $listing = Invoke-Native $tar @('-tvzf', $archive)
    if ($names.Code -ne 0 -or $listing.Code -ne 0 -or $names.Output.Count -eq 0) { Fail "$Asset is not a readable archive" }
    foreach ($name in $names.Output) {
        if ($name -cnotmatch $MemberPattern) { Fail "$Asset contains an unexpected path: $name" }
    }
    foreach ($line in $listing.Output) {
        if (-not ($line.StartsWith('-') -or $line.StartsWith('d'))) { Fail "$Asset contains a link or special file: $line" }
    }
    New-Item -ItemType Directory -Path $out | Out-Null
    $result = Invoke-Native $tar @('-xzf', $archive, '-C', $out)
    if ($result.Code -ne 0) { Fail "could not extract ${Asset}: $($result.Output -join ' ')" }
    $links = @(Get-ChildItem -LiteralPath $out -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint })
    if ($links.Count -gt 0) { Fail "$Asset produced a link" }
}

function Get-ReleaseField([string]$path, [string]$key) {
    foreach ($line in [IO.File]::ReadAllLines($path)) {
        $fields = $line.Split(' ', 2)
        if ($fields.Count -eq 2 -and $fields[0] -ceq $key) { return $fields[1] }
    }
    return $null
}

# Returns the problem, or $null for a complete toolchain of this release.
function Test-Toolchain([string]$dir, [string]$short) {
    foreach ($required in @('bin\dewy-core.exe', 'lib\core\rt.jo', 'PACKAGE.json', 'RELEASE')) {
        if (-not (Test-Path -LiteralPath (Join-Path $dir $required) -PathType Leaf)) { return "the toolchain lacks $required" }
    }
    $release = Join-Path $dir 'RELEASE'
    if (([IO.File]::ReadAllLines($release))[0] -cne 'dewy-toolchain-release 1') { return 'unrecognised toolchain RELEASE file' }
    $hostName = Get-ReleaseField $release 'platform'
    if ($hostName -cne $Platform) { return "the toolchain is for $hostName, not $Platform" }
    $revision = Get-ReleaseField $release 'revision'
    if ($null -eq $revision -or -not $revision.StartsWith($short)) { return "the toolchain revision $revision does not match the release" }
    return $null
}

# The compiler reports its version and builds and runs a tiny program, with
# no inherited DEWY_*/SLOPPY_* settings and no build tools on PATH.
function Test-Smoke([string]$dir) {
    $work = Join-Path $State.Staging 'smoke'
    if (Test-Path -LiteralPath $work) { Remove-Item -LiteralPath $work -Recurse -Force }
    New-Item -ItemType Directory -Path $work | Out-Null
    $compiler = Join-Path $dir 'bin\dewy-core.exe'
    $saved = @{}
    foreach ($item in @(Get-ChildItem env: | Where-Object { $_.Name -match '^(DEWY_|SLOPPY_)' -or $_.Name -eq 'PATH' })) {
        $saved[$item.Name] = $item.Value
        Remove-Item -LiteralPath "env:$($item.Name)"
    }
    $env:PATH = Join-Path $env:SystemRoot 'System32'
    Push-Location -LiteralPath $work
    try {
        $version = Invoke-Native $compiler @('--version')
        if ($version.Code -ne 0) { Write-Warning "dewy-core --version failed (exit $($version.Code)): $($version.Output -join "`n")"; return $false }
        [IO.File]::WriteAllText((Join-Path $work 'smoke.dewy'), "main=()=>{let values=[20 22] return sum(values)}`n")
        $build = Invoke-Native $compiler @('build', (Join-Path $work 'smoke.dewy'), '-o', (Join-Path $work 'smoke.exe'))
        if ($build.Code -ne 0) { Write-Warning "the smoke build failed (exit $($build.Code)): $($build.Output -join "`n")"; return $false }
        $run = Invoke-Native (Join-Path $work 'smoke.exe') @()
        if ($run.Code -ne 42) { Write-Warning "smoke program exited with $($run.Code) instead of 42"; return $false }
        return $true
    } finally {
        Pop-Location
        Remove-Item -LiteralPath env:PATH -ErrorAction SilentlyContinue
        foreach ($name in $saved.Keys) { Set-Item -LiteralPath "env:$name" -Value $saved[$name] }
    }
}

# A file opened without sharing is the lock; the system releases it when an
# installer exits for any reason, so an interrupted run leaves no stale lock.
function Enter-Lock([string]$toolchains) {
    $path = Join-Path $toolchains '.lock'
    $deadline = (Get-Date).AddSeconds(600)
    $waiting = $false
    while ($true) {
        try {
            $State.Lock = [IO.File]::Open($path, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
            return
        } catch {
            if (-not (Test-IOException $_)) { throw }
            if (-not $waiting) { Info "Waiting for another Dewy installation to finish ($path)"; $waiting = $true }
            if ((Get-Date) -gt $deadline) { Fail "timed out waiting for $path" }
            Start-Sleep -Milliseconds 500
        }
    }
}

function Read-Pointer([string]$toolchains) {
    $pointer = @{ Current = ''; Previous = '' }
    $path = Join-Path $toolchains 'current'
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        $lines = @([IO.File]::ReadAllLines($path))
        if ($lines.Count -ge 1 -and $lines[0] -cmatch $NamePattern) { $pointer.Current = $lines[0] }
        if ($lines.Count -ge 2 -and $lines[1] -cmatch $NamePattern) { $pointer.Previous = $lines[1] }
    }
    return $pointer
}

# Replace a file by rename; retry briefly while a launcher holds it open.
function Set-FileAtomically([string]$source, [string]$destination) {
    for ($attempt = 0; ; $attempt++) {
        try {
            if (Test-Path -LiteralPath $destination -PathType Leaf) {
                [IO.File]::Replace($source, $destination, [NullString]::Value)
            } else {
                [IO.File]::Move($source, $destination)
            }
            return
        } catch {
            if ($attempt -ge 50 -or -not (Test-IOException $_)) { throw }
            Start-Sleep -Milliseconds 100
        }
    }
}

function Write-Pointer([string]$toolchains, [string]$current, [string]$previous) {
    $next = Join-Path $toolchains ".current.$PID"
    [IO.File]::WriteAllText($next, "$current`r`n$previous`r`n", [Text.Encoding]::ASCII)
    Set-FileAtomically $next (Join-Path $toolchains 'current')
}

function Write-TextFile([string]$path, [string]$content) {
    if ((Test-Path -LiteralPath $path -PathType Leaf) -and [IO.File]::ReadAllText($path) -ceq $content) { return }
    $next = Join-Path (Split-Path -Parent $path) (".$(Split-Path -Leaf $path).$PID")
    [IO.File]::WriteAllText($next, $content, [Text.Encoding]::ASCII)
    Set-FileAtomically $next $path
}

# Each command is one line so that cmd.exe never rereads a replaced launcher.
function Write-Launcher([string]$prefix, [string]$name) {
    $content = @"
@echo off
rem Dewy launcher written by the Dewy installer: runs the active toolchain's
rem compiler. "$name update [--release TAG]" and "$name rollback" manage toolchains.
setlocal DisableDelayedExpansion
set "DEWY_ROOT=$prefix"
if /i "%~1"=="update" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%DEWY_ROOT%\libexec\dewy-install.ps1" -Prefix "%DEWY_ROOT%" %* & exit /b
if /i "%~1"=="rollback" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%DEWY_ROOT%\libexec\dewy-install.ps1" -Prefix "%DEWY_ROOT%" %* & exit /b
set "DEWY_TOOLCHAIN="
if exist "%DEWY_ROOT%\toolchains\current" set /p DEWY_TOOLCHAIN=<"%DEWY_ROOT%\toolchains\current"
if not defined DEWY_TOOLCHAIN goto missing
"%DEWY_ROOT%\toolchains\%DEWY_TOOLCHAIN%\bin\dewy-core.exe" %* & exit /b
:missing
echo ${name}: no Dewy toolchain is active in "%DEWY_ROOT%"; run the installer again 1>&2
exit /b 1
"@
    Write-TextFile (Join-Path $prefix "bin\$name.cmd") ($content.Replace("`r`n", "`n").Replace("`n", "`r`n") + "`r`n")
}

function Remove-Unused([string]$toolchains, $pointer) {
    foreach ($dir in @(Get-ChildItem -LiteralPath $toolchains -Directory)) {
        if ($dir.Name.StartsWith('.') -or $dir.Name -ceq $pointer.Current -or $dir.Name -ceq $pointer.Previous) { continue }
        # Rename first so that a half-deleted toolchain is never reused. A
        # running compiler can keep it locked; it is retried next time.
        $trash = Join-Path $toolchains ".trash.$($dir.Name).$PID"
        try {
            [IO.Directory]::Move($dir.FullName, $trash)
            Remove-Item -LiteralPath $trash -Recurse -Force -ErrorAction SilentlyContinue
        } catch {
            Info "Keeping $($dir.Name) for now: $($_.Exception.Message)"
        }
    }
}

function Add-UserPath([string]$bin) {
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment', $true)
    try {
        $raw = [string]$key.GetValue('Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
        $entries = @($raw.Split(';') | Where-Object { $_ -ne '' })
        $normal = $bin.TrimEnd('\')
        foreach ($entry in $entries) {
            if ([Environment]::ExpandEnvironmentVariables($entry).TrimEnd('\') -ieq $normal) {
                Info "PATH already contains $bin"
                return
            }
        }
        $key.SetValue('Path', (@($bin) + $entries) -join ';', [Microsoft.Win32.RegistryValueKind]::ExpandString)
    } finally {
        $key.Close()
    }
    # Setting a variable through the API broadcasts the change to new shells.
    [Environment]::SetEnvironmentVariable('DEWY_INSTALL_PATH_CHANGED', '1', 'User')
    [Environment]::SetEnvironmentVariable('DEWY_INSTALL_PATH_CHANGED', $null, 'User')
    Info "Added $bin to the user PATH"
}

function Invoke-Rollback([string]$toolchains) {
    $pointer = Read-Pointer $toolchains
    if (-not $pointer.Current) { Fail "no Dewy toolchain is active in $toolchains" }
    if (-not $pointer.Previous -or -not (Test-Path -LiteralPath (Join-Path $toolchains "$($pointer.Previous)\bin\dewy-core.exe"))) {
        Fail "there is no previous toolchain to roll back to (active: $($pointer.Current))"
    }
    Write-Pointer $toolchains $pointer.Previous $pointer.Current
    Info "Rolled back to $($pointer.Previous) (from $($pointer.Current); dewy rollback switches again)."
}

function Install-Dewy([object[]]$arguments) {
    $release = ''
    $prefix = ''
    $modifyPath = $true
    $action = 'install'
    for ($i = 0; $i -lt $arguments.Count; $i++) {
        $arg = [string]$arguments[$i]
        if ($arg -in @('-Release', '--release', '-Prefix', '--prefix')) {
            if ($i + 1 -ge $arguments.Count) { Fail "$arg needs a value" }
            $i++
            if ($arg -like '*release') { $release = [string]$arguments[$i] } else { $prefix = [string]$arguments[$i] }
        } elseif ($arg -in @('-NoModifyPath', '--no-modify-path')) {
            $modifyPath = $false
        } elseif ($arg -in @('update', '-Update', '--update')) {
            $action = 'update'
            $modifyPath = $false
        } elseif ($arg -in @('rollback', '-Rollback', '--rollback')) {
            $action = 'rollback'
        } elseif ($arg -in @('-h', '--help', '-Help')) {
            Show-Usage
            return
        } else {
            Fail "unknown option: $arg (see -Help)"
        }
    }
    if ($release -and $release -cnotmatch $TagPattern) { Fail "not a Dewy toolchain release tag: $release" }
    if ($action -eq 'rollback' -and $release) { Fail 'rollback takes no release; it switches to the previous toolchain' }

    $onWindows = ($PSVersionTable.PSVersion.Major -lt 6) -or (Get-Variable -Name IsWindows -ValueOnly)
    if (-not $onWindows) { Fail 'install.ps1 is for Windows; use install.sh on Linux and macOS' }
    $arch = $env:PROCESSOR_ARCHITEW6432
    if (-not $arch) { $arch = $env:PROCESSOR_ARCHITECTURE }
    if ($arch -ne 'AMD64') { Fail "unsupported host: Windows $arch. Dewy toolchains exist for Windows x86_64, Linux x86_64/aarch64 and macOS arm64." }
    if (-not (Test-Path -LiteralPath (Join-Path $env:SystemRoot 'System32\tar.exe'))) { Fail 'tar.exe (Windows 10 1803 or later) is required' }

    if (-not $prefix) { $prefix = Join-Path $HOME '.dewy' }
    $prefix = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($prefix).TrimEnd('\')
    if ($prefix -match '[%"!^]') { Fail "the prefix must not contain % `" ! or ^: $prefix" }
    $toolchains = Join-Path $prefix 'toolchains'

    if ($action -eq 'rollback') {
        if (-not (Test-Path -LiteralPath $toolchains)) { Fail "no Dewy toolchains are installed in $prefix" }
        Enter-Lock $toolchains
        Invoke-Rollback $toolchains
        return
    }

    foreach ($dir in @($toolchains, (Join-Path $prefix 'bin'), (Join-Path $prefix 'libexec'))) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    Enter-Lock $toolchains
    # Leftovers from interrupted runs; the lock guarantees none is active.
    Get-ChildItem -LiteralPath $toolchains -Force | Where-Object { $_.Name -match '^\.(staging|trash|current)\.' } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    $State.Staging = Join-Path $toolchains ('.staging.' + [Guid]::NewGuid().ToString('N').Substring(0, 12))
    New-Item -ItemType Directory -Path $State.Staging | Out-Null
    $pointer = Read-Pointer $toolchains

    $channelUrl = $env:DEWY_INSTALL_CHANNEL_URL
    if (-not $channelUrl) { $channelUrl = 'https://dewy-lang.org/toolchain-channel.txt' }
    $downloadUrl = $env:DEWY_INSTALL_DOWNLOAD_URL
    if (-not $downloadUrl) { $downloadUrl = 'https://github.com/david-andrew/dewy-lang/releases/download' }
    $downloadUrl = $downloadUrl.TrimEnd('/', '\')
    $separator = '/'
    if ($downloadUrl -notmatch '^[A-Za-z][A-Za-z0-9+.-]+://') { $separator = '\' }

    # 1. Resolve the release and the digests that every download must match.
    if ($release) {
        $tag = $release
        $sums = Join-Path $State.Staging 'SHA256SUMS'
        Get-Download "$downloadUrl$separator$tag${separator}SHA256SUMS" $sums
        $archiveSum = Find-Sum $sums $Asset
        $installerSum = Find-Sum $sums 'install.ps1'
        if (-not $archiveSum -or -not $installerSum) { Fail "SHA256SUMS of $tag does not list $Asset and install.ps1" }
    } else {
        $channelFile = Join-Path $State.Staging 'channel.txt'
        Get-Download $channelUrl $channelFile
        $channel = Read-Channel $channelFile
        if ($null -eq $channel) { Fail "invalid toolchain channel at $channelUrl" }
        $tag = $channel.Tag
        if (-not $channel.Sums.ContainsKey($Asset) -or -not $channel.Sums.ContainsKey('install.ps1')) { Fail "the channel lists no $Asset or install.ps1" }
        $archiveSum = $channel.Sums[$Asset]
        $installerSum = $channel.Sums['install.ps1']
    }
    if ($tag -cnotmatch $TagPattern) { Fail "not a Dewy toolchain release tag: $tag" }
    $short = $Matches[1]
    if ($action -eq 'update' -and $tag -ceq $pointer.Current) { Info "Dewy is up to date ($tag)." }

    # 2. Download and verify the installer this release ships (the updater).
    $installer = Join-Path $State.Staging 'install.ps1'
    Get-Download "$downloadUrl$separator$tag${separator}install.ps1" $installer
    Assert-Sum $installer $installerSum 'install.ps1'

    # 3. Reuse a verified toolchain, or download, verify, extract and test one.
    $target = Join-Path $toolchains $tag
    if ((Test-Path -LiteralPath $target) -and $null -eq (Test-Toolchain $target $short) -and (Test-Smoke $target)) {
        Info "Using the installed toolchain $tag"
    } else {
        $archive = Join-Path $State.Staging $Asset
        Get-Download "$downloadUrl$separator$tag$separator$Asset" $archive
        Assert-Sum $archive $archiveSum $Asset
        $unpacked = Join-Path $State.Staging 'unpacked'
        Expand-Toolchain $archive $unpacked
        $problem = Test-Toolchain (Join-Path $unpacked 'dewy-core') $short
        if ($problem) { Fail "$Asset is not a $Platform toolchain for ${tag}: $problem; nothing was changed" }
        if (-not (Test-Smoke (Join-Path $unpacked 'dewy-core'))) { Fail 'the downloaded toolchain failed its smoke test; nothing was changed' }
        if (Test-Path -LiteralPath $target) {
            [IO.Directory]::Move($target, (Join-Path $toolchains ".trash.$tag.$PID"))
        }
        [IO.Directory]::Move((Join-Path $unpacked 'dewy-core'), $target)
    }

    # 4. Launchers and the updater, each replaced by rename.
    Write-Launcher $prefix 'dewy'
    Write-Launcher $prefix 'dewy-core'
    $updater = Join-Path $prefix 'libexec\dewy-install.ps1'
    if (-not (Test-Path -LiteralPath $updater) -or (Get-Sha256 $updater) -cne $installerSum) {
        $next = Join-Path $prefix "libexec\.dewy-install.ps1.$PID"
        Copy-Item -LiteralPath $installer -Destination $next
        Set-FileAtomically $next $updater
    }

    # 5. Activate: one rename switches the toolchain. Keep one previous one.
    $previous = $pointer.Current
    if ($previous -ceq $tag) { $previous = $pointer.Previous }
    Write-Pointer $toolchains $tag $previous
    Remove-Unused $toolchains @{ Current = $tag; Previous = $previous }

    $bin = Join-Path $prefix 'bin'
    if ($modifyPath) {
        Add-UserPath $bin
        if (-not (($env:PATH -split ';') -contains $bin)) { $env:PATH = "$bin;$env:PATH" }
    }
    $revision = Get-ReleaseField (Join-Path $target 'RELEASE') 'revision'
    Info "Installed Dewy toolchain $tag ($Platform, revision $revision)"
    Info "  compiler:  $target\bin\dewy-core.exe"
    Info "  launchers: $bin\dewy.cmd, $bin\dewy-core.cmd"
    if ($previous) { Info "  previous:  $previous (dewy rollback switches back)" }
    if (-not $modifyPath) { Info "Add $bin to PATH, or run $bin\dewy.cmd directly." }
}

$code = 0
try {
    Install-Dewy $argv
} catch {
    [Console]::Error.WriteLine("dewy install: $($_.Exception.Message)")
    $code = 1
} finally {
    if ($State.Staging -and (Test-Path -LiteralPath $State.Staging)) {
        Remove-Item -LiteralPath $State.Staging -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($State.Lock) { $State.Lock.Dispose() }
}
# A script file reports failure through its exit code; `irm | iex` must not
# close the caller's session.
if ($PSCommandPath) { exit $code }
if ($code) { $global:LASTEXITCODE = $code }
} $args

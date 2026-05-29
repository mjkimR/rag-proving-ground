@echo off
:: Install 'just' command runner (Windows)
setlocal

where just >nul 2>&1
if %ERRORLEVEL% == 0 (
    echo just is already installed:
    just --version
    exit /b 0
)

:: Prefer winget, then scoop, then Cargo
where winget >nul 2>&1
if %ERRORLEVEL% == 0 (
    echo Installing just via winget...
    winget install --id Casey.Just -e --source winget
    goto :done
)

where scoop >nul 2>&1
if %ERRORLEVEL% == 0 (
    echo Installing just via Scoop...
    scoop install just
    goto :done
)

where cargo >nul 2>&1
if %ERRORLEVEL% == 0 (
    echo Installing just via Cargo...
    cargo install just
    goto :done
)

echo ERROR: No supported package manager found (winget / scoop / cargo).
echo Install winget, Scoop (https://scoop.sh), or Rust/Cargo (https://rustup.rs) and retry.
exit /b 1

:done
echo just installed successfully:
just --version
endlocal

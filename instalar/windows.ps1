# Instala Portavoz Lite en Windows. Lo maneja la skill portavoz-instalar, que pide permiso antes de cada pieza.
#
# Las piezas que falten se instalan con winget (el instalador de programas que trae Windows):
#   Node (OpenJS.NodeJS.LTS), Python 3.12 (Python.Python.3.12), FFmpeg (Gyan.FFmpeg) y git (Git.Git).
# Primero se prueba "solo para este usuario" (sin pedir permiso de administrador); si el programa no lo permite, se
# instala normal y Windows puede mostrar su ventanita de permiso.
# La ruta entera de Python queda en el .env como PORTAVOZ_PYTHON (nunca el Python falso de la tienda de Microsoft, que
# vive en WindowsApps y sólo abre la tienda). El arranque suma esa carpeta a las que se buscan programas.
#
# Uso: powershell -ExecutionPolicy Bypass -File instalar\windows.ps1 revisar | traer node|python|ffmpeg|git |
#      preparar | icono | probar-llaves | abrir
# Cada paso imprime UNA linea de JSON al final. Escrito para el PowerShell 5.1 que trae Windows.
param([string]$Paso = "", [string]$Pieza = "")

$ErrorActionPreference = "Continue"
$Raiz = Split-Path -Parent $PSScriptRoot
$Env = Join-Path $Raiz ".env"
$Escritorio = [Environment]::GetFolderPath("Desktop")
$Icono = Join-Path $Escritorio "Portavoz Lite.lnk"
$Ids = @{ node = "OpenJS.NodeJS.LTS"; python = "Python.Python.3.12"; ffmpeg = "Gyan.FFmpeg"; git = "Git.Git" }

function Write-Linea($datos) { $datos | ConvertTo-Json -Compress -Depth 5 }

function Exit-Mal($paso, $motivo) {
  Write-Linea ([ordered]@{ paso = $paso; ok = $false; motivo = $motivo })
  exit 1
}

# Despues de instalar algo, la lista de carpetas donde se buscan programas se vuelve a leer de Windows.
function Update-Carpetas {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

function Read-PortavozEnv {
  $datos = @{}
  if (Test-Path $Env) {
    foreach ($l in [IO.File]::ReadAllLines($Env)) {
      $t = $l.Trim()
      if ($t -and -not $t.StartsWith("#") -and $t.Contains("=")) {
        $i = $t.IndexOf("=")
        $datos[$t.Substring(0, $i).Trim()] = $t.Substring($i + 1).Trim().Trim('"', "'")
      }
    }
  }
  return $datos
}

# Cambia (o agrega) una linea NOMBRE=valor del .env y deja todas las demas como estaban.
function Set-PortavozEnv($nombre, $valor) {
  $lineas = New-Object System.Collections.Generic.List[string]
  if (Test-Path $Env) { foreach ($l in [IO.File]::ReadAllLines($Env)) { $lineas.Add($l.TrimStart([char]0xFEFF)) } }
  $hecho = $false
  for ($i = 0; $i -lt $lineas.Count; $i++) {
    if ($lineas[$i] -match "^\s*$([regex]::Escape($nombre))\s*=") { $lineas[$i] = "$nombre=$valor"; $hecho = $true }
  }
  if (-not $hecho) { $lineas.Add("$nombre=$valor") }
  [IO.File]::WriteAllText($Env, (($lineas -join "`n") + "`n"), (New-Object Text.UTF8Encoding $false))
}

function Test-Python($ruta) {
  if (-not $ruta -or -not (Test-Path $ruta) -or $ruta -like "*\WindowsApps\*") { return $null }
  $v = & $ruta -c "import sys;print('%d.%d.%d'%sys.version_info[:3]);sys.exit(0 if sys.version_info>=(3,10) else 1)" 2>$null
  if ($LASTEXITCODE -eq 0 -and $v) { return "$v".Trim() }
  return $null
}

# El Python que va a usar Portavoz Lite: el del .env, o el primero de verdad que aparezca.
function Find-PortavozPython {
  $env_ = Read-PortavozEnv
  $candidatos = @()
  if ($env_["PORTAVOZ_PYTHON"]) { $candidatos += $env_["PORTAVOZ_PYTHON"] }
  $candidatos += @(Get-Command python -All -ErrorAction SilentlyContinue | ForEach-Object { $_.Source })
  $candidatos += @(Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe", "$env:ProgramFiles\Python3*\python.exe" -ErrorAction SilentlyContinue |
      Sort-Object FullName -Descending | ForEach-Object { $_.FullName })
  foreach ($c in $candidatos) {
    $v = Test-Python $c
    if ($v) { return @{ ruta = $c; version = $v } }
  }
  return $null
}

function Test-Programa($nombre, $argumento) {
  $c = Get-Command $nombre -ErrorAction SilentlyContinue
  if (-not $c) { return $false }
  & $c.Source $argumento *> $null
  return ($LASTEXITCODE -eq 0)
}

function Test-NodeSirve {
  $v = (& node -v 2>$null)
  if (-not $v) { return $false }
  $p = "$v".Trim().TrimStart("v").Split(".")
  return ([int]$p[0] -gt 20 -or ([int]$p[0] -eq 20 -and [int]$p[1] -ge 9))
}

function Invoke-Revisar {
  $py = Find-PortavozPython
  $piezas = $false
  if ($py) { & $py.ruta -c "import numpy, fontTools" *> $null; $piezas = ($LASTEXITCODE -eq 0) }
  $nodev = ""
  if (Get-Command node -ErrorAction SilentlyContinue) { $nodev = "$(& node -v 2>$null)".Trim() }
  Write-Linea ([ordered]@{
      paso = "revisar"; ok = $true; sistema = "windows"; carpeta = $Raiz
      en_onedrive = ($Raiz -like "*OneDrive*")
      winget = [bool](Get-Command winget -ErrorAction SilentlyContinue)
      git = (Test-Programa git "--version")
      node = (Test-NodeSirve); node_version = $nodev
      python = [bool]$py; python_version = $(if ($py) { $py.version } else { "" }); python_ruta = $(if ($py) { $py.ruta } else { "" })
      piezas_python = $piezas
      ffmpeg = (Test-Programa ffmpeg "-version"); ffprobe = (Test-Programa ffprobe "-version")
      env = (Test-Path $Env); icono = (Test-Path $Icono)
    })
}

function Invoke-Traer($pieza) {
  if (-not $Ids.ContainsKey($pieza)) { Exit-Mal "traer" "pieza-desconocida" }
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { Exit-Mal "traer" "sin-winget" }
  $comun = @("install", "-e", "--id", $Ids[$pieza], "--silent", "--accept-source-agreements", "--accept-package-agreements", "--disable-interactivity")
  & winget @comun --scope user *> $null
  if ($LASTEXITCODE -ne 0) { & winget @comun *> $null }
  Update-Carpetas
  $ok = switch ($pieza) {
    "node" { Test-NodeSirve }
    "git" { Test-Programa git "--version" }
    "ffmpeg" { (Test-Programa ffmpeg "-version") -and (Test-Programa ffprobe "-version") }
    "python" {
      $py = Find-PortavozPython
      if ($py) { Set-PortavozEnv "PORTAVOZ_PYTHON" $py.ruta }
      [bool]$py
    }
  }
  if (-not $ok) { Exit-Mal "traer" "no-quedo" }
  Write-Linea ([ordered]@{ paso = "traer"; pieza = $pieza; ok = $true })
}

function Invoke-Preparar {
  $py = Find-PortavozPython
  if (-not $py) { Exit-Mal "preparar" "sin-python" }
  if (-not (Read-PortavozEnv)["PORTAVOZ_PYTHON"]) { Set-PortavozEnv "PORTAVOZ_PYTHON" $py.ruta }
  & $py.ruta -m pip install --disable-pip-version-check -q -r (Join-Path $Raiz "motor\requisitos.txt") *> $null
  if ($LASTEXITCODE -ne 0) { Exit-Mal "preparar" "python" }
  Push-Location (Join-Path $Raiz "estudio")
  try {
    & npm.cmd ci --no-audit --no-fund *> $null
    if ($LASTEXITCODE -ne 0) { Exit-Mal "preparar" "piezas" }
    & npm.cmd run build *> $null
    if ($LASTEXITCODE -ne 0) { Exit-Mal "preparar" "armado" }
  } finally { Pop-Location }
  Write-Linea ([ordered]@{ paso = "preparar"; ok = $true })
}

function Invoke-Icono {
  $node = (Get-Command node -ErrorAction SilentlyContinue).Source
  if (-not $node) { Exit-Mal "icono" "sin-node" }
  $sh = New-Object -ComObject WScript.Shell
  $a = $sh.CreateShortcut($Icono)
  $a.TargetPath = $node
  $a.Arguments = '"' + (Join-Path $Raiz "estudio\scripts\arrancar.mjs") + '"'
  $a.WorkingDirectory = Join-Path $Raiz "estudio"
  $a.WindowStyle = 7
  $a.IconLocation = (Join-Path $Raiz "marca\portavoz.ico") + ",0"
  $a.Description = "Abre Portavoz Lite"
  $a.Save()
  Write-Linea ([ordered]@{ paso = "icono"; ok = (Test-Path $Icono); donde = $Icono })
}

function Invoke-ProbarLlaves {
  $py = Find-PortavozPython
  if (-not $py) { Exit-Mal "probar-llaves" "sin-python" }
  & $py.ruta -B (Join-Path $Raiz "motor\chequeo.py") --llaves
}

switch ($Paso) {
  "revisar" { Invoke-Revisar }
  "traer" { Invoke-Traer $Pieza }
  "preparar" { Invoke-Preparar }
  "icono" { Invoke-Icono }
  "probar-llaves" { Invoke-ProbarLlaves }
  "abrir" {
    if (-not (Test-Path $Icono)) { Exit-Mal "abrir" "sin-icono" }
    Start-Process $Icono
    Write-Linea ([ordered]@{ paso = "abrir"; ok = $true })
  }
  default { Exit-Mal $Paso "paso-desconocido" }
}

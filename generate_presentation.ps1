<#
.SYNOPSIS
    Genera los 18 clips de la presentación "IA en Falabella" en orden,
    con coherencia visual (style pack), logo overlay y renombrado final.

.DESCRIPTION
    Fase 0: Verificación de prerequisitos
    Fase 1: Generar clip_4_1a (fuente de dependencia para clip de colapso)
    Fase 2: Extraer último frame de clip_4_1a como referencia
    Fase 3: Generar los 17 clips restantes de la presentación
    Fase 4: Aplicar logo overlay a todos los clips (si logo.png y ffmpeg disponibles)
    Fase 5: Copiar a carpeta final con nombres secuenciales

.NOTES
    Ejecutar desde la raíz del proyecto con el venv activado, o el script lo activa.
    Requiere: Python 3.10+, venv con dependencias, ffmpeg (para logo y frame extraction).
#>

$ErrorActionPreference = "Stop"

# ============================================================================
# CONFIGURACION
# ============================================================================

$ProjectDir   = $PSScriptRoot
$OutputDir    = Join-Path $ProjectDir "output"
$FinalDir     = Join-Path $OutputDir "presentacion"
$ImagesDir    = Join-Path $ProjectDir "input\images"
$LogoPath     = Join-Path $ProjectDir "input\images\logo.png"
$VenvActivate = Join-Path $ProjectDir ".venv\Scripts\Activate.ps1"
$StylePack    = "falabella_v1"
$Variants     = 1

$LogoPosition = "bottom-right"
$LogoScale    = 0.08
$LogoOpacity  = 0.85
$LogoMargin   = 30

# Secuencia final de la presentación: orden -> [sección, clip_id, nombre descriptivo]
$Sequence = @(
    @{ Order =  1; Section = "INTRO";   ClipId = "clip_4_1a";          Name = "los_3_pilares" }
    @{ Order =  2; Section = "INTRO";   ClipId = "clip_4_1a_collapse"; Name = "colapso_simulacion" }
    @{ Order =  3; Section = "GEMELOS"; ClipId = "clip_3a_2b";         Name = "digitalizacion" }
    @{ Order =  4; Section = "GEMELOS"; ClipId = "clip_3a_2a";         Name = "pausa_escaneo" }
    @{ Order =  5; Section = "GEMELOS"; ClipId = "clip_3a_4a";         Name = "impacto_mejora" }
    @{ Order =  6; Section = "GEMELOS"; ClipId = "clip_5_1a_gemelos";  Name = "vista_aerea_digital" }
    @{ Order =  7; Section = "RL";      ClipId = "clip_3b_2a";         Name = "agentes_caoticos" }
    @{ Order =  8; Section = "RL";      ClipId = "clip_3b_2b";         Name = "agentes_optimizados" }
    @{ Order =  9; Section = "RL";      ClipId = "clip_5_1a_rl";       Name = "zonificacion_dinamica" }
    @{ Order = 10; Section = "MODELO";  ClipId = "clip_3b_4a";         Name = "optimizacion_rutas" }
    @{ Order = 11; Section = "MODELO";  ClipId = "clip_3c_1a";         Name = "problema_dotacion" }
    @{ Order = 12; Section = "MODELO";  ClipId = "clip_3c_1a_demand";  Name = "demanda_dinamica" }
    @{ Order = 13; Section = "MODELO";  ClipId = "clip_3c_3a";         Name = "operacion_balanceada" }
    @{ Order = 14; Section = "ADIC";    ClipId = "clip_4_2a";          Name = "lectura_documentos" }
    @{ Order = 15; Section = "ADIC";    ClipId = "clip_4_2b";          Name = "alertas_inteligentes" }
    @{ Order = 16; Section = "ADIC";    ClipId = "clip_4_2c";          Name = "contratos_ia" }
    @{ Order = 17; Section = "ADIC";    ClipId = "clip_3b_3b";         Name = "reslotting" }
    @{ Order = 18; Section = "CIERRE";  ClipId = "clip_5_1b";          Name = "vista_final" }
)

# ============================================================================
# FUNCIONES
# ============================================================================

function Write-Phase {
    param([string]$Phase, [string]$Description)
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor DarkGray
    Write-Host "  FASE $Phase : $Description" -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor DarkGray
}

function Write-Ok    { param([string]$Msg) Write-Host "  [OK] $Msg" -ForegroundColor Green }
function Write-Warn  { param([string]$Msg) Write-Host "  [!!] $Msg" -ForegroundColor Yellow }
function Write-Fail  { param([string]$Msg) Write-Host "  [XX] $Msg" -ForegroundColor Red }
function Write-Info  { param([string]$Msg) Write-Host "  [..] $Msg" -ForegroundColor Gray }

function Find-Ffmpeg {
    # 1) System PATH
    $cmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    # 2) Python imageio-ffmpeg (bundled binary inside the venv)
    try {
        $pyPath = python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())" 2>$null
        if ($pyPath -and (Test-Path $pyPath)) { return $pyPath.Trim() }
    } catch {}

    return $null
}

function Invoke-LogoOverlay {
    param(
        [string]$FfmpegExe,
        [string]$VideoPath,
        [string]$Logo,
        [string]$OutPath,
        [string]$Position,
        [float]$Scale,
        [float]$Opacity,
        [int]$Margin
    )

    $scaleFilter = "scale=iw*${Scale}:-1"
    if ($Opacity -lt 1.0) {
        $scaleFilter += ",format=rgba,colorchannelmixer=aa=$Opacity"
    }

    $posMap = @{
        "top-left"     = "x=${Margin}:y=${Margin}"
        "top-right"    = "x=W-w-${Margin}:y=${Margin}"
        "bottom-left"  = "x=${Margin}:y=H-h-${Margin}"
        "bottom-right" = "x=W-w-${Margin}:y=H-h-${Margin}"
        "center"       = "x=(W-w)/2:y=(H-h)/2"
    }
    $posExpr = $posMap[$Position]
    if (-not $posExpr) { $posExpr = $posMap["bottom-right"] }

    $filterComplex = "[1:v]${scaleFilter}[logo];[0:v][logo]overlay=${posExpr}"

    $proc = Start-Process -FilePath $FfmpegExe `
        -ArgumentList "-y -i `"$VideoPath`" -i `"$Logo`" -filter_complex `"$filterComplex`" -codec:a copy `"$OutPath`"" `
        -NoNewWindow -Wait -PassThru -RedirectStandardError (Join-Path $env:TEMP "ffmpeg_err.txt")

    return ($proc.ExitCode -eq 0)
}

# ============================================================================
# FASE 0: PREREQUISITOS
# ============================================================================

Write-Phase "0" "Verificacion de prerequisitos"

Set-Location $ProjectDir

# Activar venv si no está activo
if (-not $env:VIRTUAL_ENV) {
    if (Test-Path $VenvActivate) {
        Write-Info "Activando entorno virtual..."
        & $VenvActivate
        Write-Ok "Venv activado: $env:VIRTUAL_ENV"
    } else {
        Write-Fail "No se encontro .venv\Scripts\Activate.ps1"
        Write-Fail "Ejecuta: python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt"
        exit 1
    }
} else {
    Write-Ok "Venv ya activo: $env:VIRTUAL_ENV"
}

# Verificar python
try {
    $pyVer = python --version 2>&1
    Write-Ok "Python: $pyVer"
} catch {
    Write-Fail "Python no encontrado"; exit 1
}

# Verificar ffmpeg (sistema o imageio-ffmpeg del venv)
$FfmpegExe = Find-Ffmpeg
$hasFfmpeg = $null -ne $FfmpegExe
if ($hasFfmpeg) {
    Write-Ok "ffmpeg encontrado: $FfmpegExe"
} else {
    Write-Warn "ffmpeg no encontrado. Se omitira extraccion de frames y logo overlay."
    Write-Warn "Instala con: pip install imageio-ffmpeg"
}

# Verificar logo
$hasLogo = Test-Path $LogoPath
if ($hasLogo) {
    Write-Ok "Logo encontrado: $LogoPath"
} else {
    Write-Warn "Logo no encontrado en $LogoPath. Se omitira logo overlay."
}

# Crear directorios
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
New-Item -ItemType Directory -Force -Path $FinalDir  | Out-Null
New-Item -ItemType Directory -Force -Path $ImagesDir  | Out-Null

# Dry-run de verificacion rapida
Write-Info "Verificando configuracion con dry-run..."
python main.py --dry-run --presentation --style-pack $StylePack 2>&1 | Select-Object -Last 10 | ForEach-Object { Write-Info $_ }

Write-Host ""
Write-Host "  Se van a generar $($Sequence.Count) clips con:" -ForegroundColor White
Write-Host "    Style pack : $StylePack" -ForegroundColor White
Write-Host "    Variantes  : $Variants" -ForegroundColor White
Write-Host "    Logo       : $(if ($hasLogo -and $hasFfmpeg) { 'SI' } else { 'NO (falta logo o ffmpeg)' })" -ForegroundColor White
Write-Host ""

$confirm = Read-Host "  Continuar? (S/n)"
if ($confirm -and $confirm -notin @("S", "s", "si", "Si", "SI", "y", "Y", "yes", "")) {
    Write-Host "  Cancelado." -ForegroundColor Yellow
    exit 0
}

$startTime = Get-Date

# ============================================================================
# FASE 1: GENERAR clip_4_1a (fuente de dependencia)
# ============================================================================

Write-Phase "1" "Generando clip_4_1a (base para clip de colapso)"

python main.py --clips clip_4_1a --style-pack $StylePack --variants $Variants

if ($LASTEXITCODE -ne 0) {
    Write-Fail "Error generando clip_4_1a"
    Write-Warn "Continuando de todas formas..."
}

$clip4_1a_path = Join-Path $OutputDir "clip_4_1a.mp4"
if (Test-Path $clip4_1a_path) {
    Write-Ok "clip_4_1a.mp4 generado correctamente"
} else {
    Write-Warn "clip_4_1a.mp4 no encontrado. clip_4_1a_collapse se generara sin frame de referencia."
}

# ============================================================================
# FASE 2: EXTRAER ULTIMO FRAME DE clip_4_1a
# ============================================================================

Write-Phase "2" "Extrayendo ultimo frame de clip_4_1a como referencia"

$frameOutput = Join-Path $ImagesDir "ref_4_1a_lastframe.png"

if ($hasFfmpeg -and (Test-Path $clip4_1a_path)) {
    Write-Info "Extrayendo frame..."
    & $FfmpegExe -y -sseof -0.04 -i $clip4_1a_path -frames:v 1 -update 1 $frameOutput 2>$null

    if (Test-Path $frameOutput) {
        Write-Ok "Frame extraido -> $frameOutput"
        Write-Ok "clip_4_1a_collapse usara este frame como imagen de referencia"
    } else {
        Write-Warn "No se pudo extraer frame. clip_4_1a_collapse se genera sin referencia."
    }
} else {
    if (-not $hasFfmpeg) {
        Write-Warn "ffmpeg no disponible. Saltando extraccion de frame."
    } else {
        Write-Warn "clip_4_1a.mp4 no existe. Saltando extraccion de frame."
    }
}

# ============================================================================
# FASE 3: GENERAR LOS 17 CLIPS RESTANTES
# ============================================================================

Write-Phase "3" "Generando 17 clips restantes de la presentacion"

$remainingClips = @(
    "clip_4_1a_collapse"
    "clip_3a_2b"
    "clip_3a_2a"
    "clip_3a_4a"
    "clip_5_1a_gemelos"
    "clip_3b_2a"
    "clip_3b_2b"
    "clip_5_1a_rl"
    "clip_3b_4a"
    "clip_3c_1a"
    "clip_3c_1a_demand"
    "clip_3c_3a"
    "clip_4_2a"
    "clip_4_2b"
    "clip_4_2c"
    "clip_3b_3b"
    "clip_5_1b"
) -join ","

Write-Info "Clips: $($remainingClips -replace ',', ', ')"
Write-Info "Esto puede tomar varios minutos por clip..."

python main.py --clips $remainingClips --style-pack $StylePack --variants $Variants

if ($LASTEXITCODE -ne 0) {
    Write-Warn "Algunos clips pudieron haber fallado. Revisa el log arriba."
}

# Verificar cuántos se generaron
$generatedCount = 0
foreach ($entry in $Sequence) {
    $mp4 = Join-Path $OutputDir "$($entry.ClipId).mp4"
    if (Test-Path $mp4) { $generatedCount++ }
}
Write-Info "$generatedCount / $($Sequence.Count) clips generados exitosamente"

# ============================================================================
# FASE 4: APLICAR LOGO OVERLAY
# ============================================================================

Write-Phase "4" "Aplicando logo overlay a todos los clips"

if ($hasLogo -and $hasFfmpeg) {
    $logoOk = 0
    $logoFail = 0

    foreach ($entry in $Sequence) {
        $srcPath = Join-Path $OutputDir "$($entry.ClipId).mp4"
        $dstPath = Join-Path $OutputDir "$($entry.ClipId)_logo.mp4"

        if (-not (Test-Path $srcPath)) {
            Write-Warn "Saltando $($entry.ClipId) (no generado)"
            $logoFail++
            continue
        }

        Write-Info "Logo -> $($entry.ClipId)..."
        $result = Invoke-LogoOverlay `
            -FfmpegExe $FfmpegExe `
            -VideoPath $srcPath `
            -Logo $LogoPath `
            -OutPath $dstPath `
            -Position $LogoPosition `
            -Scale $LogoScale `
            -Opacity $LogoOpacity `
            -Margin $LogoMargin

        if ($result -and (Test-Path $dstPath)) {
            Write-Ok "$($entry.ClipId)_logo.mp4"
            $logoOk++
        } else {
            Write-Warn "Fallo logo para $($entry.ClipId). Se usara version sin logo."
            $logoFail++
        }
    }

    Write-Info "Logo aplicado: $logoOk OK, $logoFail fallidos/saltados"
} else {
    Write-Warn "Logo overlay omitido ($(if (-not $hasLogo) { 'logo.png falta' } else { 'ffmpeg no encontrado' }))"
    Write-Info "Los clips se copiaran sin logo en la fase final."
}

# ============================================================================
# FASE 5: COPIAR A CARPETA FINAL CON NOMBRES SECUENCIALES
# ============================================================================

Write-Phase "5" "Creando secuencia final en output\presentacion\"

# Limpiar carpeta de presentación
Get-ChildItem $FinalDir -Filter "*.mp4" -ErrorAction SilentlyContinue | Remove-Item -Force

$copied = 0
$missing = 0

foreach ($entry in $Sequence) {
    $order   = "{0:D2}" -f $entry.Order
    $section = $entry.Section
    $name    = $entry.Name
    $clipId  = $entry.ClipId

    $finalName = "${order}_${section}_${name}.mp4"

    # Preferir version con logo; si no existe, usar la original
    $logoFile = Join-Path $OutputDir "${clipId}_logo.mp4"
    $rawFile  = Join-Path $OutputDir "${clipId}.mp4"

    $sourceFile = $null
    $hasLogoTag = ""
    if (Test-Path $logoFile) {
        $sourceFile = $logoFile
        $hasLogoTag = " [+logo]"
    } elseif (Test-Path $rawFile) {
        $sourceFile = $rawFile
    }

    if ($sourceFile) {
        $destFile = Join-Path $FinalDir $finalName
        Copy-Item -Path $sourceFile -Destination $destFile -Force
        Write-Ok "${finalName}${hasLogoTag}"
        $copied++
    } else {
        Write-Fail "${finalName} -> FALTA (${clipId} no generado)"
        $missing++
    }
}

# ============================================================================
# RESUMEN FINAL
# ============================================================================

$elapsed = (Get-Date) - $startTime

Write-Host ""
Write-Host ("=" * 70) -ForegroundColor DarkGray
Write-Host "  RESUMEN FINAL" -ForegroundColor Cyan
Write-Host ("=" * 70) -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Clips copiados   : $copied / $($Sequence.Count)" -ForegroundColor $(if ($copied -eq $Sequence.Count) { "Green" } else { "Yellow" })
Write-Host "  Clips faltantes  : $missing" -ForegroundColor $(if ($missing -eq 0) { "Green" } else { "Red" })
Write-Host "  Carpeta final    : $FinalDir" -ForegroundColor White
Write-Host "  Tiempo total     : $($elapsed.ToString('hh\:mm\:ss'))" -ForegroundColor White
Write-Host ""

if ($copied -gt 0) {
    Write-Host "  Archivos en orden de presentacion:" -ForegroundColor White
    Get-ChildItem $FinalDir -Filter "*.mp4" | Sort-Object Name | ForEach-Object {
        $sizeMb = [math]::Round($_.Length / 1MB, 1)
        Write-Host "    $($_.Name)  ($sizeMb MB)" -ForegroundColor Gray
    }
}

Write-Host ""
if ($missing -gt 0) {
    Write-Host "  Para regenerar clips faltantes, ejecuta:" -ForegroundColor Yellow
    $missingIds = ($Sequence | Where-Object {
        $p = Join-Path $OutputDir "$($_.ClipId).mp4"
        -not (Test-Path $p)
    } | ForEach-Object { $_.ClipId }) -join ","
    Write-Host "    python main.py --clips $missingIds --style-pack $StylePack --variants $Variants" -ForegroundColor Yellow
    Write-Host "  Y luego vuelve a ejecutar este script." -ForegroundColor Yellow
}

Write-Host ""

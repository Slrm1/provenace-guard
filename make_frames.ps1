Add-Type -AssemblyName System.Drawing
$frameDir = Join-Path $PSScriptRoot 'video_frames'
New-Item -ItemType Directory -Path $frameDir -Force | Out-Null
$capturePath = Join-Path $PSScriptRoot 'demo_capture.json'
if (-not (Test-Path $capturePath)) { throw 'Run python record_demo.py first to capture live HTTP responses.' }
$capture = Get-Content $capturePath -Raw | ConvertFrom-Json
$firstId = $capture.submissions[0].body.content_id
$rateCodes = $capture.rate_limit_statuses_after_first_three -join '  '

$slides = @(
    @{Title='PROVENANCE GUARD'; Body=@('Live local HTTP demonstration', 'Real responses from the Flask API', 'Captured by python record_demo.py')},
    @{Title='START THE API'; Body=@('> python record_demo.py', 'Flask serves on 127.0.0.1', "GET /health  ->  HTTP $($capture.health.http_status)", "Response: $($capture.health.body.status)")},
    @{Title='SUBMIT WRITING'; Body=@('POST /submit  {text, creator_id}', "HTTP $($capture.submissions[0].http_status)  ->  $($capture.submissions[0].body.attribution)", "AI-likeness: $($capture.submissions[0].body.ai_likeness_score)", "Confidence: $($capture.submissions[0].body.confidence)")},
    @{Title='SIGNALS IN THE RESPONSE'; Body=@("Structural: $($capture.submissions[0].body.signals.structural)", "Formulaic: $($capture.submissions[0].body.signals.formulaic)", 'Weighted score: 0.55 x structure + 0.45 x phrases', 'Scores are indicators, not proof of authorship.')},
    @{Title='THREE ACTUAL RESULTS'; Body=@("AI-style text: $($capture.submissions[0].body.attribution) / $($capture.submissions[0].body.confidence)", "Casual review: $($capture.submissions[1].body.attribution) / $($capture.submissions[1].body.confidence)", "Tiny poem: $($capture.submissions[2].body.attribution) / $($capture.submissions[2].body.confidence)", 'Short writing receives an uncertain label.')},
    @{Title='THE READER LABEL'; Body=@('Likely AI response says:', 'Strong indicators of AI generation.', 'This assessment is not proof of authorship.', 'The creator can appeal.')},
    @{Title='APPEAL THE RESULT'; Body=@('POST /appeal  {content_id, creator_id,', 'creator_reasoning}', "HTTP $($capture.appeal.http_status)  ->  $($capture.appeal.body.status)", "Content ID: $($firstId.Substring(0, 18))...")},
    @{Title='CHECK STORED STATUS'; Body=@('GET /content/<content_id>', "HTTP $($capture.content_after_appeal.http_status)", "Current status: $($capture.content_after_appeal.body.status)", 'The original decision remains in the audit trail.')},
    @{Title='INSPECT AUDIT EVENTS'; Body=@('GET /log', "HTTP $($capture.audit_log.http_status)  ->  $($capture.audit_log.body.entries.Count) events", 'Three decisions and one linked appeal', 'Each decision includes time, signals and score.')},
    @{Title='TEST THE RATE LIMIT'; Body=@('POST /submit repeatedly from one IP', $rateCodes, 'The final two requests return HTTP 429.', 'Limit: 10 per minute and 100 per day.')},
    @{Title='DESIGN DECISIONS'; Body=@('Likely AI requires a score of at least 0.85.', 'Short or conflicting evidence stays uncertain.', 'Creators can appeal a decision.', 'This avoids an automatic accusation on weak evidence.')},
    @{Title='RUN IT YOURSELF'; Body=@('python -m unittest discover -s tests -v', 'python record_demo.py', 'See demo_capture.json for full HTTP responses.', 'See planning.md and README.md for the design.')}
)

$width = 960
$height = 540
$background = [System.Drawing.Color]::FromArgb(13, 22, 40)
$accent = [System.Drawing.Color]::FromArgb(79, 225, 193)
$white = [System.Drawing.Color]::FromArgb(236, 244, 250)
$muted = [System.Drawing.Color]::FromArgb(165, 187, 205)
$titleFont = New-Object System.Drawing.Font('Segoe UI', 34, [System.Drawing.FontStyle]::Bold)
$bodyFont = New-Object System.Drawing.Font('Segoe UI', 23)
$smallFont = New-Object System.Drawing.Font('Segoe UI', 14)
$backgroundBrush = New-Object System.Drawing.SolidBrush($background)
$accentBrush = New-Object System.Drawing.SolidBrush($accent)
$whiteBrush = New-Object System.Drawing.SolidBrush($white)
$mutedBrush = New-Object System.Drawing.SolidBrush($muted)
$accentPen = New-Object System.Drawing.Pen($accent, 4)

for ($i = 0; $i -lt $slides.Count; $i++) {
    $bitmap = New-Object System.Drawing.Bitmap($width, $height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $graphics.FillRectangle($backgroundBrush, 0, 0, $width, $height)
    $graphics.FillRectangle($accentBrush, 54, 68, 12, 62)
    $graphics.DrawString($slides[$i].Title, $titleFont, $whiteBrush, 87, 65)
    $graphics.DrawLine($accentPen, 57, 156, 905, 156)
    for ($j = 0; $j -lt $slides[$i].Body.Count; $j++) {
        $graphics.DrawString($slides[$i].Body[$j], $bodyFont, $whiteBrush, 60, (200 + 61 * $j))
    }
    $graphics.DrawString('Provenance Guard  |  captured live HTTP responses', $smallFont, $mutedBrush, 60, 492)
    $graphics.DrawString("$($i+1) / $($slides.Count)", $smallFont, $accentBrush, 851, 492)
    $path = Join-Path $frameDir ('{0:D2}.jpg' -f $i)
    $bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Jpeg)
    $graphics.Dispose()
    $bitmap.Dispose()
}

$titleFont.Dispose(); $bodyFont.Dispose(); $smallFont.Dispose()
$backgroundBrush.Dispose(); $accentBrush.Dispose(); $whiteBrush.Dispose(); $mutedBrush.Dispose(); $accentPen.Dispose()
Write-Output "Created $($slides.Count) caption slides in $frameDir"

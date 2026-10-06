Add-Type -AssemblyName System.Drawing
$frameDir = Join-Path $PSScriptRoot 'video_frames'
New-Item -ItemType Directory -Path $frameDir -Force | Out-Null

$slides = @(
    @{Title='PROVENANCE GUARD'; Body=@('A cautious writing-attribution API', 'Project 4 portfolio walkthrough', 'Signals  >  score  >  label  >  appeal')},
    @{Title='THE PROBLEM'; Body=@('A detector cannot prove who wrote a passage.', 'Readers need context without false certainty.', 'Creators need a clear path to contest a result.')},
    @{Title='SUBMISSION FLOW'; Body=@('POST /submit with text and creator_id', 'Validate  >  score distinct signals', 'Choose a careful label  >  save audit event', 'Return content_id, confidence, and label')},
    @{Title='TWO LOCAL SIGNALS'; Body=@('Structure: sentence rhythm and punctuation', 'Formulaic language: stock phrases per word', 'Optional Groq: semantic style assessment', 'Each signal can be wrong on its own.')},
    @{Title='UNCERTAINTY RULES'; Body=@('AI-like score >= 0.85: likely AI', 'Score <= 0.30: likely human', 'Middle, short, or conflicting: uncertain', 'Scores are indicators, not proof.')},
    @{Title='ACTUAL DEMO SCORES'; Body=@('AI-style text: 0.8875  >  likely AI', 'Casual review: 0.2531  >  likely human', 'Tiny poem: 0.2750  >  uncertain', 'The short-text guard overrides its score.')},
    @{Title='READER LABELS'; Body=@('Likely AI: strong indicators, appeal offered', 'Likely human: strong human indicators', 'Uncertain: no authorship claim is made', 'Exact label text is in README.md.')},
    @{Title='APPEAL FLOW'; Body=@('POST /appeal with content_id, creator_id,', 'and the creator reasoning', 'Matching creator  >  under_review', 'A second linked audit event is written.')},
    @{Title='AUDIT AND SAFETY'; Body=@('Three real decisions plus a linked appeal.', 'Raw text is not saved; its SHA-256 hash is.', '10 submissions per minute; 100 per day per IP.', 'The demo reaches HTTP 429 twice.')},
    @{Title='TRY THE LIVE DEMO'; Body=@('pip install -r requirements.txt', 'python -m unittest discover -s tests -v', 'python demo.py', 'The demo prints three submissions and an appeal.')},
    @{Title='DESIGN LIMITS'; Body=@('Short poems can look too repetitive.', 'Formal human writing can look formulaic.', 'Edited AI text may evade these indicators.', 'Identity and audit access need production controls.')},
    @{Title='THANK YOU'; Body=@('Source: app.py and planning.md', 'Evidence: tests/test_app.py and demo.py', 'See README.md for the exact labels and API.')}
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
    $graphics.DrawString('Provenance Guard  |  captioned project tour', $smallFont, $mutedBrush, 60, 492)
    $graphics.DrawString("$($i+1) / $($slides.Count)", $smallFont, $accentBrush, 851, 492)
    $path = Join-Path $frameDir ('{0:D2}.jpg' -f $i)
    $bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Jpeg)
    $graphics.Dispose()
    $bitmap.Dispose()
}

$titleFont.Dispose(); $bodyFont.Dispose(); $smallFont.Dispose()
$backgroundBrush.Dispose(); $accentBrush.Dispose(); $whiteBrush.Dispose(); $mutedBrush.Dispose(); $accentPen.Dispose()
Write-Output "Created $($slides.Count) caption slides in $frameDir"

$ErrorActionPreference = "Stop"

# 1. Update addons.xml.md5
$md5 = [System.Security.Cryptography.MD5]::Create()
$fileBytes = [System.IO.File]::ReadAllBytes("addons.xml")
$hashBytes = $md5.ComputeHash($fileBytes)
$md5String = ($hashBytes | ForEach-Object { $_.ToString("x2") }) -join ""
[System.IO.File]::WriteAllText("addons.xml.md5", $md5String)
Write-Host "Updated addons.xml.md5 to: $md5String"

# Helper function to create clean Zip file with directory structure and forward slashes
function Create-KodiZip {
    param(
        [string]$sourceDirName,  # e.g. "repository.movierulz" or "plugin.video.movierulz"
        [string]$zipFileName     # e.g. "repository.movierulz-1.0.0.zip"
    )
    
    $zipPath = Join-Path (Get-Location) $zipFileName
    if (Test-Path $zipPath) { Remove-Item $zipPath }
    
    # Load System.IO.Compression
    [System.Reflection.Assembly]::LoadWithPartialName("System.IO.Compression") | Out-Null
    
    # Open the zip file for writing
    $stream = [System.IO.File]::OpenWrite($zipPath)
    $archive = [System.IO.Compression.ZipArchive]::new($stream, [System.IO.Compression.ZipArchiveMode]::Create)
    
    # Add directory entry first (must end with a forward slash)
    $dirEntryName = $sourceDirName + "/"
    $dirEntry = $archive.CreateEntry($dirEntryName)
    
    # Add all files in the directory directly from original path
    $sourceFullPath = (Get-Item $sourceDirName).FullName
    $files = Get-ChildItem -Path $sourceFullPath -File -Recurse -Exclude "*.zip"
    foreach ($file in $files) {
        # Calculate the relative path within the directory
        $relativePath = $file.FullName.Substring($sourceFullPath.Length + 1)
        # Normalize path separators to forward slash
        $entryName = $sourceDirName + "/" + $relativePath.Replace("\", "/")
        
        Write-Host "Adding entry to $zipFileName - $entryName"
        
        # Create entry and write bytes
        $entry = $archive.CreateEntry($entryName)
        $entryStream = $entry.Open()
        $fileBytes = [System.IO.File]::ReadAllBytes($file.FullName)
        $entryStream.Write($fileBytes, 0, $fileBytes.Length)
        $entryStream.Close()
    }
    
    $archive.Dispose()
    $stream.Close()
    
    Write-Host "Created $zipFileName successfully."
}

# 2. Package repository
Create-KodiZip -sourceDirName "repository.movierulz" -zipFileName "repository.movierulz-1.0.0.zip"
# Copy zip inside the repository folder itself for Kodi repository indexing structure
Copy-Item -Path "repository.movierulz-1.0.0.zip" -Destination "repository.movierulz/repository.movierulz-1.0.0.zip" -Force

# 3. Package plugin
Create-KodiZip -sourceDirName "plugin.video.movierulz" -zipFileName "plugin.video.movierulz-1.0.0.zip"
# Copy zip inside the plugin folder itself for Kodi repository indexing structure
Copy-Item -Path "plugin.video.movierulz-1.0.0.zip" -Destination "plugin.video.movierulz/plugin.video.movierulz-1.0.0.zip" -Force

# 4. Copy to GitHub Pages directory
$ghPagesDir = "C:\Users\jaisimha.seelam\OneDrive - ascendion\Documents\jaisimhaseelam.github.io"
if (Test-Path $ghPagesDir) {
    Copy-Item -Path "repository.movierulz-1.0.0.zip" -Destination (Join-Path $ghPagesDir "repository.movierulz-1.0.0.zip") -Force
    Copy-Item -Path "plugin.video.movierulz-1.0.0.zip" -Destination (Join-Path $ghPagesDir "plugin.video.movierulz-1.0.0.zip") -Force
    Write-Host "Copied zip files to GitHub Pages directory."
} else {
    Write-Warning "GitHub Pages directory not found at $ghPagesDir"
}

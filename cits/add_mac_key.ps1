# Add Mac SSH public key to authorized_keys
$key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFXjRl8inYMa4q/Idwl4Kk6njtciiRReq44y7iKBYe3d hirokmiyao@mac"
$authFile = "$env:USERPROFILE\.ssh\authorized_keys"
$existing = Get-Content $authFile -ErrorAction SilentlyContinue
if ($existing -notcontains $key) {
    Add-Content -Path $authFile -Value $key
    Write-Host "Key added successfully"
} else {
    Write-Host "Key already exists"
}
Get-Content $authFile

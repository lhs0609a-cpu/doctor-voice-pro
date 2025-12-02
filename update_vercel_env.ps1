# Remove old environment variables
Write-Host "Removing old NEXT_PUBLIC_API_URL from all environments..."
cd frontend

# Remove from Production
echo "y" | vercel env rm NEXT_PUBLIC_API_URL production 2>$null

# Remove from Preview
echo "y" | vercel env rm NEXT_PUBLIC_API_URL preview 2>$null

# Remove from Development
echo "y" | vercel env rm NEXT_PUBLIC_API_URL development 2>$null

Write-Host "Old variables removed."
Write-Host ""
Write-Host "Adding new NEXT_PUBLIC_API_URL..."

# Add the correct value
$apiUrl = "https://doctor-voice-pro-backend.fly.dev"
echo $apiUrl | vercel env add NEXT_PUBLIC_API_URL production
echo $apiUrl | vercel env add NEXT_PUBLIC_API_URL preview
echo $apiUrl | vercel env add NEXT_PUBLIC_API_URL development

Write-Host "Environment variables updated!"

$ErrorActionPreference = "Stop"

$SDK = "C:\Users\User\AppData\Local\Android\Sdk"
$BUILD_TOOLS = "$SDK\build-tools\35.0.0"
$PLATFORM = "$SDK\platforms\android-34"
$JBR = "C:\Program Files\Android\Android Studio\jbr"
$KEYSTORE = "$env:USERPROFILE\.android\debug.keystore"

$SRC = "src\main"
$OUT = "build"

Write-Host "=== Compiling Java ==="
& "$JBR\bin\javac.exe" -d $OUT\classes -source 11 -target 11 -bootclasspath "$PLATFORM\android.jar" "$SRC\java\com\a11y\dummy\DummyAccessibilityService.java" 2>&1

Write-Host "=== Converting to DEX ==="
& "$BUILD_TOOLS\d8.bat" --lib "$PLATFORM\android.jar" --min-api 21 --output $OUT $OUT\classes\com\a11y\dummy\DummyAccessibilityService.class 2>&1

Write-Host "=== Creating APK ==="
& "$BUILD_TOOLS\aapt.exe" package -f -M "$SRC\AndroidManifest.xml" -I "$PLATFORM\android.jar" -F "$OUT\unsigned.apk" 2>&1

Write-Host "=== Adding DEX ==="
& "$BUILD_TOOLS\aapt.exe" add "$OUT\unsigned.apk" "$OUT\classes.dex" 2>&1

Write-Host "=== Signing ==="
& "$BUILD_TOOLS\apksigner.bat" sign --ks "$KEYSTORE" --ks-key-alias androiddebugkey --ks-pass pass:android --key-pass pass:android --out "$OUT\dummy-a11y.apk" "$OUT\unsigned.apk" 2>&1

Write-Host "=== Done ==="
Write-Host "APK: $OUT\dummy-a11y.apk"

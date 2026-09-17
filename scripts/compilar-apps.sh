#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  RAMAS 2 y 3: App Store y Google Play, del MISMO frontend.
#
#  Compila las dos, compara el frontend byte a byte y NO sube nada si difieren.
#  Ese fue el otro fallo del 1-sep-2026: publicar en una tienda una cosa y en la
#  otra otra, o subir a revision un build que no llevaba lo ultimo.
#
#  Uso:  scripts/compilar-apps.sh 1.0.12
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")/.."
RAIZ="$(pwd)"
VERSION="${1:?falta la version, p.ej. 1.0.12}"
export JAVA_HOME=/opt/homebrew/opt/openjdk@21
export PATH="$JAVA_HOME/bin:$PATH"

paso() { printf "\n\033[1m── %s\033[0m\n" "$1"; }
ok()   { printf "   ✓ %s\n" "$1"; }
malo() { printf "   ✗ %s\n" "$1"; exit 1; }

cd mobile
# El numero de build se pide a APPLE, no al fichero local.
IOS_BUILD=$(python3 "$RAIZ/scripts/siguiente-build-ios.py" 2>/dev/null || true)
if [ -z "$IOS_BUILD" ]; then
  echo "   ! no pude preguntar a Apple; uso el contador local +1"
  IOS_BUILD=$(( $(grep -m1 -o 'CURRENT_PROJECT_VERSION = [0-9]*' ios/App/App.xcodeproj/project.pbxproj | grep -o '[0-9]*') + 1 ))
fi
AND_VC=$((    $(grep -m1 -o 'versionCode [0-9]*' android/app/build.gradle | grep -o '[0-9]*') + 1 ))

paso "Versiones"
sed -i '' "s/MARKETING_VERSION = .*/MARKETING_VERSION = $VERSION;/g" ios/App/App.xcodeproj/project.pbxproj
sed -i '' "s/CURRENT_PROJECT_VERSION = .*/CURRENT_PROJECT_VERSION = $IOS_BUILD;/g" ios/App/App.xcodeproj/project.pbxproj
sed -i '' "s/versionCode [0-9]*/versionCode $AND_VC/" android/app/build.gradle
sed -i '' "s/versionName \".*\"/versionName \"$VERSION\"/" android/app/build.gradle
ok "iOS $VERSION ($IOS_BUILD) · Android $VERSION ($AND_VC)"

paso "Metiendo el frontend en las dos"
npx cap sync ios >/dev/null && npx cap sync android >/dev/null
ok "sincronizado"

# ── SELLO DE VERSION (17-sep-2026) ──────────────────────────────────────────
# La app no enseñaba su version por ningun lado y eso costo TRES cacerias de
# fallos inexistentes (6-sep muro de pago, 8-sep Niaz 2, 13-sep relazione): en
# los tres el codigo estaba bien y lo que faltaba era saber que binario tenia
# el founder delante. Se sella AQUI, en la copia que va al binario, y no en
# `frontend/` — asi la web sigue enseñando su propia version de despliegue y
# los dos binarios siguen siendo identicos entre si, que es lo que comprueba
# el paso de abajo.
paso "Sellando la version dentro del binario"
# Cada tienda lleva SU numero de build: en Android el versionCode y en iOS el
# suyo, que no coinciden. Si se sellara el mismo en las dos, quien abre la app
# en Android leeria un numero de iOS — peor que no enseñar nada, porque miente.
sed -i '' "s|__DM_VERSION__|$VERSION ($IOS_BUILD)|g" ios/App/App/public/index.html
sed -i '' "s|__DM_VERSION__|$VERSION ($AND_VC)|g"    android/app/src/main/assets/public/index.html
grep -q "$VERSION ($IOS_BUILD)" ios/App/App/public/index.html \
  || malo "no se pudo sellar la version en iOS"
grep -q "$VERSION ($AND_VC)" android/app/src/main/assets/public/index.html \
  || malo "no se pudo sellar la version en Android"
ok "sellado: iOS $VERSION ($IOS_BUILD) · Android $VERSION ($AND_VC)"

paso "Compilando Android"
( cd android && ./gradlew bundleRelease -q )
AAB=android/app/build/outputs/bundle/release/app-release.aab
[ -f "$AAB" ] || malo "no se genero el AAB"
unzip -p "$AAB" base/assets/public/index.html > /tmp/rama_android.html
ok "AAB listo ($(du -h "$AAB" | cut -f1))"

paso "Compilando iOS"
( cd ios/App && rm -rf /tmp/DMbuild.xcarchive \
  && xcodebuild -project App.xcodeproj -scheme App -configuration Release \
     -destination 'generic/platform=iOS' -archivePath /tmp/DMbuild.xcarchive archive \
     -allowProvisioningUpdates >/dev/null )
rm -rf /tmp/DMexport && xcodebuild -exportArchive -archivePath /tmp/DMbuild.xcarchive \
  -exportOptionsPlist "$RAIZ/scripts/exportOptions.plist" -exportPath /tmp/DMexport \
  -allowProvisioningUpdates >/dev/null
rm -rf /tmp/rama_ios && mkdir /tmp/rama_ios && ( cd /tmp/rama_ios && unzip -q /tmp/DMexport/App.ipa )
cp /tmp/rama_ios/Payload/App.app/public/index.html /tmp/rama_ios.html
ok "IPA lista ($(du -h /tmp/DMexport/App.ipa | cut -f1))"

paso "LA COMPROBACION QUE IMPORTA"
# El sello de version es el UNICO byte que puede diferir, y a proposito: lleva
# el numero de build de cada tienda. Se normaliza antes de comparar para que la
# comprobacion siga siendo byte a byte en todo lo demas, que es lo que importa.
sed "s|$VERSION ($IOS_BUILD)|__DM_VERSION__|g" /tmp/rama_ios.html     > /tmp/rama_ios_n.html
sed "s|$VERSION ($AND_VC)|__DM_VERSION__|g"    /tmp/rama_android.html > /tmp/rama_android_n.html
if cmp -s /tmp/rama_ios_n.html /tmp/rama_android_n.html; then
  ok "las dos tiendas llevan EXACTAMENTE el mismo frontend (sello de version aparte)"
  ok "md5: $(md5 -q /tmp/rama_ios_n.html)"
else
  malo "iOS y Android llevan frontends DISTINTOS — no subir"
fi

paso "Listo para subir"
echo "   iOS:      xcrun altool --upload-app -f /tmp/DMexport/App.ipa -t ios \\"
echo "               --apiKey 26Q473G2V8 --apiIssuer 4af2188f-87d6-459c-88ea-793b67971435"
echo "   Android:  $AAB"
echo
echo "   Ninguna de las dos se sube sola: hace falta el OK del founder."

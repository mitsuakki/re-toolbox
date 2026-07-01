# ctf-re-image

Image Docker tout-en-un pour le reverse engineering en CTF, avec radare2 et
Ghidra branchés en MCP (utilisables directement par Claude ou tout autre
client MCP), et BinDiff / angr / AFL++ / honggfuzz / Android (apktool, jadx,
frida) installés en CLI.

## Build & run

```bash
docker compose build
docker compose up -d
docker exec -it ctf-re bash
```

Le dossier `./workspace` sur l'hôte est monté dans `/workspace` du
conteneur : dépose tes binaires de challenge là-dedans.

## radare2 + r2mcp

Déjà installé et prêt. Pour le brancher à Claude Desktop ou tout client MCP,
copie l'entrée `radare2` de `configs/mcp-client-config.json` dans la config
de ton client (le `docker exec -i ctf-re r2pm -r r2mcp` lance le serveur
stdio à la demande, pas besoin de le démarrer manuellement).

En CLI direct dans le conteneur :
```bash
r2 -A /workspace/chall          # analyse classique
r2pm -r r2mcp -t                # liste les tools MCP exposés
```

`r2ghidra` est aussi installé, donc la commande `pdg` (décompilation via le
moteur Ghidra) fonctionne directement dans r2/r2mcp sans lancer Ghidra.

## Ghidra — les deux modes

### Headless (recommandé pour automatisation CTF)

Démarré automatiquement par l'entrypoint (`ENABLE_GHIDRA_HEADLESS_MCP=1` par
défaut) sur le port `8089`, exposé par compose. Branche l'entrée
`ghidra-headless` du fichier de config MCP.

```bash
curl http://localhost:8089/check_connection
docker cp ./mybin ctf-re:/data/mybin
curl -X POST -d "file=/data/mybin" http://localhost:8089/load_program
curl -X POST "http://localhost:8089/run_analysis?program=mybin"
curl "http://localhost:8089/decompile_function?program=mybin&name=main"
```

⚠️ Le build du jar `GhidraMCPHeadless.jar` se fait via Maven pendant le
build de l'image. S'il échoue faute de réseau au build-time, reconstruis-le
à la main dans le conteneur :
```bash
cd /opt/tools/ghidra-mcp && mvn -DskipTests -Dghidra.version=11.3.2 clean package
```

### GUI (plugin classique, via noVNC dans le navigateur)

```bash
docker compose down
ENABLE_GHIDRA_GUI=1 docker compose up -d
# puis ouvre http://localhost:6080/vnc.html dans ton navigateur
```

Dans la session VNC : lance `ghidraRun`, ouvre/importe ton binaire, puis
`File > Configure > Configure All Plugins > GhidraMCP` pour activer le
plugin, et `Tools > GhidraMCP > Start MCP Server`. Branche ensuite l'entrée
`ghidra-gui` de la config MCP (port 8080 par défaut, configurable dans le
plugin).

## BinDiff

CLI uniquement, pas de MCP officiel. Workflow classique :
```bash
# Exporte chaque binaire en .BinExport depuis Ghidra (script BinExportHeadless)
# ou IDA, puis :
bindiff old.BinExport new.BinExport
```

## angr

Installé avec pwntools, ropper, capstone, unicorn, z3-solver, lief, r2pipe.
Un wrapper CLI rapide est fourni mais le travail de Xavier peut-être utilisé :

```bash
angr-solve.py info ./chall
angr-solve.py find ./chall --stdin-len 32 --find "Correct" --avoid "Wrong"
angr-solve.py find ./chall --find-addr 0x401300 --avoid-addr 0x401234
```

Pour des scripts angr custom, l'environnement Python est directement
utilisable (`python3 -c "import angr; ..."`).

## Fuzzing (AFL++ / honggfuzz)

```bash
fuzz-init.sh afl ./chall            # scaffolde un dossier de corpus + affiche la commande
afl-fuzz -i fuzz-chall-afl/in -o fuzz-chall-afl/out -- ./chall @@

fuzz-init.sh hfuzz ./chall
honggfuzz -i fuzz-chall-hfuzz/in -o fuzz-chall-hfuzz/out -- ./chall ___FILE___
```

Pour binaire fermé sans recompilation : `afl-fuzz -Q ...` (mode QEMU).

## Android

```bash
apktool d app.apk -o app_decoded
jadx app.apk -d app_jadx_out
adb devices
frida -U -f com.example.app -l hook.js --no-pause
objection -g com.example.app explore
```

## Sécurité du conteneur

Le compose ajoute `CAP_SYS_PTRACE` et désactive seccomp (`unconfined`) car
gdb/strace/AFL en a besoin pour attacher aux processus et tracer les
syscalls. Garde ce conteneur dans un environnement isolé / un VM dédié si tu
fais tourner des binaires malveillants réels (pas juste des crackmes CTF).

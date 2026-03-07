### Windows-Native Local Services

For Windows, do not use the existing `.sh` service wrappers. They depend on Linux tools such as `tmux`, shell path semantics, and WSL-style Java paths. The repository now includes Python wrappers for the three local benchmark services:

- `services/genome-nexus/start_with_jacoco.py`
- `services/genome-nexus/stop_with_jacoco.py`
- `services/LanguageTool-6.7-SNAPSHOT/start_with_jacoco.py`
- `services/LanguageTool-6.7-SNAPSHOT/stop_with_jacoco.py`
- `services/restcountries/start_with_jacoco.py`
- `services/restcountries/stop_with_jacoco.py`

Recommended prerequisites on Windows:

- Docker Desktop running in Linux container mode
- Maven on `PATH`
- `JAVA8_HOME` configured for `genome-nexus` and `restcountries`
- `JAVA17_HOME` configured for `LanguageTool`

Example PowerShell session:

```powershell
$env:JAVA8_HOME = "C:\Program Files\Eclipse Adoptium\jdk-8.0.442.6-hotspot"
$env:JAVA17_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.0.14.7-hotspot"
```

The Python wrappers accept `--java`, `--mvn`, and `--docker` overrides, but by default they resolve tools from `JAVA8_HOME`, `JAVA17_HOME`, `JAVA_HOME`, and `PATH`. WSL and Git Bash are not required.

Examples:

```powershell
python services\restcountries\start_with_jacoco.py --tool-name manual
python services\restcountries\stop_with_jacoco.py --tool-name manual

python services\LanguageTool-6.7-SNAPSHOT\start_with_jacoco.py --tool-name manual
python services\LanguageTool-6.7-SNAPSHOT\stop_with_jacoco.py --tool-name manual

python services\genome-nexus\start_with_jacoco.py --tool-name manual --rebuild
python services\genome-nexus\stop_with_jacoco.py --tool-name manual
```

Each service stores runtime metadata under `target/runtime.json`, logs under `target/logs/`, the JaCoCo exec file under `target/jacoco.exec`, and a copied HTML report under `results/<service>/<tool-name>/jacoco/<timestamp>/`.

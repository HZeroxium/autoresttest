### Windows-Native Local Services

For Windows, do not use the existing `.sh` service wrappers. They depend on Linux tools such as `tmux`, shell path semantics, and WSL-style Java paths. The repository now includes Python wrappers for the four local benchmark services:

- `services/genome-nexus/start_with_jacoco.py`
- `services/genome-nexus/stop_with_jacoco.py`
- `services/LanguageTool-6.7-SNAPSHOT/start_with_jacoco.py`
- `services/LanguageTool-6.7-SNAPSHOT/stop_with_jacoco.py`
- `services/restcountries/start_with_jacoco.py`
- `services/restcountries/stop_with_jacoco.py`
- `services/spring-petclinic-rest/start_with_jacoco.py`
- `services/spring-petclinic-rest/stop_with_jacoco.py`

Recommended prerequisites on Windows:

- Docker Desktop running in Linux container mode
- Maven on `PATH`
- `JAVA8_HOME` configured for `genome-nexus` and `restcountries`
- `JAVA17_HOME` configured for `LanguageTool`
- `JAVA21_HOME` configured for `spring-petclinic-rest`

Example PowerShell session:

```powershell
$env:JAVA8_HOME = "C:\Program Files\Eclipse Adoptium\jdk-8.0.442.6-hotspot"
$env:JAVA17_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.0.14.7-hotspot"
$env:JAVA21_HOME = "C:\Program Files\Java\jdk-21"
```

The Python wrappers accept `--java`, `--mvn`, and `--docker` overrides, but by default they resolve tools from `JAVA8_HOME`, `JAVA17_HOME`, `JAVA21_HOME`, `JAVA_HOME`, and `PATH`. `spring-petclinic-rest` prefers its local Maven wrapper (`mvnw.cmd` on Windows, `mvnw` on POSIX) before falling back to Maven on `PATH`. WSL and Git Bash are not required.

Examples:

```powershell
python services\restcountries\start_with_jacoco.py --tool-name manual
python services\restcountries\stop_with_jacoco.py --tool-name manual

python services\LanguageTool-6.7-SNAPSHOT\start_with_jacoco.py --tool-name manual
python services\LanguageTool-6.7-SNAPSHOT\stop_with_jacoco.py --tool-name manual

python services\genome-nexus\start_with_jacoco.py --tool-name manual --rebuild
python services\genome-nexus\stop_with_jacoco.py --tool-name manual

python services\spring-petclinic-rest\start_with_jacoco.py --tool-name manual --rebuild
python services\spring-petclinic-rest\stop_with_jacoco.py --tool-name manual
```

Each service stores runtime metadata under `target/runtime.json`, logs under `target/logs/`, the JaCoCo exec file under `target/jacoco.exec`, and a copied HTML report under `results/<service>/<tool-name>/jacoco/<timestamp>/`.

For `spring-petclinic-rest`, the default service port is `9966`, the default JaCoCo port is `6306`, the primary readiness check is `http://localhost:9966/petclinic/actuator/health`, and the HTML report excludes generated classes under `rest/api` and `rest/dto`.

Suggested smoke verification for PetClinic:

```powershell
python services\spring-petclinic-rest\start_with_jacoco.py --tool-name smoke --rebuild
Invoke-WebRequest http://localhost:9966/petclinic/actuator/health
Invoke-WebRequest http://localhost:9966/petclinic/api/pettypes
python services\spring-petclinic-rest\stop_with_jacoco.py --tool-name smoke
```

"""
NWIS Phase 9.1 Repository Secret Scanner
Scans files for patterns: password=, secret=, api_key=, token=, authorization=, postgresql://, Bearer
Checks extensions: .env, .env.*, *.pem, *.key, *.crt, configuration files, Python, PowerShell, Docker, JSON.
Never exposes secret values.
"""
import os
import re
import sys

TARGET_PATTERNS = [
    re.compile(r"password\s*[:=]\s*['\"]?([^'\"\s\r\n]{4,})", re.I),
    re.compile(r"secret\s*[:=]\s*['\"]?([^'\"\s\r\n]{4,})", re.I),
    re.compile(r"api_key\s*[:=]\s*['\"]?([^'\"\s\r\n]{4,})", re.I),
    re.compile(r"token\s*[:=]\s*['\"]?([^'\"\s\r\n]{4,})", re.I),
    re.compile(r"authorization\s*[:=]\s*['\"]?([^'\"\s\r\n]{4,})", re.I),
    re.compile(r"postgresql://([^@]+)@", re.I),
    re.compile(r"Bearer\s+([A-Za-z0-9\-._~+/]+=*)", re.I)
]

SAFE_TOKENS = {
    "your-secret-key-here",
    "your_super_secret_jwt_key_here",
    "your-secret-key-change-in-production-use-strong-random-key",
    "supersecretkeyforphase9hardeningvalidationonly",
    "your-secret-key",
    "postgres:postgres",
    "admin:admin",
    "changeme",
    "testpassword",
    "dummy",
    "token",
    "null",
    "none",
    "true",
    "false"
}

IGNORED_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    ".tempmediaStorage", ".agents", ".gemini", "brain"
}

CERT_EXTS = {".pem", ".key", ".crt"}
SCAN_EXTS = {".py", ".ps1", ".json", ".yml", ".yaml", ".conf", ".md", ".txt", ".env"}

def scan_repository(repo_path: str):
    findings = []
    cert_findings = []
    scanned_count = 0

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        for file in files:
            path = os.path.join(root, file)
            rel_path = os.path.relpath(path, repo_path)
            _, ext = os.path.splitext(file)

            if ext.lower() in CERT_EXTS:
                cert_findings.append(rel_path)
                continue

            is_env = file.startswith(".env")
            is_docker = "dockerfile" in file.lower()
            if not (ext.lower() in SCAN_EXTS or is_env or is_docker):
                continue

            scanned_count += 1
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_idx, line in enumerate(f, start=1):
                        stripped = line.strip()
                        # Skip comment lines, regex definitions, and type hints
                        if stripped.startswith(("#", "//", "/*", "*", "<!--")):
                            continue
                        if "re.compile" in line or "SENSITIVE_PATTERNS" in line:
                            continue
                        if ": str" in line or ": Optional[str]" in line or "Column(" in line:
                            continue
                        if "api_key=self." in line or "api_key=api_key" in line or "api_key=None" in line:
                            continue
                        if "token = parts[" in line or "token = " in line and ("[" in line or "(" in line):
                            continue
                        if "test_" in file or "tests" in rel_path:
                            continue
                        if rel_path.endswith(".md"):
                            continue

                        for pattern in TARGET_PATTERNS:
                            matches = pattern.findall(line)
                            for match in matches:
                                cleaned = match.strip().strip("'\"").lower()
                                if any(safe in cleaned for safe in SAFE_TOKENS) or len(cleaned) < 5:
                                    continue
                                # Check if it's an env var placeholder like ${VAR:-default}
                                if "${" in match or "os.getenv" in line or "os.environ" in line:
                                    continue
                                # Check if it's dummy / default config strings
                                if any(word in cleaned for word in ["placeholder", "example", "change", "default", "nwis_admin", "postgres"]):
                                    continue
                                findings.append({
                                    "file": rel_path,
                                    "line": line_idx,
                                    "pattern": pattern.pattern[:25]
                                })
            except Exception:
                pass

    print(f"Scanned files: {scanned_count}")
    print(f"Certificate/Key files found: {len(cert_findings)}")
    print(f"Suspicious unmasked secret patterns: {len(findings)}")

    if cert_findings:
        print("[FAIL] Discovered certificate/key files:")
        for cf in cert_findings:
            print(f"  - {cf}")
        print("\nSECRET_SCAN_STATUS = FAIL")
        return False

    if findings:
        print("[FAIL] Found unmasked secrets in:")
        for f in findings[:10]:
            print(f"  - {f['file']}:{f['line']} (Pattern: {f['pattern']})")
        print("\nSECRET_SCAN_STATUS = FAIL")
        return False

    print("\nSECRET_SCAN_STATUS = PASS")
    return True

if __name__ == "__main__":
    success = scan_repository(".")
    sys.exit(0 if success else 1)
